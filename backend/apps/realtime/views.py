import logging

from redis.exceptions import RedisError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsOwnerOrAdmin
from apps.common.permissions import HasOrganization

from .pubsub import publish_announcement
from .serializers import AnnouncementSerializer

logger = logging.getLogger(__name__)


class AnnouncementView(APIView):
    """Send a message to every support agent currently connected.

    Owner/admin only. Responds 202 with how many connected agents received it
    (zero is a valid answer: Pub/Sub only reaches whoever is online right now).
    """

    permission_classes = [HasOrganization, IsOwnerOrAdmin]

    def post(self, request):
        serializer = AnnouncementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            delivered_to = publish_announcement(
                request.user.organization_id,
                serializer.validated_data["message"],
                request.user.username,
            )
        except RedisError:
            # Unlike a comment's live push, the publish is the whole point of
            # this request, so a failure must be reported, not swallowed.
            logger.exception("Announcement publish failed")
            return Response(
                {"detail": "Announcement could not be sent. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        logger.info(
            "Announcement from %s reached %d connected agent(s)",
            request.user.username,
            delivered_to,
        )
        return Response({"delivered_to": delivered_to}, status=status.HTTP_202_ACCEPTED)
