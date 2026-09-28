import pytest
from channels.layers import channel_layers
from django.core.cache import caches

from apps.accounts.models import Organization, User


@pytest.fixture
def org():
    return Organization.objects.create(name="Acme", slug="acme")


@pytest.fixture
def owner(org):
    return User.objects.create_user(
        username="owner1",
        password="whatever123",
        organization=org,
        role=User.Role.OWNER,
        email="owner1@acme.test",
    )


@pytest.fixture
def agent(org):
    return User.objects.create_user(
        username="agent1",
        password="whatever123",
        organization=org,
        role=User.Role.AGENT,
        email="agent1@acme.test",
    )


@pytest.fixture
def customer(org):
    return User.objects.create_user(
        username="cust1",
        password="whatever123",
        organization=org,
        role=User.Role.CUSTOMER,
        email="cust1@acme.test",
    )


@pytest.fixture(autouse=True)
def _use_tmp_media_root(settings, tmp_path):
    """Redirect file uploads to a throwaway local directory during tests,
    instead of the real S3-compatible storage configured in STORAGES.

    Without the STORAGES override, every attachment test would need a real
    LocalStack/S3 endpoint reachable, making the suite depend on outside
    infrastructure for something that should be a fast, isolated unit test
    (and CI has no such service running). Without MEDIA_ROOT pointing at a
    throwaway directory, a test run against the real FileSystemStorage would
    write real files into the project's actual media/ folder, which
    pytest-django's transaction rollback never cleans up since they're on
    the filesystem, not in the database.
    """
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    }
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture(autouse=True)
def _run_celery_tasks_eagerly(settings):
    """Run Celery tasks inline, synchronously, during tests.

    Without this, every `.delay(...)` call would try to reach a real Redis
    broker and queue the task for a real worker to pick up later — tests
    would either hang waiting for a worker that isn't running, or pass
    without ever actually proving the task's logic works.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture(autouse=True)
def _use_in_memory_channel_layer(settings):
    """Keep WebSocket tests off Redis, and isolated from each other.

    The in-memory layer lives inside the test process, so tests neither need
    a running Redis nor can they see another test's messages.
    """
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    channel_layers.backends = {}
    yield
    channel_layers.backends = {}


@pytest.fixture(autouse=True)
def _use_local_memory_cache(settings):
    # Tests must not read or write the developer's real cache. LocMemCache keeps
    # its data at module level, so it is emptied explicitly around every test.
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    caches["default"].clear()
    yield
    caches["default"].clear()
