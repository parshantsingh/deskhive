import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .groups import ticket_group, ticket_staff_group

logger = logging.getLogger(__name__)


def broadcast_comment(ticket_id, comment_data, is_internal_note):
    """Push a new comment to everyone currently watching the ticket.

    Internal notes go only to the staff group; public comments go to the
    everyone group (which staff are in too). Never raises: the comment is
    already saved, and losing a live push is far better than failing the
    request that created it — clients still see it on their next fetch.
    """
    group = ticket_staff_group(ticket_id) if is_internal_note else ticket_group(ticket_id)
    try:
        async_to_sync(get_channel_layer().group_send)(
            group, {"type": "comment.created", "comment": comment_data}
        )
    except Exception:
        logger.exception("Failed to broadcast comment on ticket %s", ticket_id)
