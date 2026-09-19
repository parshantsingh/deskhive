import uuid

from django.db import models


class UUIDPrimaryKeyModel(models.Model):
    """A random UUID primary key instead of Django's default auto-incrementing
    integer. Sequential IDs let anyone guess neighbouring records
    (/tickets/104/, /tickets/105/); a UUID removes that enumeration risk.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    """Records when a row was created and when it was last modified."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(UUIDPrimaryKeyModel, TimestampedModel):
    """The standard columns every domain model carries: id, created_at, updated_at."""

    class Meta:
        abstract = True
