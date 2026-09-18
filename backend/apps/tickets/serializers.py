from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import Attachment, Category, Comment, SLAPolicy, Tag, Ticket

User = get_user_model()

MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_ATTACHMENT_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "application/pdf",
    "text/plain",
    "text/csv",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]


class SLAPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = SLAPolicy
        fields = [
            "id",
            "name",
            "priority",
            "response_time_minutes",
            "resolution_time_minutes",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class TicketSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), required=False, allow_null=True
    )
    tags = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), many=True, required=False)
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Ticket
        fields = [
            "id",
            "category",
            "tags",
            "requester",
            "assignee",
            "subject",
            "description",
            "status",
            "priority",
            "due_at",
            "resolved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "requester",
            "due_at",
            "resolved_at",
            "created_at",
            "updated_at",
        ]

    def _organization(self):
        return self.context["request"].user.organization

    def validate_category(self, value):
        if value and value.organization_id != self._organization().id:
            raise serializers.ValidationError("Category does not belong to your organization.")
        return value

    def validate_assignee(self, value):
        if value is None:
            return value

        request_user = self.context["request"].user
        if request_user.role == User.Role.CUSTOMER:
            raise serializers.ValidationError("Customers cannot assign tickets.")
        if value.organization_id != self._organization().id:
            raise serializers.ValidationError("Assignee does not belong to your organization.")
        if value.role == User.Role.CUSTOMER:
            raise serializers.ValidationError("Tickets cannot be assigned to a customer.")
        return value

    def validate_tags(self, value):
        organization_id = self._organization().id
        for tag in value:
            if tag.organization_id != organization_id:
                raise serializers.ValidationError(
                    "One or more tags do not belong to your organization."
                )
        return value

    def create(self, validated_data):
        validated_data.setdefault("requester", self.context["request"].user)
        tags = validated_data.pop("tags", [])

        sla_policy = SLAPolicy.objects.filter(
            organization=validated_data["organization"],
            priority=validated_data.get("priority", Ticket._meta.get_field("priority").default),
        ).first()
        if sla_policy:
            validated_data["due_at"] = timezone.now() + timezone.timedelta(
                minutes=sla_policy.resolution_time_minutes
            )

        ticket = Ticket.objects.create(**validated_data)
        if tags:
            ticket.tags.set(tags)
        return ticket

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)

        new_status = validated_data.get("status")
        if new_status == Ticket.Status.RESOLVED and instance.status != Ticket.Status.RESOLVED:
            validated_data["resolved_at"] = timezone.now()

        ticket = super().update(instance, validated_data)
        if tags is not None:
            ticket.tags.set(tags)
        return ticket


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ["id", "author", "body", "is_internal_note", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


class AttachmentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)

    class Meta:
        model = Attachment
        fields = [
            "id",
            "uploaded_by",
            "file",
            "original_filename",
            "content_type",
            "size_bytes",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "uploaded_by",
            "original_filename",
            "content_type",
            "size_bytes",
            "created_at",
        ]

    def validate_file(self, value):
        if value.size > MAX_ATTACHMENT_SIZE_BYTES:
            raise serializers.ValidationError(
                f"File too large ({value.size} bytes). Max size is "
                f"{MAX_ATTACHMENT_SIZE_BYTES} bytes."
            )
        if value.content_type not in ALLOWED_ATTACHMENT_CONTENT_TYPES:
            raise serializers.ValidationError(f"Unsupported file type: {value.content_type}")
        return value

    def create(self, validated_data):
        file_obj = validated_data.pop("file")
        return Attachment.objects.create(
            file=file_obj,
            original_filename=file_obj.name,
            content_type=file_obj.content_type,
            size_bytes=file_obj.size,
            **validated_data,
        )
