import uuid

import pytest
from django.core import mail

from apps.notifications.tasks import (
    send_new_comment_notification,
    send_ticket_created_notifications,
)
from apps.tickets.models import Comment, Ticket


@pytest.mark.django_db
def test_ticket_created_notifies_requester_and_assigned_agent(org, owner, agent, customer):
    ticket = Ticket.objects.create(
        organization=org,
        requester=customer,
        assignee=agent,
        subject="Help",
        description="...",
    )

    send_ticket_created_notifications(str(ticket.id))

    assert len(mail.outbox) == 2
    recipients = {email for message in mail.outbox for email in message.to}
    assert recipients == {"cust1@acme.test", "agent1@acme.test"}


@pytest.mark.django_db
def test_ticket_created_notifies_owners_when_unassigned(org, owner, customer):
    ticket = Ticket.objects.create(
        organization=org, requester=customer, subject="Help", description="..."
    )

    send_ticket_created_notifications(str(ticket.id))

    recipients = {email for message in mail.outbox for email in message.to}
    assert "owner1@acme.test" in recipients


@pytest.mark.django_db
def test_ticket_created_task_handles_missing_ticket_gracefully():
    send_ticket_created_notifications(str(uuid.uuid4()))

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_internal_note_never_sends_an_email(org, owner, customer):
    ticket = Ticket.objects.create(
        organization=org, requester=customer, subject="Help", description="..."
    )
    comment = Comment.objects.create(
        organization=org, ticket=ticket, author=owner, body="internal only", is_internal_note=True
    )

    send_new_comment_notification(str(comment.id))

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_customer_comment_notifies_staff(org, agent, customer):
    ticket = Ticket.objects.create(
        organization=org, requester=customer, assignee=agent, subject="Help", description="..."
    )
    comment = Comment.objects.create(
        organization=org, ticket=ticket, author=customer, body="Any update?"
    )

    send_new_comment_notification(str(comment.id))

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["agent1@acme.test"]


@pytest.mark.django_db
def test_staff_comment_notifies_customer(org, agent, customer):
    ticket = Ticket.objects.create(
        organization=org, requester=customer, assignee=agent, subject="Help", description="..."
    )
    comment = Comment.objects.create(
        organization=org, ticket=ticket, author=agent, body="Looking into it"
    )

    send_new_comment_notification(str(comment.id))

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["cust1@acme.test"]


@pytest.mark.django_db
def test_comment_task_handles_missing_comment_gracefully():
    send_new_comment_notification(str(uuid.uuid4()))

    assert len(mail.outbox) == 0
