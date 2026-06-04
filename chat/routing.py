# from django.urls import re_path
# from .consumers import DMConsumer, GroupConsumer

# websocket_urlpatterns = [
#     # DM WebSocket connection
#     # Usage: ws://host/ws/dm/<conversation_id>/?token=<jwt>
#     re_path(r"^ws/dm/(?P<conversation_id>\d+)/$", DMConsumer.as_asgi()),

#     # Group WebSocket connection
#     # Usage: ws://host/ws/group/<group_id>/?token=<jwt>
#     re_path(r"^ws/group/(?P<group_id>\d+)/$", GroupConsumer.as_asgi()),
# ]









from django.urls import re_path
from .consumers import DMConsumer, GroupConsumer, NotificationConsumer

websocket_urlpatterns = [
    # DM WebSocket connection
    # Usage: ws://host/ws/dm/<conversation_id>/?token=<jwt>
    re_path(r"^ws/dm/(?P<conversation_id>\d+)/$", DMConsumer.as_asgi()),

    # Group WebSocket connection
    # Usage: ws://host/ws/group/<group_id>/?token=<jwt>
    re_path(r"^ws/group/(?P<group_id>\d+)/$", GroupConsumer.as_asgi()),

    # Notification WebSocket connection
    # Usage: ws://host/ws/notifications/<user_id>/?token=<jwt>
    re_path(r"^ws/notifications/(?P<user_id>\d+)/$", NotificationConsumer.as_asgi()),
]