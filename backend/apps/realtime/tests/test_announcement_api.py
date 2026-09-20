import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def _announce(user, payload):
    client = APIClient()
    if user:
        client.force_authenticate(user=user)
    return client.post("/api/v1/announcements/", payload, format="json")


def test_owner_can_announce(owner):
    response = _announce(owner, {"message": "Maintenance tonight"})

    assert response.status_code == 202
    assert response.data == {"delivered_to": 0}


@pytest.mark.parametrize("who", ["agent", "customer"])
def test_only_owners_and_admins_can_announce(who, request):
    user = request.getfixturevalue(who)

    assert _announce(user, {"message": "hi"}).status_code == 403


def test_anonymous_users_cannot_announce():
    assert _announce(None, {"message": "hi"}).status_code == 401


@pytest.mark.parametrize("payload", [{}, {"message": ""}, {"message": "x" * 501}])
def test_invalid_messages_are_rejected(owner, payload):
    response = _announce(owner, payload)

    assert response.status_code == 400
    assert "message" in response.data


def test_a_redis_outage_is_reported_not_swallowed(owner, monkeypatch):
    def broken_publish(*args, **kwargs):
        raise RedisConnectionError("redis is down")

    monkeypatch.setattr("apps.realtime.views.publish_announcement", broken_publish)

    response = _announce(owner, {"message": "hi"})

    assert response.status_code == 503
