"""Hand-written SQL for the analytics endpoints.

Raw SQL is used here, and only here, because both queries lean on PostgreSQL
features the ORM has no expression for:

- percentile_cont(0.5) WITHIN GROUP (ORDER BY ...) for a true median. Django
  ships no percentile aggregate, and an average would be dragged around by the
  few tickets that stayed open for weeks.
- generate_series() to emit a row for every day, including days with no
  tickets. The ORM only groups rows that exist, so the gaps would have to be
  filled in Python after fetching.

The cost is that these queries are PostgreSQL-only, and table and column names
are literals that makemigrations cannot check. The tests compare every figure
against the equivalent ORM query, so a rename fails loudly instead of silently.
Values always travel as bound parameters, never string-formatted into the SQL.
"""

from datetime import timedelta
from datetime import timezone as utc_timezone

from django.db import connection
from django.utils import timezone

# Same window for both queries: the last N calendar days in UTC, today included.
DAILY_VOLUME_SQL = """
WITH days AS (
    SELECT (%(start_at)s AT TIME ZONE 'UTC')::date + n AS day
    FROM generate_series(0, %(days)s - 1) AS n
),
created AS (
    SELECT (created_at AT TIME ZONE 'UTC')::date AS day, COUNT(*) AS total
    FROM tickets_ticket
    WHERE organization_id = %(organization)s AND created_at >= %(start_at)s
    GROUP BY 1
),
resolved AS (
    SELECT (resolved_at AT TIME ZONE 'UTC')::date AS day, COUNT(*) AS total
    FROM tickets_ticket
    WHERE organization_id = %(organization)s AND resolved_at >= %(start_at)s
    GROUP BY 1
)
SELECT d.day, COALESCE(c.total, 0) AS created, COALESCE(r.total, 0) AS resolved
FROM days AS d
LEFT JOIN created AS c ON c.day = d.day
LEFT JOIN resolved AS r ON r.day = d.day
ORDER BY d.day
"""

# The cohort is tickets created inside the window and currently assigned to the
# agent. SLA compliance only considers resolved tickets that had a deadline.
AGENT_PERFORMANCE_SQL = """
SELECT
    u.id AS agent_id,
    u.username,
    COUNT(*) AS assigned,
    COUNT(*) FILTER (WHERE t.resolved_at IS NOT NULL) AS resolved,
    ROUND((
        percentile_cont(0.5) WITHIN GROUP (
            ORDER BY EXTRACT(EPOCH FROM (t.resolved_at - t.created_at)) / 3600
        ) FILTER (WHERE t.resolved_at IS NOT NULL)
    )::numeric, 2)::float8 AS median_hours_to_resolve,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE t.resolved_at <= t.due_at)
        / NULLIF(COUNT(*) FILTER (WHERE t.resolved_at IS NOT NULL AND t.due_at IS NOT NULL), 0),
        1
    )::float8 AS sla_met_pct
FROM tickets_ticket AS t
JOIN accounts_user AS u ON u.id = t.assignee_id
WHERE t.organization_id = %(organization)s AND t.created_at >= %(start_at)s
GROUP BY u.id, u.username
ORDER BY resolved DESC, u.username
"""


def window_start(days, now=None):
    """Midnight UTC of the first day in a window of `days` calendar days ending today."""
    now = (now or timezone.now()).astimezone(utc_timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=days - 1)


def _fetch_all(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        columns = [column.name for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def daily_volume(organization_id, days, now=None):
    """Tickets created and resolved per day, with a row for every day in the window."""
    params = {
        "organization": organization_id,
        "days": days,
        "start_at": window_start(days, now),
    }
    return _fetch_all(DAILY_VOLUME_SQL, params)


def agent_performance(organization_id, days, now=None):
    """Per-agent workload, median hours to resolve and SLA compliance over the window."""
    params = {"organization": organization_id, "start_at": window_start(days, now)}
    return _fetch_all(AGENT_PERFORMANCE_SQL, params)
