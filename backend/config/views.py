import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response

logger = logging.getLogger(__name__)


@api_view(["GET"])
def health_check(request):
    logger.info("health check requested")
    return Response({"status": "ok"})
