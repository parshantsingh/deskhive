import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.tickets.models import Category, Tag, Ticket

pytestmark = pytest.mark.django_db


def _make_tickets(org, requester, assignee, count):
    category, _ = Category.objects.get_or_create(organization=org, name="Billing")
    tag, _ = Tag.objects.get_or_create(organization=org, name="vip")
    for number in range(count):
        ticket = Ticket.objects.create(
            organization=org,
            requester=requester,
            assignee=assignee,
            category=category,
            subject=f"Ticket {number}",
            description="...",
        )
        ticket.tags.add(tag)


def _list_queries(user):
    client = APIClient()
    client.force_authenticate(user=user)
    with CaptureQueriesContext(connection) as queries:
        response = client.get("/api/v1/tickets/")
    assert response.status_code == 200
    return [query["sql"] for query in queries]


def test_listing_tickets_takes_three_queries_however_many_there_are(org, agent, customer):
    _make_tickets(org, customer, agent, count=2)
    few = _list_queries(agent)

    _make_tickets(org, customer, agent, count=12)
    many = _list_queries(agent)

    # pagination count, the page itself, and one prefetch for every ticket's tags.
    assert len(few) == len(many) == 3


def test_the_list_query_does_not_join_tables_the_serializer_never_reads(org, agent, customer):
    _make_tickets(org, customer, agent, count=3)

    page_query = next(
        sql for sql in _list_queries(agent) if 'FROM "tickets_ticket"' in sql and "LIMIT" in sql
    )

    # requester, assignee and category are serialized as bare ids, which already
    # sit on the ticket row; joining their tables (user rows include password
    # hashes) fetches columns nothing reads.
    assert "JOIN" not in page_query
