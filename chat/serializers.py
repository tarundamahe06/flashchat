from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Conversation, Group, GroupMembership, Message

User = get_user_model()


class ParticipantSerializer(serializers.ModelSerializer):
    """Lightweight user info used inside chat serializers."""
    class Meta:
        model = User
        fields = ["id", "username", "full_name"]


# ─────────────────────────────────────────────
# Message Serializers
# ─────────────────────────────────────────────

class MessageSerializer(serializers.ModelSerializer):
    sender = ParticipantSerializer(read_only=True)
    content = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "content",
            "created_at",
            "is_read",
            "is_deleted",
        ]

    def get_content(self, obj):
        return obj.get_display_content()


class SendMessageSerializer(serializers.Serializer):
    """Used to validate incoming message content from REST API."""
    content = serializers.CharField(max_length=2000, allow_blank=False)


# ─────────────────────────────────────────────
# Conversation (DM) Serializers
# ─────────────────────────────────────────────

class ConversationSerializer(serializers.ModelSerializer):
    participants = ParticipantSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "participants",
            "last_message",
            "unread_count",
            "created_at",
            "updated_at",
        ]

    def get_last_message(self, obj):
        last = obj.messages.filter(is_deleted=False).last()
        if last:
            return MessageSerializer(last).data
        return None

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if request:
            return obj.messages.filter(
                is_read=False,
                is_deleted=False
            ).exclude(sender=request.user).count()
        return 0


# ─────────────────────────────────────────────
# Group Serializers
# ─────────────────────────────────────────────

class GroupMembershipSerializer(serializers.ModelSerializer):
    user = ParticipantSerializer(read_only=True)

    class Meta:
        model = GroupMembership
        fields = ["user", "is_admin", "joined_at"]


class GroupSerializer(serializers.ModelSerializer):
    creator = ParticipantSerializer(read_only=True)
    members = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "description",
            "creator",
            "members",
            "member_count",
            "last_message",
            "unread_count",
            "is_member",
            "is_admin",
            "created_at",
            "updated_at",
        ]

    def get_members(self, obj):
        memberships = obj.memberships.select_related("user").all()
        return GroupMembershipSerializer(memberships, many=True).data

    def get_member_count(self, obj):
        return obj.members.count()

    def get_last_message(self, obj):
        last = obj.messages.filter(is_deleted=False).last()
        if last:
            return MessageSerializer(last).data
        return None

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if request:
            return obj.messages.filter(
                is_read=False,
                is_deleted=False
            ).exclude(sender=request.user).count()
        return 0

    def get_is_member(self, obj):
        request = self.context.get("request")
        if request:
            return obj.members.filter(pk=request.user.pk).exists()
        return False

    def get_is_admin(self, obj):
        request = self.context.get("request")
        if request:
            return obj.memberships.filter(
                user=request.user,
                is_admin=True
            ).exists()
        return False


class CreateGroupSerializer(serializers.ModelSerializer):
    member_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        default=list,
    )

    class Meta:
        model = Group
        fields = ["id", "name", "description", "member_ids"]

    def validate_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Group name must be at least 3 characters.")
        return value.strip()

    def create(self, validated_data):
        member_ids = validated_data.pop("member_ids", [])
        request = self.context.get("request")
        creator = request.user

        group = Group.objects.create(
            creator=creator,
            **validated_data
        )

        # Add creator as admin member
        GroupMembership.objects.create(user=creator, group=group, is_admin=True)

        # Add other members
        for user_id in member_ids:
            try:
                user = User.objects.get(pk=user_id)
                if user != creator:
                    GroupMembership.objects.get_or_create(user=user, group=group)
            except User.DoesNotExist:
                pass

        return group


class AddMembersSerializer(serializers.Serializer):
    member_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
    )


class RemoveMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()