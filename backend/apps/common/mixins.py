class OrganizationScopedMixin:
    """Scopes a ModelViewSet to the requesting user's organization.

    Every model this is used with MUST have an `organization` ForeignKey.
    Combine with `apps.common.permissions.HasOrganization` so an
    organization-less user gets a clean 403 instead of an empty queryset.
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(organization=self.request.user.organization)

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)
