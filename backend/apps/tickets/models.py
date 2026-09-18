import uuid

from django.conf import settings
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
        ordering = ["name"]

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
        ordering = ["name"]

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
        ordering = ["priority"]

    def __str__(self):
        return f"{self.name} ({self.get_priority_display()})"


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PENDING = "pending", "Pending"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="tickets")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="tickets",
        null=True,
        blank=True,
    )
    tags = models.ManyToManyField(Tag, related_name="tickets", blank=True)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="tickets_requested",
        null=True,
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="tickets_assigned",
        null=True,
        blank=True,
    )
    subject = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    due_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="SLA deadline, snapshotted from the matching SLAPolicy at creation time.",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"], name="ticket_org_status_idx"),
            models.Index(fields=["organization", "assignee"], name="ticket_org_assignee_idx"),
            models.Index(fields=["organization", "-created_at"], name="ticket_org_created_idx"),
        ]

    def __str__(self):
        return self.subject


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # organization is denormalized here (also reachable via ticket.organization)
    # so this model can reuse the same OrganizationScopedMixin as every other
    # tenant-scoped model, and so tenant filtering never requires a join.
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="comments"
    )
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="comments",
    )
    body = models.TextField()
    is_internal_note = models.BooleanField(
        default=False,
        help_text="Internal notes are visible to agents/admins/owners only, never customers.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["ticket", "created_at"], name="comment_ticket_created_idx"),
        ]

    def __str__(self):
        return f"Comment on {self.ticket_id}"
