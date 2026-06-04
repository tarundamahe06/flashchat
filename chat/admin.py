from django.contrib import admin
from .models import Conversation, Group, GroupMembership, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ["sender", "content", "created_at", "is_read", "is_deleted"]
    can_delete = False


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0
    readonly_fields = ["joined_at"]


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "get_participants", "created_at", "updated_at"]
    readonly_fields = ["created_at", "updated_at"]
    search_fields = ["participants__username"]
    inlines = [MessageInline]

    def get_participants(self, obj):
        return ", ".join(obj.participants.values_list("username", flat=True))
    get_participants.short_description = "Participants"


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "creator", "is_active", "created_at", "updated_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "creator__username"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [GroupMembershipInline, MessageInline]


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "group", "is_admin", "joined_at"]
    list_filter = ["is_admin"]
    search_fields = ["user__username", "group__name"]
    readonly_fields = ["joined_at"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "sender", "get_chat", "short_content", "created_at", "is_read", "is_deleted"]
    list_filter = ["is_read", "is_deleted", "created_at"]
    search_fields = ["sender__username", "content"]
    readonly_fields = ["created_at"]

    def get_chat(self, obj):
        if obj.conversation:
            return f"DM #{obj.conversation.id}"
        return f"Group: {obj.group.name}"
    get_chat.short_description = "Chat"

    def short_content(self, obj):
        if obj.is_deleted:
            return "[deleted]"
        return obj.content[:60] + "..." if len(obj.content) > 60 else obj.content
    short_content.short_description = "Content"