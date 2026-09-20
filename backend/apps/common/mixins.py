class OrganizationScopedMixin:
    """Scopes a ModelViewSet to the requesting user's organization.

    Every model this is used with MUST have an `organization` ForeignKey.
    Combine with `apps.common.permissions.HasOrganization` so an
    organization-less user gets a clean 403 instead of an empty queryset.
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        # organization_id, not organization: comparing against the id the user
        # row already carries saves a query to load the Organization just to
        # read its primary key back.
        return queryset.filter(organization_id=self.request.user.organization_id)

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)
