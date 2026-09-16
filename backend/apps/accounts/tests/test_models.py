import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import Organization

User = get_user_model()


@pytest.mark.django_db
def test_user_belongs_to_an_organization_with_a_role():
    org = Organization.objects.create(name="Acme Support", slug="acme-support")
    user = User.objects.create_user(
        username="jane",
        password="password123",
        organization=org,
        role=User.Role.AGENT,
    )

    assert user.organization == org
    assert user.role == User.Role.AGENT
    assert org.users.count() == 1
    assert org.users.first() == user


@pytest.mark.django_db
def test_default_role_is_customer():
    org = Organization.objects.create(name="Beta Inc", slug="beta-inc")
    user = User.objects.create_user(username="bob", password="password123", organization=org)

    assert user.role == User.Role.CUSTOMER
