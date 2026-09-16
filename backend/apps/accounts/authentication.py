import hmac

from django.utils import timezone
from rest_framework import authentication, exceptions

from .models import APIKey


class APIKeyAuthentication(authentication.BaseAuthentication):
    keyword = "Api-Key"

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).decode("utf-8")
        if not auth_header.startswith(f"{self.keyword} "):
            return None

        raw_key = auth_header[len(self.keyword) + 1 :]
        prefix = raw_key[:8]

        try:
            api_key = APIKey.objects.select_related("organization").get(prefix=prefix)
        except APIKey.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid API key.")

        if not api_key.is_active:
            raise exceptions.AuthenticationFailed("This API key has been revoked.")

        if not hmac.compare_digest(APIKey.hash_key(raw_key), api_key.hashed_key):
            raise exceptions.AuthenticationFailed("Invalid API key.")

        owner = api_key.organization.owner
        if owner is None:
            raise exceptions.AuthenticationFailed("This organization has no owner account.")

        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=["last_used_at"])

        return (owner, api_key)
