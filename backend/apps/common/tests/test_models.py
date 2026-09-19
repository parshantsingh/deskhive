import datetime
import uuid

import pytest
from django.utils import timezone

from apps.accounts.models import Organization
from apps.tickets.models import Category, Comment, Ticket


@pytest.mark.django_db
def test_models_use_uuid_primary_keys(org):
    category = Category.objects.create(organization=org, name="Billing")

    assert isinstance(category.id, uuid.UUID)
    assert isinstance(org.id, uuid.UUID)


@pytest.mark.django_db
def test_saving_moves_updated_at_but_not_created_at(org):
    category = Category.objects.create(organization=org, name="Billing")
    original_created_at = category.created_at

    # .update() bypasses auto_now, letting us rewind the clock deterministically
    # instead of hoping two saves land on different microseconds.
    long_ago = timezone.now() - datetime.timedelta(days=1)
    Category.objects.filter(pk=category.pk).update(updated_at=long_ago)

    category.refresh_from_db()
    category.name = "Payments"
    category.save()
    category.refresh_from_db()

    assert category.updated_at > long_ago
    assert category.created_at == original_created_at


@pytest.mark.parametrize("model", [Organization, Category, Ticket, Comment])
def test_every_domain_model_carries_the_standard_columns(model):
    field_names = {field.name for field in model._meta.get_fields()}

    assert {"id", "created_at", "updated_at"} <= field_names
