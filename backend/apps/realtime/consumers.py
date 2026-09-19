from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.accounts.models import User
from apps.tickets.selectors import accessible_tickets

from .groups import ticket_group, ticket_staff_group

STAFF_ROLES = {User.Role.OWNER, User.Role.ADMIN, User.Role.AGENT}


class TicketConsumer(AsyncJsonWebsocketConsumer):
    """Live updates for one ticket: new comments and typing indicators.

    Access uses the same `accessible_tickets` rule as the REST API. Every
    failure — anonymous, no organization, ticket not visible — is rejected
    identically before the handshake completes, so a probe can't tell "not
    yours" from "doesn't exist".
    """

    async def connect(self):
        user = self.scope["user"]
        ticket_id = self.scope["url_route"]["kwargs"]["ticket_id"]

        if not user.is_authenticated or not user.organization_id:
            await self.close()
            return
        if not await accessible_tickets(user).filter(id=ticket_id).aexists():
            await self.close()
            return

        self.groups_joined = [ticket_group(ticket_id)]
        if user.role in STAFF_ROLES:
            self.groups_joined.append(ticket_staff_group(ticket_id))

        for group in self.groups_joined:
            await self.channel_layer.group_add(group, self.channel_name)
        self.ticket_id = ticket_id
        await self.accept()

    async def disconnect(self, code):
        for group in getattr(self, "groups_joined", []):
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # The only client -> server message is a typing notification; anything
        # else is ignored rather than trusted.
        if isinstance(content, dict) and content.get("type") == "typing":
            user = self.scope["user"]
            await self.channel_layer.group_send(
                ticket_group(self.ticket_id),
                {"type": "ticket.typing", "user_id": user.id, "username": user.username},
            )

    async def comment_created(self, event):
        await self.send_json({"type": "comment.created", "comment": event["comment"]})

    async def ticket_typing(self, event):
        if event["user_id"] == self.scope["user"].id:
            return  # don't echo someone's own typing back to them
        await self.send_json({"type": "typing", "user": event["username"]})
