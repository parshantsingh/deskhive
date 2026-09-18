import datetime
import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from apps.accounts.models import Organization
from apps.tickets.models import Comment, Ticket

logger = logging.getLogger(__name__)
User = get_user_model()


def _staff_recipients(ticket):
    """Who on the support side should hear about this ticket.

    The assigned agent if there is one; otherwise every owner/admin in the
    organization, since an unassigned ticket is everyone's responsibility
    until someone picks it up.
    """
    if ticket.assignee and ticket.assignee.email:
        return [ticket.assignee.email]
    return list(
        User.objects.filter(
            organization=ticket.organization,
            role__in=[User.Role.OWNER, User.Role.ADMIN],
        )
        .exclude(email="")
        .values_list("email", flat=True)
    )


@shared_task
def send_ticket_created_notifications(ticket_id):
    try:
        ticket = Ticket.objects.select_related("organization", "requester", "assignee").get(
            id=ticket_id
        )
    except Ticket.DoesNotExist:
        logger.warning("Ticket %s no longer exists; skipping notification", ticket_id)
        return

    if ticket.requester and ticket.requester.email:
        send_mail(
            subject=f"We've received your ticket: {ticket.subject}",
            message=(
                f"Hi {ticket.requester.username},\n\n"
                f'Your ticket "{ticket.subject}" has been received and our '
                "team will get back to you soon."
            ),
            from_email=None,
            recipient_list=[ticket.requester.email],
        )

    staff_emails = _staff_recipients(ticket)
    if staff_emails:
        send_mail(
            subject=f"New ticket: {ticket.subject}",
            message=f"A new {ticket.priority}-priority ticket was filed:\n\n{ticket.description}",
            from_email=None,
            recipient_list=staff_emails,
        )


@shared_task
def send_new_comment_notification(comment_id):
    try:
        comment = Comment.objects.select_related(
            "ticket",
            "ticket__organization",
            "ticket__requester",
            "ticket__assignee",
            "author",
        ).get(id=comment_id)
    except Comment.DoesNotExist:
        logger.warning("Comment %s no longer exists; skipping notification", comment_id)
        return

    if comment.is_internal_note:
        # Internal notes are staff-only by design (see apps.tickets); never
        # worth an email, and definitely never to the customer.
        return

    ticket = comment.ticket
    author = comment.author

    if author and author.role == User.Role.CUSTOMER:
        recipients = _staff_recipients(ticket)
    elif ticket.requester and ticket.requester.email:
        recipients = [ticket.requester.email]
    else:
        recipients = []

    if not recipients:
        return

    send_mail(
        subject=f"New reply on: {ticket.subject}",
        message=comment.body,
        from_email=None,
        recipient_list=recipients,
    )


@shared_task
def send_sla_breach_notification(ticket_id):
    try:
        ticket = Ticket.objects.select_related("organization", "assignee").get(id=ticket_id)
    except Ticket.DoesNotExist:
        logger.warning("Ticket %s no longer exists; skipping breach notification", ticket_id)
        return

    recipients = _staff_recipients(ticket)
    if not recipients:
        return

    send_mail(
        subject=f"SLA breached: {ticket.subject}",
        message=(
            f'Ticket "{ticket.subject}" ({ticket.priority} priority) missed its SLA '
            f"deadline of {ticket.due_at:%Y-%m-%d %H:%M} UTC."
        ),
        from_email=None,
        recipient_list=recipients,
    )


@shared_task
def send_weekly_digest():
    """Run once a week by Celery Beat — one summary email per organization."""
    since = timezone.now() - datetime.timedelta(days=7)

    for organization in Organization.objects.all():
        owner_emails = list(
            User.objects.filter(organization=organization, role=User.Role.OWNER)
            .exclude(email="")
            .values_list("email", flat=True)
        )
        if not owner_emails:
            continue

        org_tickets = Ticket.objects.filter(organization=organization)
        created_count = org_tickets.filter(created_at__gte=since).count()
        resolved_count = org_tickets.filter(resolved_at__gte=since).count()
        open_count = org_tickets.filter(
            status__in=[Ticket.Status.OPEN, Ticket.Status.PENDING]
        ).count()
        breached_count = org_tickets.filter(sla_breached_at__gte=since).count()

        send_mail(
            subject=f"Weekly summary for {organization.name}",
            message=(
                "This week:\n"
                f"- New tickets: {created_count}\n"
                f"- Resolved tickets: {resolved_count}\n"
                f"- Currently open: {open_count}\n"
                f"- SLA breaches: {breached_count}\n"
            ),
            from_email=None,
            recipient_list=owner_emails,
        )
