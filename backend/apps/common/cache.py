"""Cache-aside helpers that treat the cache as an optimization, never a dependency.

If Redis is unreachable the caller gets the value straight from its source,
slower but correct, and a warning is logged. A cache outage must not turn
into a page outage.
"""

import logging

from django.core.cache import cache
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


def get_or_compute(key, compute, timeout):
    """Return (value, hit): the cached value if there is one, else compute() and store it.

    `compute` must not return None, which the cache uses to mean "not there".
    """
    try:
        value = cache.get(key)
    except RedisError:
        logger.warning("Cache read failed for %s; computing from source", key, exc_info=True)
        return compute(), False

    if value is not None:
        logger.debug("Cache hit: %s", key)
        return value, True

    logger.debug("Cache miss: %s", key)
    value = compute()
    try:
        cache.set(key, value, timeout)
    except RedisError:
        logger.warning("Cache write failed for %s; serving uncached", key, exc_info=True)
    return value, False


def invalidate(*keys):
    """Drop cached keys. A failure is logged, not raised: the write that caused
    the invalidation has already committed, and the entry's TTL bounds how long
    a value we failed to delete can stay stale."""
    try:
        cache.delete_many(keys)
    except RedisError:
        logger.warning("Cache invalidation failed for %s", keys, exc_info=True)
