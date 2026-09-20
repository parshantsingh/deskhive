from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAgentOrAbove, IsOwnerOrAdmin
from apps.common.permissions import HasOrganization

from . import sql
from .serializers import OverviewQuerySerializer
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


class AnalyticsOverviewView(APIView):
    """Ticket volume per day and per-agent performance over the last `days` days.

    Owners and admins only: it exposes how each individual agent is doing.
    """

    permission_classes = [HasOrganization, IsOwnerOrAdmin]

    def get(self, request):
        query = OverviewQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        days = query.validated_data["days"]
        organization_id = request.user.organization_id

        return Response(
            {
                "days": days,
                "daily_volume": sql.daily_volume(organization_id, days),
                "agents": sql.agent_performance(organization_id, days),
            }
        )
