from django.contrib import admin

from .models import Category, SLAPolicy, Tag


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
