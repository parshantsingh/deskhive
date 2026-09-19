from urllib.parse import parse_qs

from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


class JWTAuthMiddleware(BaseMiddleware):
    """Authenticates a WebSocket connection from `?token=<access token>`.

    Browsers cannot set an Authorization header on a WebSocket, so the access
    token travels in the query string. The trade-off: URLs end up in server
    and proxy logs. Access tokens are short-lived (minutes), which limits the
    exposure; a one-time ticket exchange would remove it entirely.

    A missing, expired or forged token yields an AnonymousUser rather than an
    error — the consumer decides what an anonymous user may do (nothing).
    """

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        scope["user"] = await self._get_user(scope)
        return await super().__call__(scope, receive, send)

    async def _get_user(self, scope):
        query = parse_qs(scope.get("query_string", b"").decode())
        token = (query.get("token") or [None])[0]
        if not token:
            return AnonymousUser()

        try:
            user_id = AccessToken(token)["user_id"]
            return await User.objects.select_related("organization").aget(pk=user_id)
        except (TokenError, User.DoesNotExist, KeyError, ValueError):
            return AnonymousUser()
