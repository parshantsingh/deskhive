from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.common.cache import get_or_compute, invalidate
from apps.tickets.models import Priority, Ticket

# "Still needs work": tickets in these states count towards workload figures.
ACTIVE_STATUSES = [Ticket.Status.OPEN, Ticket.Status.PENDING]

# Ticket writes invalidate the entry (see signals.py), so this only bounds how
# stale the figures that depend on the clock can get: "overdue" changes as time
# passes with no write to react to.
SUMMARY_TTL_SECONDS = 300


def build_dashboard_summary(organization_id):
    """Headline numbers for one organization, computed in a single query.

    Every figure is a COUNT(*) FILTER (WHERE ...) over the same rows, so
    Postgres makes one pass over the organization's tickets instead of one
    query per number.
    """
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    active = Q(status__in=ACTIVE_STATUSES)

    counts = Ticket.objects.filter(organization_id=organization_id).aggregate(
        open=Count("id", filter=Q(status=Ticket.Status.OPEN)),
        pending=Count("id", filter=Q(status=Ticket.Status.PENDING)),
        resolved=Count("id", filter=Q(status=Ticket.Status.RESOLVED)),
        closed=Count("id", filter=Q(status=Ticket.Status.CLOSED)),
        unassigned=Count("id", filter=active & Q(assignee__isnull=True)),
        overdue=Count("id", filter=active & Q(due_at__lt=now)),
        urgent=Count("id", filter=active & Q(priority=Priority.URGENT)),
        created=Count("id", filter=Q(created_at__gte=week_ago)),
        resolved_recently=Count("id", filter=Q(resolved_at__gte=week_ago)),
    )

    return {
        "generated_at": now.isoformat(),
        "by_status": {name: counts[name] for name in ("open", "pending", "resolved", "closed")},
        "open_work": {name: counts[name] for name in ("unassigned", "overdue", "urgent")},
        "last_7_days": {"created": counts["created"], "resolved": counts["resolved_recently"]},
    }


def summary_cache_key(organization_id):
    # The version segment lets a change to the payload's shape roll out without
    # serving old-shaped entries that are still sitting in Redis.
    return f"dashboard:summary:v1:{organization_id}"


def get_dashboard_summary(organization_id):
    """Cache-aside read. Returns (summary, hit)."""
    return get_or_compute(
        summary_cache_key(organization_id),
        lambda: build_dashboard_summary(organization_id),
        SUMMARY_TTL_SECONDS,
    )


def invalidate_dashboard_summary(organization_id):
    invalidate(summary_cache_key(organization_id))
