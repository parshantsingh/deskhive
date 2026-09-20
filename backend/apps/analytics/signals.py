from functools import partial

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.tickets.models import Ticket

from .services import invalidate_dashboard_summary


@receiver(
    [post_save, post_delete],
    sender=Ticket,
    dispatch_uid="analytics.invalidate_dashboard_summary",
)
def invalidate_summary_when_a_ticket_changes(sender, instance, **kwargs):
    # Only after the transaction commits. Deleting the key earlier lets a request
    # that arrives before the commit rebuild the entry from the old rows and
    # cache it, and the stale figures then outlive the write until the TTL.
    #
    # This only sees writes made through model save()/delete(). QuerySet.update()
    # and bulk_* skip signals; the TTL is the backstop for any that get added.
    transaction.on_commit(partial(invalidate_dashboard_summary, instance.organization_id))
