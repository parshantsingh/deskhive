from apps.accounts.models import User

from .models import Ticket


def accessible_tickets(user):
    """The tickets this user is allowed to see.

    Everyone is limited to their own organization. Customers are further
    limited to tickets they filed themselves; support staff see them all.
    This is the single source of truth for that rule — the REST API and the
    WebSocket consumer both call it so they can never disagree.
    """
    tickets = Ticket.objects.filter(organization=user.organization)
    if user.role == User.Role.CUSTOMER:
        tickets = tickets.filter(requester=user)
    return tickets
