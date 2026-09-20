import logging

import pytest
from django.core.cache import cache
from redis.exceptions import ConnectionError as RedisConnectionError

from apps.common.cache import get_or_compute, invalidate


class Source:
    """Stands in for the expensive thing (a database query) and counts its calls."""

    def __init__(self, value):
        self.value = value
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.value


def test_first_call_computes_and_second_call_is_served_from_cache():
    source = Source({"open": 3})

    first = get_or_compute("k", source, timeout=60)
    second = get_or_compute("k", source, timeout=60)

    assert first == ({"open": 3}, False)
    assert second == ({"open": 3}, True)
    assert source.calls == 1


def test_invalidate_forces_the_next_read_to_recompute():
    source = Source("v")
    get_or_compute("k", source, timeout=60)

    invalidate("k")
    _, hit = get_or_compute("k", source, timeout=60)

    assert hit is False
    assert source.calls == 2


def test_falsy_values_are_cached_too():
    source = Source(0)

    get_or_compute("k", source, timeout=60)
    value, hit = get_or_compute("k", source, timeout=60)

    assert (value, hit) == (0, True)
    assert source.calls == 1


def _broken(*args, **kwargs):
    raise RedisConnectionError("redis is down")


def test_a_redis_outage_on_read_falls_back_to_the_source(monkeypatch, caplog):
    monkeypatch.setattr(cache, "get", _broken)
    source = Source("fresh")

    with caplog.at_level(logging.WARNING, logger="apps.common.cache"):
        value, hit = get_or_compute("k", source, timeout=60)

    assert (value, hit) == ("fresh", False)
    assert "Cache read failed" in caplog.text


def test_a_redis_outage_on_write_still_returns_the_value(monkeypatch, caplog):
    monkeypatch.setattr(cache, "set", _broken)

    with caplog.at_level(logging.WARNING, logger="apps.common.cache"):
        value, hit = get_or_compute("k", Source("fresh"), timeout=60)

    assert (value, hit) == ("fresh", False)
    assert "Cache write failed" in caplog.text


def test_a_redis_outage_during_invalidation_is_logged_not_raised(monkeypatch, caplog):
    monkeypatch.setattr(cache, "delete_many", _broken)

    with caplog.at_level(logging.WARNING, logger="apps.common.cache"):
        invalidate("k")

    assert "Cache invalidation failed" in caplog.text


@pytest.mark.parametrize("failure", [ValueError("a real bug"), KeyError("k")])
def test_only_redis_errors_are_swallowed(monkeypatch, failure):
    def boom(*args, **kwargs):
        raise failure

    monkeypatch.setattr(cache, "get", boom)

    with pytest.raises(type(failure)):
        get_or_compute("k", Source("v"), timeout=60)
