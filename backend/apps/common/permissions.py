from rest_framework.permissions import BasePermission


class HasOrganization(BasePermission):
    """Blocks any authenticated user who isn't attached to an organization yet.

    Every tenant-scoped viewset relies on request.user.organization being set;
    this permission turns a missing organization into a clean 403 instead of
    a confusing crash deeper in the queryset filtering.
    """

    message = "Your account is not attached to an organization."

    def has_permission(self, request, view):
        return bool(request.user and request.user.organization_id)
