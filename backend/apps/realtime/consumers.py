import asyncio
import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer, AsyncWebsocketConsumer
from redis.exceptions import RedisError

from apps.accounts.models import User
from apps.tickets.selectors import accessible_tickets

from .groups import ticket_group, ticket_staff_group
from .pubsub import announcement_channel, subscriber_client

logger = logging.getLogger(__name__)

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


class AnnouncementConsumer(AsyncWebsocketConsumer):
    """Streams organization-wide announcements to connected support staff.

    Each connection holds its own raw Redis subscription (no Channels layer).
    That is simple and fine at this scale; a very large deployment would keep
    one shared subscriber per process and fan out locally instead.

    Staff only — customers are not told about internal maintenance windows.
    """

    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated or not user.organization_id or user.role not in STAFF_ROLES:
            await self.close()
            return

        self.forwarder = None
        self.redis = subscriber_client()
        self.pubsub = self.redis.pubsub()
        try:
            await self.pubsub.subscribe(announcement_channel(user.organization_id))
            # Consume Redis's subscription confirmation before accepting, so an
            # announcement published right after connect can't slip past us.
            await self.pubsub.get_message(timeout=2)
        except RedisError:
            logger.exception("Could not subscribe to announcements")
            await self._release()
            await self.close()
            return

        await self.accept()
        self.forwarder = asyncio.create_task(self._forward())

    async def _forward(self):
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    await self.send(text_data=message["data"].decode())
        except RedisError:
            logger.exception("Announcement subscription dropped")
            await self.close()

    async def disconnect(self, code):
        if getattr(self, "forwarder", None):
            self.forwarder.cancel()
            await asyncio.gather(self.forwarder, return_exceptions=True)
        if hasattr(self, "pubsub"):
            await self._release()

    async def _release(self):
        # Unsubscribe explicitly first so Redis stops counting us as a
        # recipient immediately, instead of when it notices the closed socket.
        try:
            await self.pubsub.unsubscribe()
        except RedisError:
            pass
        await self.pubsub.aclose()
        await self.redis.aclose()
