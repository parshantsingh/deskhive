from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Organization
from apps.analytics.services import build_dashboard_summary
from apps.tickets.models import Ticket

pytestmark = pytest.mark.django_db


def _ticket(org, requester, **fields):
    return Ticket.objects.create(
        organization=org, requester=requester, subject="s", description="d", **fields
    )


def _backdate(ticket, **fields):
    # created_at is auto_now_add, so history has to be written with an UPDATE.
    Ticket.objects.filter(pk=ticket.pk).update(**fields)


@pytest.fixture
def populated(org, agent, customer):
    now = timezone.now()
    past, future = now - timedelta(hours=1), now + timedelta(hours=1)

    _ticket(org, customer, status="open", priority="urgent", due_at=past)
    _ticket(org, customer, status="pending", priority="medium", assignee=agent, due_at=future)
    # Finished work: unassigned and past due, yet it must not count as workload.
    _ticket(org, customer, status="resolved", priority="urgent", due_at=past, resolved_at=now)
    old = _ticket(org, customer, status="closed", priority="low", assignee=agent)
    _backdate(old, created_at=now - timedelta(days=30), resolved_at=now - timedelta(days=20))

    other_org = Organization.objects.create(name="Other", slug="other")
    _ticket(other_org, None, status="open", priority="urgent", due_at=past)


def test_counts_tickets_by_status(org, populated):
    summary = build_dashboard_summary(org.id)

    assert summary["by_status"] == {"open": 1, "pending": 1, "resolved": 1, "closed": 1}


def test_workload_counts_only_tickets_that_still_need_work(org, populated):
    summary = build_dashboard_summary(org.id)

    assert summary["open_work"] == {"unassigned": 1, "overdue": 1, "urgent": 1}


def test_recent_activity_only_looks_back_seven_days(org, populated):
    summary = build_dashboard_summary(org.id)

    # The closed ticket was created 30 days ago and resolved 20 days ago.
    assert summary["last_7_days"] == {"created": 3, "resolved": 1}


def test_other_organizations_tickets_are_never_counted(org, populated):
    other = Organization.objects.get(slug="other")

    assert sum(build_dashboard_summary(org.id)["by_status"].values()) == 4
    assert sum(build_dashboard_summary(other.id)["by_status"].values()) == 1


def test_an_empty_organization_is_all_zeros(org):
    summary = build_dashboard_summary(org.id)

    assert summary["by_status"] == {"open": 0, "pending": 0, "resolved": 0, "closed": 0}
    assert summary["open_work"] == {"unassigned": 0, "overdue": 0, "urgent": 0}
    assert summary["last_7_days"] == {"created": 0, "resolved": 0}


def test_the_whole_summary_is_one_query(org, populated, django_assert_num_queries):
    with django_assert_num_queries(1):
        build_dashboard_summary(org.id)
