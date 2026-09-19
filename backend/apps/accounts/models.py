import hashlib
import secrets

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.common.models import BaseModel


class Organization(BaseModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name

    @property
    def owner(self):
        return self.users.filter(role=User.Role.OWNER).first()


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        AGENT = "agent", "Agent"
        CUSTOMER = "customer", "Customer"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)

    def __str__(self):
        return self.username


class APIKey(BaseModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="api_keys"
    )
    name = models.CharField(max_length=255)
    prefix = models.CharField(max_length=8, unique=True, editable=False)
    hashed_key = models.CharField(max_length=64, editable=False)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

    @property
    def is_active(self):
        return self.revoked_at is None

    @staticmethod
    def hash_key(raw_key):
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @classmethod
    def create_for_organization(cls, organization, name):
        raw_key = secrets.token_urlsafe(32)
        prefix = raw_key[:8]
        instance = cls.objects.create(
            organization=organization,
            name=name,
            prefix=prefix,
            hashed_key=cls.hash_key(raw_key),
        )
        return instance, raw_key
