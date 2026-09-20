import asyncio

import pytest
from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import Organization, User
from apps.realtime.middleware import JWTAuthMiddleware
from apps.realtime.pubsub import publish_announcement
from apps.realtime.routing import websocket_urlpatterns

# These tests run against the real Redis (CI provides one): the feature under
# test is raw Redis Pub/Sub, so the in-memory channel layer would prove nothing.
application = JWTAuthMiddleware(URLRouter(websocket_urlpatterns))

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


async def _connect(user):
    token = str(AccessToken.for_user(user)) if user else ""
    communicator = WebsocketCommunicator(application, f"/ws/announcements/?token={token}")
    connected, _ = await communicator.connect()
    return communicator, connected


def _announce(user, message):
    client = APIClient()
    client.force_authenticate(user=user)
    return client.post("/api/v1/announcements/", {"message": message}, format="json")


async def test_connected_agent_receives_the_announcement(owner, agent):
    agent_socket, connected = await _connect(agent)
    assert connected

    response = await sync_to_async(_announce)(owner, "Maintenance at 22:00")
    message = await agent_socket.receive_json_from()

    assert response.status_code == 202
    assert response.data == {"delivered_to": 1}
    assert message["type"] == "announcement"
    assert message["message"] == "Maintenance at 22:00"
    assert message["sent_by"] == "owner1"
    await agent_socket.disconnect()


async def test_every_connected_staff_member_receives_it(owner, agent):
    owner_socket, _ = await _connect(owner)
    agent_socket, _ = await _connect(agent)

    response = await sync_to_async(_announce)(owner, "Standup moved")

    assert response.data == {"delivered_to": 2}
    assert (await owner_socket.receive_json_from())["message"] == "Standup moved"
    assert (await agent_socket.receive_json_from())["message"] == "Standup moved"
    await owner_socket.disconnect()
    await agent_socket.disconnect()


async def test_customers_cannot_subscribe(customer):
    _, connected = await _connect(customer)

    assert not connected


async def test_anonymous_users_cannot_subscribe():
    _, connected = await _connect(None)

    assert not connected


async def test_other_organizations_never_receive_it(owner):
    def make_outsider():
        other_org = Organization.objects.create(name="Other", slug="other")
        return User.objects.create_user(
            username="outsider", password="whatever123", organization=other_org, role="owner"
        )

    outsider = await sync_to_async(make_outsider)()
    outsider_socket, _ = await _connect(outsider)

    response = await sync_to_async(_announce)(owner, "Ours only")

    assert response.data == {"delivered_to": 0}
    assert await outsider_socket.receive_nothing(timeout=0.5)
    await outsider_socket.disconnect()


async def test_announcing_with_nobody_online_reports_zero(owner):
    response = await sync_to_async(_announce)(owner, "Anyone there?")

    assert response.status_code == 202
    assert response.data == {"delivered_to": 0}


async def test_a_disconnected_agent_stops_being_counted(org, agent):
    agent_socket, _ = await _connect(agent)
    await agent_socket.disconnect()

    # Unsubscribe is explicit, but give Redis a moment rather than flake.
    for _ in range(20):
        if await sync_to_async(publish_announcement)(org.id, "probe", "test") == 0:
            break
        await asyncio.sleep(0.1)

    assert await sync_to_async(publish_announcement)(org.id, "probe", "test") == 0
