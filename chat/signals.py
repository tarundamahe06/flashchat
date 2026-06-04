from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Message


@receiver(post_save, sender=Message)
def message_post_save(sender, instance, created, **kwargs):
    """
    Signal fired after a Message is saved.
    Updates the parent conversation or group updated_at timestamp
    so that chat lists can be ordered by most recent activity.
    """
    if created:
        if instance.conversation:
            # Touch the conversation so it bubbles to top of list
            instance.conversation.__class__.objects.filter(
                pk=instance.conversation.pk
            ).update(updated_at=instance.created_at)

        elif instance.group:
            # Touch the group so it bubbles to top of list
            instance.group.__class__.objects.filter(
                pk=instance.group.pk
            ).update(updated_at=instance.created_at)