import pytest

from apps.accounts.models import Organization
from apps.analytics.services import get_dashboard_summary
from apps.tickets.models import Ticket

pytestmark = pytest.mark.django_db


def _new_ticket(org, requester, **fields):
    return Ticket.objects.create(
        organization=org, requester=requester, subject="s", description="d", **fields
    )


def test_the_second_read_is_served_from_cache(org):
    _, first_hit = get_dashboard_summary(org.id)
    _, second_hit = get_dashboard_summary(org.id)

    assert (first_hit, second_hit) == (False, True)


def test_creating_a_ticket_refreshes_the_summary(org, customer, django_capture_on_commit_callbacks):
    get_dashboard_summary(org.id)

    with django_capture_on_commit_callbacks(execute=True):
        _new_ticket(org, customer, status="open")
    summary, hit = get_dashboard_summary(org.id)

    assert hit is False
    assert summary["by_status"]["open"] == 1


def test_changing_a_status_refreshes_the_summary(org, customer, django_capture_on_commit_callbacks):
    ticket = _new_ticket(org, customer, status="open")
    get_dashboard_summary(org.id)

    with django_capture_on_commit_callbacks(execute=True):
        ticket.status = Ticket.Status.RESOLVED
        ticket.save()
    summary, hit = get_dashboard_summary(org.id)

    assert hit is False
    assert summary["by_status"]["open"] == 0
    assert summary["by_status"]["resolved"] == 1


def test_deleting_a_ticket_refreshes_the_summary(org, customer, django_capture_on_commit_callbacks):
    ticket = _new_ticket(org, customer, status="open")
    get_dashboard_summary(org.id)

    with django_capture_on_commit_callbacks(execute=True):
        ticket.delete()
    summary, hit = get_dashboard_summary(org.id)

    assert hit is False
    assert summary["by_status"]["open"] == 0


def test_the_entry_survives_until_the_transaction_commits(
    org, customer, django_capture_on_commit_callbacks
):
    get_dashboard_summary(org.id)

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        _new_ticket(org, customer, status="open")
        _, hit_before_commit = get_dashboard_summary(org.id)

    # Nothing was dropped yet: a reader arriving now would otherwise rebuild the
    # entry from rows that don't include this ticket and cache the stale numbers.
    assert hit_before_commit is True
    assert len(callbacks) == 1

    for callback in callbacks:
        callback()
    assert get_dashboard_summary(org.id)[1] is False


def test_another_organizations_changes_leave_this_cache_alone(
    org, customer, django_capture_on_commit_callbacks
):
    other = Organization.objects.create(name="Other", slug="other")
    get_dashboard_summary(org.id)

    with django_capture_on_commit_callbacks(execute=True):
        _new_ticket(other, None, status="open")

    assert get_dashboard_summary(org.id)[1] is True
