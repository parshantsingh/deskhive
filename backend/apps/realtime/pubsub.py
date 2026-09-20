"""Raw Redis Pub/Sub for organization-wide announcements.

Deliberately does NOT go through the Channels layer used by the ticket
sockets: this talks to Redis directly with redis-py's PUBLISH/SUBSCRIBE.

Pub/Sub semantics worth knowing before relying on this:

- Fire-and-forget. Nothing is stored. A subscriber that isn't connected at the
  instant of publishing never sees the message, and it can't be replayed.
- PUBLISH returns how many subscribers received the message, so the sender
  learns how many people were actually reached (possibly zero).
- Pub/Sub is global to the Redis server; it ignores the database number in
  REDIS_URL. Hence the namespaced channel name, so another app sharing this
  Redis can't collide with (or eavesdrop on) our channels.
"""

import json
from functools import lru_cache

import redis
import redis.asyncio as aredis
from django.conf import settings
from django.utils import timezone


def announcement_channel(organization_id):
    return f"deskhive.announcements.{organization_id}"


@lru_cache(maxsize=1)
def _publisher():
    return redis.Redis.from_url(settings.REDIS_URL)


def publish_announcement(organization_id, message, sent_by):
    """Publish to every staff member currently connected for this organization.

    Returns the number of subscribers that received it. Raises
    redis.RedisError if Redis is unreachable — the caller must surface that,
    because here the publish IS the feature.
    """
    payload = json.dumps(
        {
            "type": "announcement",
            "message": message,
            "sent_by": sent_by,
            "sent_at": timezone.now().isoformat(),
        }
    )
    return _publisher().publish(announcement_channel(organization_id), payload)


def subscriber_client():
    """A fresh async client. Each subscriber needs its own connection: a
    connection in subscribe mode can't be used for anything else."""
    return aredis.Redis.from_url(settings.REDIS_URL)
