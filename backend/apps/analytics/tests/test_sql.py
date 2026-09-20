import statistics
from datetime import timedelta

import pytest
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.accounts.models import Organization, User
from apps.analytics import sql
from apps.tickets.models import Ticket

pytestmark = pytest.mark.django_db

HOUR = timedelta(hours=1)
DAY = timedelta(days=1)


@pytest.fixture
def now():
    # Noon UTC keeps every ticket on the day the test means, whenever it runs.
    return timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)


def _ticket(org, assignee, created, resolved_after=None, due_after=None, resolved=None):
    """Create a ticket, then write its history: created_at is auto_now_add."""
    ticket = Ticket.objects.create(
        organization=org, requester=None, assignee=assignee, subject="s", description="d"
    )
    resolved_at = created + resolved_after if resolved_after is not None else resolved
    Ticket.objects.filter(pk=ticket.pk).update(
        created_at=created,
        resolved_at=resolved_at,
        due_at=created + due_after if due_after is not None else None,
    )
    return ticket


@pytest.fixture
def history(org, agent, owner, now):
    # agent: four tickets in the window, three resolved in 2h, 4h and 10h.
    _ticket(org, agent, now - 3 * DAY, resolved_after=2 * HOUR, due_after=3 * HOUR)  # met
    _ticket(org, agent, now - 2 * DAY, resolved_after=4 * HOUR, due_after=3 * HOUR)  # missed
    _ticket(org, agent, now - 1 * DAY, resolved_after=10 * HOUR, due_after=24 * HOUR)  # met
    _ticket(org, agent, now - 1 * DAY, due_after=5 * HOUR)  # still open
    # owner: one ticket, never resolved.
    _ticket(org, owner, now - 1 * DAY)
    # Created 45 days ago: outside every window used below.
    _ticket(org, agent, now - 45 * DAY, resolved_after=1 * HOUR, due_after=2 * HOUR)
    # Created before the window but resolved inside it: counts as a resolution
    # on that day, yet is not part of the agent's created-in-window cohort.
    _ticket(org, agent, now - 40 * DAY, resolved=now - 2 * DAY)

    other_org = Organization.objects.create(name="Other", slug="other")
    stranger = User.objects.create_user(
        username="stranger", password="whatever123", organization=other_org, role="agent"
    )
    _ticket(other_org, stranger, now - 1 * DAY, resolved_after=1 * HOUR, due_after=2 * HOUR)


def test_window_starts_at_midnight_utc_n_minus_one_days_back(now):
    start = sql.window_start(7, now)

    assert start == (now - 6 * DAY).replace(hour=0)


def test_daily_volume_has_a_row_for_every_day_including_empty_ones(org, history, now):
    rows = sql.daily_volume(org.id, 7, now)

    assert len(rows) == 7
    assert [row["day"] for row in rows] == [(now - n * DAY).date() for n in range(6, -1, -1)]
    assert rows[-1] == {"day": now.date(), "created": 0, "resolved": 0}


def test_daily_volume_counts_creations_and_resolutions_per_day(org, history, now):
    by_day = {row["day"]: row for row in sql.daily_volume(org.id, 7, now)}

    assert by_day[(now - 3 * DAY).date()] == {
        "day": (now - 3 * DAY).date(),
        "created": 1,
        "resolved": 1,
    }
    # Two resolutions on this day: one ticket created that day, one created 40 days ago.
    assert by_day[(now - 2 * DAY).date()]["created"] == 1
    assert by_day[(now - 2 * DAY).date()]["resolved"] == 2
    assert by_day[(now - 1 * DAY).date()]["created"] == 3
    assert by_day[(now - 1 * DAY).date()]["resolved"] == 1


def test_daily_volume_matches_the_orm(org, history, now):
    start = sql.window_start(30, now)
    tickets = Ticket.objects.filter(organization=org)
    created = dict(
        tickets.filter(created_at__gte=start)
        .annotate(day=TruncDate("created_at"))
        .values_list("day")
        .annotate(total=Count("id"))
    )
    resolved = dict(
        tickets.filter(resolved_at__gte=start)
        .annotate(day=TruncDate("resolved_at"))
        .values_list("day")
        .annotate(total=Count("id"))
    )

    rows = sql.daily_volume(org.id, 30, now)

    assert len(rows) == 30
    for row in rows:
        assert row["created"] == created.get(row["day"], 0)
        assert row["resolved"] == resolved.get(row["day"], 0)


def test_agent_performance_figures(org, agent, history, now):
    rows = {row["username"]: row for row in sql.agent_performance(org.id, 30, now)}

    assert rows[agent.username] == {
        "agent_id": agent.id,
        "username": agent.username,
        "assigned": 4,
        "resolved": 3,
        "median_hours_to_resolve": 4.0,
        "sla_met_pct": 66.7,
    }


def test_an_agent_with_nothing_resolved_has_no_median_or_sla_figure(org, owner, history, now):
    rows = {row["username"]: row for row in sql.agent_performance(org.id, 30, now)}

    assert rows[owner.username]["assigned"] == 1
    assert rows[owner.username]["resolved"] == 0
    assert rows[owner.username]["median_hours_to_resolve"] is None
    assert rows[owner.username]["sla_met_pct"] is None


def test_agent_performance_matches_the_orm_and_plain_python(org, history, now):
    start = sql.window_start(30, now)
    cohort = Ticket.objects.filter(organization=org, created_at__gte=start, assignee__isnull=False)
    orm_counts = {
        row["assignee_id"]: row
        for row in cohort.values("assignee_id").annotate(
            assigned=Count("id"), resolved=Count("id", filter=Q(resolved_at__isnull=False))
        )
    }

    rows = sql.agent_performance(org.id, 30, now)

    assert {row["agent_id"] for row in rows} == set(orm_counts)
    for row in rows:
        mine = list(cohort.filter(assignee_id=row["agent_id"], resolved_at__isnull=False))
        hours = [(t.resolved_at - t.created_at).total_seconds() / 3600 for t in mine]
        with_deadline = [t for t in mine if t.due_at is not None]

        assert row["assigned"] == orm_counts[row["agent_id"]]["assigned"]
        assert row["resolved"] == orm_counts[row["agent_id"]]["resolved"]
        if hours:
            assert row["median_hours_to_resolve"] == pytest.approx(
                statistics.median(hours), abs=0.01
            )
            met = sum(t.resolved_at <= t.due_at for t in with_deadline)
            assert row["sla_met_pct"] == pytest.approx(100 * met / len(with_deadline), abs=0.1)


def test_other_organizations_never_appear(org, history, now):
    rows = sql.agent_performance(org.id, 30, now)

    assert "stranger" not in {row["username"] for row in rows}
    other = Organization.objects.get(slug="other")
    assert sum(row["created"] for row in sql.daily_volume(other.id, 30, now)) == 1
    # Five created inside the window; the 45 and 40 day old tickets fall outside it.
    assert sum(row["created"] for row in sql.daily_volume(org.id, 30, now)) == 5
