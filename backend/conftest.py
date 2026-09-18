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
