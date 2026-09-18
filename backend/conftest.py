import pytest


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
