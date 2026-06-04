
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import Conversation, Group, GroupMembership, Message

User = get_user_model()


# ─────────────────────────────────────────────
# Helper — Send notification to a user
# ─────────────────────────────────────────────

async def send_notification(channel_layer, user_id, data):
    """
    Push a notification to a specific user's notification channel.
    """
    await channel_layer.group_send(
        f"notifications_{user_id}",
        {
            "type": "notification_message",
            **data,
        }
    )


# ─────────────────────────────────────────────
# Notification Consumer
# ─────────────────────────────────────────────

class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    URL: ws://host/ws/notifications/<user_id>/?token=<jwt>

    Receives notification events when any new message arrives
    for the connected user across all conversations and groups.
    """

    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        self.user_id = self.scope["url_route"]["kwargs"]["user_id"]

        # Security: only allow user to connect to their own notification channel
        if str(self.user.id) != str(self.user_id):
            await self.close()
            return

        self.group_name = f"notifications_{self.user_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        # Notification channel is receive-only from server
        pass

    async def notification_message(self, event):
        """Send notification event to WebSocket client."""
        await self.send(text_data=json.dumps({
            "type": "notification",
            "chat_type": event.get("chat_type"),
            "chat_id": event.get("chat_id"),
            "chat_name": event.get("chat_name"),
            "message_id": event.get("message_id"),
            "content": event.get("content"),
            "sender_id": event.get("sender_id"),
            "sender_username": event.get("sender_username"),
            "sender_full_name": event.get("sender_full_name"),
            "created_at": event.get("created_at"),
        }))


# ─────────────────────────────────────────────
# DM Consumer
# ─────────────────────────────────────────────

class DMConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for direct messages.
    URL: ws://host/ws/dm/<conversation_id>/?token=<jwt>
    """

    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"dm_{self.conversation_id}"

        if not await self.is_participant():
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON.")
            return

        message_type = data.get("type")

        if message_type == "message.send":
            await self.handle_send_message(data)
        elif message_type == "message.delete":
            await self.handle_delete_message(data)
        else:
            await self.send_error("Unknown message type.")

    async def handle_send_message(self, data):
        content = data.get("content", "").strip()

        if not content:
            await self.send_error("Message content cannot be empty.")
            return

        if len(content) > 2000:
            await self.send_error("Message too long. Maximum 2000 characters.")
            return

        can_send, error = await self.can_send_message()
        if not can_send:
            await self.send_error(error)
            return

        message, other_user = await self.save_dm_message(content)

        event = {
            "type": "chat_message",
            "message_id": message.id,
            "content": message.content,
            "sender_id": self.user.id,
            "sender_username": self.user.username,
            "sender_full_name": self.user.full_name,
            "created_at": message.created_at.isoformat(),
            "is_deleted": False,
        }

        # Broadcast message to conversation room
        await self.channel_layer.group_send(self.room_group_name, event)

        # Send notification to the other user
        if other_user:
            await send_notification(self.channel_layer, other_user.id, {
                "chat_type": "dm",
                "chat_id": int(self.conversation_id),
                "chat_name": self.user.full_name,
                "message_id": message.id,
                "content": message.content,
                "sender_id": self.user.id,
                "sender_username": self.user.username,
                "sender_full_name": self.user.full_name,
                "created_at": message.created_at.isoformat(),
            })

    async def handle_delete_message(self, data):
        message_id = data.get("message_id")
        if not message_id:
            await self.send_error("message_id is required.")
            return

        success, error = await self.delete_dm_message(message_id)
        if not success:
            await self.send_error(error)
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "message_deleted",
                "message_id": message_id,
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "message.new",
            "message_id": event["message_id"],
            "content": event["content"],
            "sender_id": event["sender_id"],
            "sender_username": event["sender_username"],
            "sender_full_name": event["sender_full_name"],
            "created_at": event["created_at"],
            "is_deleted": event["is_deleted"],
        }))

    async def message_deleted(self, event):
        await self.send(text_data=json.dumps({
            "type": "message.deleted",
            "message_id": event["message_id"],
        }))

    async def send_error(self, error_message):
        await self.send(text_data=json.dumps({
            "type": "error",
            "message": error_message,
        }))

    @database_sync_to_async
    def is_participant(self):
        return Conversation.objects.filter(
            pk=self.conversation_id,
            participants=self.user
        ).exists()

    @database_sync_to_async
    def can_send_message(self):
        try:
            conversation = Conversation.objects.prefetch_related("participants").get(
                pk=self.conversation_id
            )
            other_user = conversation.participants.exclude(pk=self.user.pk).first()
            if not other_user:
                return False, "Conversation participant not found."
            if not self.user.can_message(other_user):
                return False, "You cannot send messages to this user."
            return True, None
        except Conversation.DoesNotExist:
            return False, "Conversation not found."

    @database_sync_to_async
    def save_dm_message(self, content):
        conversation = Conversation.objects.get(pk=self.conversation_id)
        message = Message.objects.create(
            conversation=conversation,
            sender=self.user,
            content=content,
        )
        conversation.save()
        other_user = conversation.participants.exclude(pk=self.user.pk).first()
        return message, other_user

    @database_sync_to_async
    def delete_dm_message(self, message_id):
        try:
            message = Message.objects.get(
                pk=message_id,
                conversation_id=self.conversation_id
            )
            if message.sender != self.user:
                return False, "You can only delete your own messages."
            if message.is_deleted:
                return False, "Message is already deleted."
            message.is_deleted = True
            message.save()
            return True, None
        except Message.DoesNotExist:
            return False, "Message not found."


# ─────────────────────────────────────────────
# Group Consumer
# ─────────────────────────────────────────────

class GroupConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for group messages.
    URL: ws://host/ws/group/<group_id>/?token=<jwt>
    """

    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        self.group_id = self.scope["url_route"]["kwargs"]["group_id"]
        self.room_group_name = f"group_{self.group_id}"

        if not await self.is_member():
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON.")
            return

        message_type = data.get("type")

        if message_type == "message.send":
            await self.handle_send_message(data)
        elif message_type == "message.delete":
            await self.handle_delete_message(data)
        else:
            await self.send_error("Unknown message type.")

    async def handle_send_message(self, data):
        content = data.get("content", "").strip()

        if not content:
            await self.send_error("Message content cannot be empty.")
            return

        if len(content) > 2000:
            await self.send_error("Message too long. Maximum 2000 characters.")
            return

        message, other_member_ids = await self.save_group_message(content)

        event = {
            "type": "chat_message",
            "message_id": message.id,
            "content": message.content,
            "sender_id": self.user.id,
            "sender_username": self.user.username,
            "sender_full_name": self.user.full_name,
            "created_at": message.created_at.isoformat(),
            "is_deleted": False,
        }

        # Broadcast to group room
        await self.channel_layer.group_send(self.room_group_name, event)

        # Send notification to all other members
        group_name = await self.get_group_name()
        for member_id in other_member_ids:
            await send_notification(self.channel_layer, member_id, {
                "chat_type": "group",
                "chat_id": int(self.group_id),
                "chat_name": group_name,
                "message_id": message.id,
                "content": message.content,
                "sender_id": self.user.id,
                "sender_username": self.user.username,
                "sender_full_name": self.user.full_name,
                "created_at": message.created_at.isoformat(),
            })

    async def handle_delete_message(self, data):
        message_id = data.get("message_id")
        if not message_id:
            await self.send_error("message_id is required.")
            return

        success, error = await self.delete_group_message(message_id)
        if not success:
            await self.send_error(error)
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "message_deleted",
                "message_id": message_id,
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "message.new",
            "message_id": event["message_id"],
            "content": event["content"],
            "sender_id": event["sender_id"],
            "sender_username": event["sender_username"],
            "sender_full_name": event["sender_full_name"],
            "created_at": event["created_at"],
            "is_deleted": event["is_deleted"],
        }))

    async def message_deleted(self, event):
        await self.send(text_data=json.dumps({
            "type": "message.deleted",
            "message_id": event["message_id"],
        }))

    async def send_error(self, error_message):
        await self.send(text_data=json.dumps({
            "type": "error",
            "message": error_message,
        }))

    @database_sync_to_async
    def is_member(self):
        return GroupMembership.objects.filter(
            group_id=self.group_id,
            user=self.user
        ).exists()

    @database_sync_to_async
    def get_group_name(self):
        try:
            return Group.objects.get(pk=self.group_id).name
        except Group.DoesNotExist:
            return "Group"

    @database_sync_to_async
    def save_group_message(self, content):
        group = Group.objects.get(pk=self.group_id)
        message = Message.objects.create(
            group=group,
            sender=self.user,
            content=content,
        )
        group.save()
        # Get all member IDs except sender for notifications
        other_member_ids = list(
            GroupMembership.objects.filter(group=group)
            .exclude(user=self.user)
            .values_list("user_id", flat=True)
        )
        return message, other_member_ids

    @database_sync_to_async
    def delete_group_message(self, message_id):
        try:
            message = Message.objects.get(
                pk=message_id,
                group_id=self.group_id
            )
            if message.sender != self.user:
                return False, "You can only delete your own messages."
            if message.is_deleted:
                return False, "Message is already deleted."
            message.is_deleted = True
            message.save()
            return True, None
        except Message.DoesNotExist:
            return False, "Message not found."