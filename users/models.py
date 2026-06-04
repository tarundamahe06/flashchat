from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    full_name = models.CharField(max_length=150)
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)
    bio = models.TextField(blank=True, default="")

    # Users this user is following
    following = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="followers",
        blank=True,
    )

    # Users this user has blocked
    blocked = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="blocked_by",
        blank=True,
    )

    # Use email for login instead of username
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email", "full_name"]

    def __str__(self):
        return self.username

    def is_blocking(self, other_user):
        """Returns True if this user has blocked other_user."""
        return self.blocked.filter(pk=other_user.pk).exists()

    def is_blocked_by(self, other_user):
        """Returns True if other_user has blocked this user."""
        return other_user.blocked.filter(pk=self.pk).exists()

    def can_message(self, other_user):
        """
        DM messaging is allowed only if neither user has blocked the other.
        Block has no effect in group chats.
        """
        return not self.is_blocking(other_user) and not self.is_blocked_by(other_user)

    def is_following(self, other_user):
        """Returns True if this user is following other_user."""
        return self.following.filter(pk=other_user.pk).exists()