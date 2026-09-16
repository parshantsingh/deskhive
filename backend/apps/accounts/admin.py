from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import APIKey, Organization, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(User)
class AccountUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Tenant", {"fields": ("organization", "role")}),)
    list_display = ("username", "email", "organization", "role", "is_staff")


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "prefix", "created_at", "last_used_at", "is_active")
    readonly_fields = ("prefix", "hashed_key", "created_at", "last_used_at")
