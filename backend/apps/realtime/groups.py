"""Channel-layer group names for a ticket's live viewers.

Two groups per ticket, because one group cannot express "everyone except
customers":

- everyone group: every allowed viewer (customer and staff). Public comments.
- staff group: support staff only. Internal notes.

Staff join both, so a public comment reaches them through the everyone group
and an internal note through the staff group — each exactly once.
"""


def ticket_group(ticket_id):
    return f"ticket.{ticket_id}"


def ticket_staff_group(ticket_id):
    return f"ticket.{ticket_id}.staff"
