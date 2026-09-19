import pytest
from channels.layers import channel_layers

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
    """Redirect file uploads to a throwaway directory during tests.

    Without this, every test that uploads a file (Attachment) writes a real
    file into the project's actual media/ folder, and pytest-django's
    transaction rollback never cleans those up since they're on the
    filesystem, not in the database.
    """
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
