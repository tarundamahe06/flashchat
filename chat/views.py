from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from .models import Conversation, Group, GroupMembership, Message
from .serializers import (
    ConversationSerializer,
    GroupSerializer,
    CreateGroupSerializer,
    MessageSerializer,
    SendMessageSerializer,
    AddMembersSerializer,
    RemoveMemberSerializer,
)

User = get_user_model()


# ─────────────────────────────────────────────
# DM Conversation Views
# ─────────────────────────────────────────────

class ConversationListView(generics.ListAPIView):
    """
    GET /api/chat/conversations/
    List all DM conversations for the authenticated user.
    """
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(
            participants=self.request.user
        ).prefetch_related("participants", "messages")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class GetOrCreateConversationView(APIView):
    """
    POST /api/chat/conversations/
    Get or create a DM conversation with another user.
    Body: { "username": "other_username" }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        username = request.data.get("username", "").strip()
        if not username:
            return Response(
                {"error": "Username is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        other_user = get_object_or_404(User, username=username)

        if other_user == request.user:
            return Response(
                {"error": "You cannot start a conversation with yourself."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check block status
        if not request.user.can_message(other_user):
            return Response(
                {"error": "You cannot message this user."},
                status=status.HTTP_403_FORBIDDEN
            )

        conversation, created = Conversation.get_or_create_dm(request.user, other_user)
        serializer = ConversationSerializer(conversation, context={"request": request})
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class ConversationMessageListView(generics.ListAPIView):
    """
    GET /api/chat/conversations/<conversation_id>/messages/
    Load message history for a DM conversation.
    """
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        conversation = get_object_or_404(
            Conversation,
            pk=self.kwargs["conversation_id"],
            participants=self.request.user
        )
        # Mark messages as read
        conversation.messages.filter(
            is_read=False
        ).exclude(sender=self.request.user).update(is_read=True)

        return conversation.messages.select_related("sender").all()


# ─────────────────────────────────────────────
# Group Views
# ─────────────────────────────────────────────

class GroupListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/chat/groups/  — List all groups the user is a member of
    POST /api/chat/groups/  — Create a new group
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CreateGroupSerializer
        return GroupSerializer

    def get_queryset(self):
        return Group.objects.filter(
            members=self.request.user,
            is_active=True
        ).prefetch_related("members", "messages", "memberships__user")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def create(self, request, *args, **kwargs):
        serializer = CreateGroupSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        group = serializer.save()
        return Response(
            GroupSerializer(group, context={"request": request}).data,
            status=status.HTTP_201_CREATED
        )


class GroupDetailView(generics.RetrieveAPIView):
    """
    GET /api/chat/groups/<group_id>/
    Retrieve group details. User must be a member.
    """
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        group = get_object_or_404(
            Group,
            pk=self.kwargs["group_id"],
            is_active=True
        )
        if not group.members.filter(pk=self.request.user.pk).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You are not a member of this group.")
        return group

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class GroupUpdateView(generics.UpdateAPIView):
    """
    PUT/PATCH /api/chat/groups/<group_id>/update/
    Update group name or description. Admin only.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        group = get_object_or_404(Group, pk=self.kwargs["group_id"], is_active=True)
        if not GroupMembership.objects.filter(
            group=group, user=self.request.user, is_admin=True
        ).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only group admins can update group details.")
        return group

    def get_serializer_class(self):
        from .serializers import CreateGroupSerializer
        return CreateGroupSerializer

    def update(self, request, *args, **kwargs):
        group = self.get_object()
        data = {k: v for k, v in request.data.items() if k in ["name", "description"]}
        serializer = self.get_serializer(group, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            GroupSerializer(group, context={"request": request}).data
        )


class GroupDeleteView(APIView):
    """
    DELETE /api/chat/groups/<group_id>/delete/
    Delete a group. Creator/admin only.
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, group_id):
        group = get_object_or_404(Group, pk=group_id, is_active=True)

        if group.creator != request.user:
            return Response(
                {"error": "Only the group creator can delete this group."},
                status=status.HTTP_403_FORBIDDEN
            )

        group.is_active = False
        group.save()
        return Response(
            {"message": "Group deleted successfully."},
            status=status.HTTP_200_OK
        )


class GroupLeaveView(APIView):
    """
    POST /api/chat/groups/<group_id>/leave/
    Leave a group. Creator cannot leave — must delete instead.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id):
        group = get_object_or_404(Group, pk=group_id, is_active=True)

        if not group.members.filter(pk=request.user.pk).exists():
            return Response(
                {"error": "You are not a member of this group."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if group.creator == request.user:
            return Response(
                {"error": "You are the group creator. Delete the group instead of leaving."},
                status=status.HTTP_400_BAD_REQUEST
            )

        GroupMembership.objects.filter(user=request.user, group=group).delete()
        return Response(
            {"message": "You have left the group."},
            status=status.HTTP_200_OK
        )


class GroupAddMembersView(APIView):
    """
    POST /api/chat/groups/<group_id>/members/add/
    Add members to a group. Admin only.
    Body: { "member_ids": [1, 2, 3] }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id):
        group = get_object_or_404(Group, pk=group_id, is_active=True)

        if not GroupMembership.objects.filter(
            group=group, user=request.user, is_admin=True
        ).exists():
            return Response(
                {"error": "Only group admins can add members."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = AddMembersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        added = []
        already_member = []

        for user_id in serializer.validated_data["member_ids"]:
            try:
                user = User.objects.get(pk=user_id)
                membership, created = GroupMembership.objects.get_or_create(
                    user=user, group=group
                )
                if created:
                    added.append(user.username)
                else:
                    already_member.append(user.username)
            except User.DoesNotExist:
                pass

        return Response({
            "added": added,
            "already_member": already_member,
        }, status=status.HTTP_200_OK)


class GroupRemoveMemberView(APIView):
    """
    POST /api/chat/groups/<group_id>/members/remove/
    Remove a member from a group. Admin only.
    Body: { "user_id": 5 }
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id):
        group = get_object_or_404(Group, pk=group_id, is_active=True)

        if not GroupMembership.objects.filter(
            group=group, user=request.user, is_admin=True
        ).exists():
            return Response(
                {"error": "Only group admins can remove members."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = RemoveMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_to_remove = get_object_or_404(User, pk=serializer.validated_data["user_id"])

        if user_to_remove == request.user:
            return Response(
                {"error": "You cannot remove yourself. Leave the group instead."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user_to_remove == group.creator:
            return Response(
                {"error": "You cannot remove the group creator."},
                status=status.HTTP_400_BAD_REQUEST
            )

        deleted, _ = GroupMembership.objects.filter(
            user=user_to_remove, group=group
        ).delete()

        if deleted:
            return Response(
                {"message": f"{user_to_remove.username} has been removed from the group."},
                status=status.HTTP_200_OK
            )
        return Response(
            {"error": "User is not a member of this group."},
            status=status.HTTP_400_BAD_REQUEST
        )


class GroupMessageListView(generics.ListAPIView):
    """
    GET /api/chat/groups/<group_id>/messages/
    Load message history for a group. User must be a member.
    """
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        group = get_object_or_404(
            Group,
            pk=self.kwargs["group_id"],
            is_active=True
        )
        if not group.members.filter(pk=self.request.user.pk).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You are not a member of this group.")

        # Mark messages as read
        group.messages.filter(
            is_read=False
        ).exclude(sender=self.request.user).update(is_read=True)

        return group.messages.select_related("sender").all()


class DeleteMessageView(APIView):
    """
    DELETE /api/chat/messages/<message_id>/
    Soft delete a message. Only the sender can delete their message.
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, message_id):
        message = get_object_or_404(Message, pk=message_id)

        if message.sender != request.user:
            return Response(
                {"error": "You can only delete your own messages."},
                status=status.HTTP_403_FORBIDDEN
            )

        if message.is_deleted:
            return Response(
                {"error": "Message is already deleted."},
                status=status.HTTP_400_BAD_REQUEST
            )

        message.is_deleted = True
        message.save()
        return Response(
            {"message": "Message deleted successfully."},
            status=status.HTTP_200_OK
        )