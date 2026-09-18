from django.contrib import admin

from .models import Attachment, Category, Comment, SLAPolicy, Tag, Ticket


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "created_at")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "created_at")


@admin.register(SLAPolicy)
class SLAPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "priority",
        "response_time_minutes",
        "resolution_time_minutes",
    )


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "subject",
        "organization",
        "status",
        "priority",
        "assignee",
        "due_at",
        "created_at",
    )
    list_filter = ("status", "priority")
    search_fields = ("subject", "description")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "author", "is_internal_note", "created_at")
    list_filter = ("is_internal_note",)


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "ticket", "uploaded_by", "size_bytes", "created_at")
