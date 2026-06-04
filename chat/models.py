from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Conversation(models.Model):
    """
    A direct message conversation between exactly two users.
    """
    participants = models.ManyToManyField(
        User,
        related_name="conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        usernames = ", ".join(self.participants.values_list("username", flat=True))
        return f"DM: {usernames}"

    @classmethod
    def get_or_create_dm(cls, user1, user2):
        """
        Get existing DM conversation between two users or create a new one.
        """
        # Find a conversation where both users are participants
        # and there are exactly 2 participants (DM only)
        shared = (
            cls.objects.filter(participants=user1)
            .filter(participants=user2)
        )
        for conv in shared:
            if conv.participants.count() == 2:
                return conv, False

        # No existing DM found — create one
        conv = cls.objects.create()
        conv.participants.add(user1, user2)
        return conv, True


class Group(models.Model):
    """
    A group chat with multiple members.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_groups",
    )
    members = models.ManyToManyField(
        User,
        through="GroupMembership",
        related_name="chat_groups",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Group: {self.name}"


class GroupMembership(models.Model):
    """
    Through model for Group members.
    Tracks when a user joined and their admin status.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="group_memberships",
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    is_admin = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "group")
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user.username} in {self.group.name}"


class Message(models.Model):
    """
    A message in either a DM conversation or a group chat.
    One of conversation or group must be set, not both.
    """
    # Either conversation (DM) or group — one must be set
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        null=True,
        blank=True,
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="messages",
        null=True,
        blank=True,
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    content = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        if self.conversation:
            return f"DM from {self.sender.username} at {self.created_at}"
        return f"Group msg from {self.sender.username} in {self.group.name} at {self.created_at}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.conversation and not self.group:
            raise ValidationError("Message must belong to a conversation or a group.")
        if self.conversation and self.group:
            raise ValidationError("Message cannot belong to both a conversation and a group.")

    def get_display_content(self):
        """Returns empty string if message is deleted."""
        if self.is_deleted:
            return ""
        return self.content