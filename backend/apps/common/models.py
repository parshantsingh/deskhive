import uuid

from django.db import models


class UUIDPrimaryKeyModel(models.Model):
    """A random UUID primary key instead of Django's default auto-incrementing
    integer, so no model using this ever exposes a guessable, sequential ID.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    """Records when a row was created."""

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
