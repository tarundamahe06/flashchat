from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """
    Signal fired after a User is saved.
    Currently used for any post-registration setup.
    Can be extended later for things like welcome notifications.
    """
    if created:
        # Placeholder for any logic needed when a new user registers
        # e.g. sending a welcome email, creating a default profile, etc.
        pass