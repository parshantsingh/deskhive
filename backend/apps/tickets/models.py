from django.conf import settings
from django.db import models

from apps.accounts.models import Organization
from apps.common.models import BaseModel


class Priority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class Category(BaseModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField(max_length=100)

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


class Tag(BaseModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=50)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="unique_tag_name_per_org")
        ]
        ordering = ["name"]

    def __str__(self):
        return self.name


class SLAPolicy(BaseModel):
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


class Ticket(BaseModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PENDING = "pending", "Pending"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

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
    sla_breached_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set once, the first time the SLA scanner detects this ticket "
        "passed its due_at — guards against re-notifying on every scan.",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "status"], name="ticket_org_status_idx"),
            models.Index(fields=["organization", "assignee"], name="ticket_org_assignee_idx"),
            models.Index(fields=["organization", "-created_at"], name="ticket_org_created_idx"),
            models.Index(fields=["due_at", "sla_breached_at"], name="ticket_due_breached_idx"),
        ]

    def __str__(self):
        return self.subject


class Comment(BaseModel):
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

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["ticket", "created_at"], name="comment_ticket_created_idx"),
        ]

    def __str__(self):
        return f"Comment on {self.ticket_id}"


def ticket_attachment_path(instance, filename):
    return f"tickets/{instance.ticket_id}/{filename}"


class Attachment(BaseModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="attachments"
    )
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="attachments")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="attachments",
    )
    file = models.FileField(upload_to=ticket_attachment_path)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.original_filename
