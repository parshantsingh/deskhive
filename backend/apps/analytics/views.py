from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAgentOrAbove
from apps.common.permissions import HasOrganization

from .services import get_dashboard_summary


class DashboardSummaryView(APIView):
    """Headline ticket numbers for the caller's organization (staff only).

    The X-Cache header says whether the figures came from Redis or were just
    rebuilt, which makes the cache observable from the outside.
    """

    permission_classes = [HasOrganization, IsAgentOrAbove]

    def get(self, request):
        summary, hit = get_dashboard_summary(request.user.organization_id)
        return Response(summary, headers={"X-Cache": "HIT" if hit else "MISS"})
