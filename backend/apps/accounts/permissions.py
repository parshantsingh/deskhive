from rest_framework.permissions import BasePermission

from .models import User


class IsOwnerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (User.Role.OWNER, User.Role.ADMIN)
        )


class IsAgentOrAbove(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (User.Role.OWNER, User.Role.ADMIN, User.Role.AGENT)
        )


class IsSameOrganization(BasePermission):
    """Object-level permission: the object must belong to the requester's organization."""

    def has_object_permission(self, request, view, obj):
        obj_org = getattr(obj, "organization", None)
        return bool(
            request.user
            and request.user.is_authenticated
            and obj_org is not None
            and obj_org == request.user.organization
        )
