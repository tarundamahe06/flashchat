from django.urls import path
from .views import (
    # DM Views
    ConversationListView,
    GetOrCreateConversationView,
    ConversationMessageListView,

    # Group Views
    GroupListCreateView,
    GroupDetailView,
    GroupUpdateView,
    GroupDeleteView,
    GroupLeaveView,
    GroupAddMembersView,
    GroupRemoveMemberView,
    GroupMessageListView,

    # Message Views
    DeleteMessageView,
)

urlpatterns = [
    # ─────────────────────────────────────────────
    # DM Conversations
    # ─────────────────────────────────────────────

    # List all DM conversations
    path("conversations/", ConversationListView.as_view(), name="conversation_list"),

    # Get or create a DM conversation
    path("conversations/open/", GetOrCreateConversationView.as_view(), name="conversation_open"),

    # Load DM message history
    path("conversations/<int:conversation_id>/messages/", ConversationMessageListView.as_view(), name="conversation_messages"),

    # ─────────────────────────────────────────────
    # Groups
    # ─────────────────────────────────────────────

    # List groups / Create group
    path("groups/", GroupListCreateView.as_view(), name="group_list_create"),

    # Group detail
    path("groups/<int:group_id>/", GroupDetailView.as_view(), name="group_detail"),

    # Update group name/description (admin only)
    path("groups/<int:group_id>/update/", GroupUpdateView.as_view(), name="group_update"),

    # Delete group (creator only)
    path("groups/<int:group_id>/delete/", GroupDeleteView.as_view(), name="group_delete"),

    # Leave group
    path("groups/<int:group_id>/leave/", GroupLeaveView.as_view(), name="group_leave"),

    # Add members (admin only)
    path("groups/<int:group_id>/members/add/", GroupAddMembersView.as_view(), name="group_add_members"),

    # Remove member (admin only)
    path("groups/<int:group_id>/members/remove/", GroupRemoveMemberView.as_view(), name="group_remove_member"),

    # Load group message history
    path("groups/<int:group_id>/messages/", GroupMessageListView.as_view(), name="group_messages"),

    # ─────────────────────────────────────────────
    # Messages
    # ─────────────────────────────────────────────

    # Soft delete a message (sender only)
    path("messages/<int:message_id>/delete/", DeleteMessageView.as_view(), name="message_delete"),
]