import logging

from celery import shared_task
from django.utils import timezone

from apps.notifications.tasks import send_sla_breach_notification

from .models import Ticket

logger = logging.getLogger(__name__)


@shared_task
def check_sla_breaches():
    """Run periodically by Celery Beat.

    Finds tickets whose due_at has passed, are still open work (not
    resolved/closed), and haven't already been flagged — marks each one
    breached exactly once and queues a notification for it.
    """
    overdue_tickets = Ticket.objects.filter(
        due_at__lt=timezone.now(),
        sla_breached_at__isnull=True,
        status__in=[Ticket.Status.OPEN, Ticket.Status.PENDING],
    )

    breached_ids = []
    for ticket in overdue_tickets:
        ticket.sla_breached_at = timezone.now()
        ticket.save(update_fields=["sla_breached_at"])
        breached_ids.append(str(ticket.id))

    for ticket_id in breached_ids:
        try:
            send_sla_breach_notification.delay(ticket_id)
        except Exception:
            logger.exception("Failed to enqueue SLA breach notification for ticket %s", ticket_id)

    if breached_ids:
        logger.info("SLA breach scan flagged %d ticket(s)", len(breached_ids))

    return len(breached_ids)
