import uuid

from django.db import models

from apps.accounts.models import Organization


class Priority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="unique_category_name_per_org"
            )
        ]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="unique_tag_name_per_org")
        ]

    def __str__(self):
        return self.name


class SLAPolicy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="sla_policies"
    )
    name = models.CharField(max_length=100)
    priority = models.CharField(max_length=10, choices=Priority.choices)
    response_time_minutes = models.PositiveIntegerField(
        help_text="How quickly an agent must first respond, in minutes."
    )
    resolution_time_minutes = models.PositiveIntegerField(
        help_text="How quickly the ticket must be resolved, in minutes."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "priority"], name="unique_sla_policy_per_priority"
            )
        ]
        verbose_name_plural = "SLA policies"

    def __str__(self):
        return f"{self.name} ({self.get_priority_display()})"
