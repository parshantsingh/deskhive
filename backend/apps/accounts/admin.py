from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Organization, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(User)
class AccountUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Tenant", {"fields": ("organization", "role")}),)
    list_display = ("username", "email", "organization", "role", "is_staff")
