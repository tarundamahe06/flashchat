from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_key):
    """
    Validate the JWT access token and return the corresponding user.
    Returns AnonymousUser if token is invalid or user does not exist.
    """
    try:
        token = AccessToken(token_key)
        user_id = token["user_id"]
        user = User.objects.get(pk=user_id)
        return user
    except (InvalidToken, TokenError, User.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware that authenticates WebSocket connections using JWT.

    The token can be passed in two ways:
    1. Query parameter: ws://host/ws/chat/1/?token=<access_token>
    2. Will be extended to support headers in future if needed.
    """

    async def __call__(self, scope, receive, send):
        # Parse query string to extract token
        query_string = scope.get("query_string", b"").decode("utf-8")
        token_key = None

        # Extract token from query params: ?token=<jwt>
        for param in query_string.split("&"):
            if param.startswith("token="):
                token_key = param.split("=", 1)[1]
                break

        if token_key:
            scope["user"] = await get_user_from_token(token_key)
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)