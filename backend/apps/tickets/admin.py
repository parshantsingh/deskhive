from django.contrib import admin

from .models import Category, SLAPolicy, Tag, Ticket


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
