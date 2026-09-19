import pytest
from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import Organization, User
from apps.realtime.middleware import JWTAuthMiddleware
from apps.realtime.routing import websocket_urlpatterns
from apps.tickets.models import Ticket

application = JWTAuthMiddleware(URLRouter(websocket_urlpatterns))

pytestmark = [pytest.mark.asyncio, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def ticket(org, customer):
    return Ticket.objects.create(
        organization=org, requester=customer, subject="Help", description="..."
    )


async def _connect(user, ticket, token=None):
    if token is None:
        token = str(AccessToken.for_user(user)) if user else ""
    query = f"?token={token}" if token else ""
    communicator = WebsocketCommunicator(application, f"/ws/tickets/{ticket.id}/{query}")
    connected, _ = await communicator.connect()
    return communicator, connected


def _post_comment(user, ticket, body, internal=False):
    client = APIClient()
    client.force_authenticate(user=user)
    return client.post(
        f"/api/v1/tickets/{ticket.id}/comments/",
        {"body": body, "is_internal_note": internal},
        format="json",
    )


async def test_customer_can_connect_to_their_own_ticket(ticket, customer):
    communicator, connected = await _connect(customer, ticket)

    assert connected
    await communicator.disconnect()


async def test_anonymous_connection_is_rejected(ticket):
    _, connected = await _connect(None, ticket)

    assert not connected


async def test_forged_token_is_rejected(ticket):
    _, connected = await _connect(None, ticket, token="not-a-real-token")

    assert not connected


async def test_customer_cannot_watch_someone_elses_ticket(org, ticket):
    other = await sync_to_async(User.objects.create_user)(
        username="cust2", password="whatever123", organization=org, role=User.Role.CUSTOMER
    )

    _, connected = await _connect(other, ticket)

    assert not connected


async def test_other_organizations_cannot_connect(ticket):
    def make_outsider():
        other_org = Organization.objects.create(name="Other", slug="other")
        return User.objects.create_user(
            username="outsider", password="whatever123", organization=other_org, role="owner"
        )

    outsider = await sync_to_async(make_outsider)()

    _, connected = await _connect(outsider, ticket)

    assert not connected


async def test_new_comment_is_pushed_to_connected_customer(ticket, customer, agent):
    communicator, _ = await _connect(customer, ticket)

    await sync_to_async(_post_comment)(agent, ticket, "Looking into it")
    message = await communicator.receive_json_from()

    assert message["type"] == "comment.created"
    assert message["comment"]["body"] == "Looking into it"
    await communicator.disconnect()


async def test_internal_note_reaches_staff_but_never_the_customer(ticket, customer, agent):
    customer_socket, _ = await _connect(customer, ticket)
    agent_socket, _ = await _connect(agent, ticket)

    await sync_to_async(_post_comment)(agent, ticket, "customer seems confused", internal=True)

    staff_message = await agent_socket.receive_json_from()
    assert staff_message["comment"]["body"] == "customer seems confused"
    assert await customer_socket.receive_nothing(timeout=0.3)

    await customer_socket.disconnect()
    await agent_socket.disconnect()


async def test_public_comment_reaches_staff_exactly_once(ticket, customer, agent):
    agent_socket, _ = await _connect(agent, ticket)

    await sync_to_async(_post_comment)(customer, ticket, "Any update?")

    assert (await agent_socket.receive_json_from())["comment"]["body"] == "Any update?"
    assert await agent_socket.receive_nothing(timeout=0.3)
    await agent_socket.disconnect()


async def test_typing_is_shown_to_the_other_party_but_not_echoed(ticket, customer, agent):
    customer_socket, _ = await _connect(customer, ticket)
    agent_socket, _ = await _connect(agent, ticket)

    await customer_socket.send_json_to({"type": "typing"})

    assert await agent_socket.receive_json_from() == {"type": "typing", "user": "cust1"}
    assert await customer_socket.receive_nothing(timeout=0.3)

    await customer_socket.disconnect()
    await agent_socket.disconnect()


async def test_unknown_client_messages_are_ignored(ticket, customer):
    communicator, _ = await _connect(customer, ticket)

    await communicator.send_json_to({"type": "delete_everything"})

    assert await communicator.receive_nothing(timeout=0.3)
    await communicator.disconnect()
