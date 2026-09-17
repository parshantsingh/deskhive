from rest_framework.viewsets import ModelViewSet

from apps.accounts.permissions import IsAgentOrAbove, IsOwnerOrAdmin
from apps.common.mixins import OrganizationScopedMixin
from apps.common.permissions import HasOrganization

from .models import Category, SLAPolicy, Tag, Ticket
from .serializers import CategorySerializer, SLAPolicySerializer, TagSerializer, TicketSerializer


class CategoryViewSet(OrganizationScopedMixin, ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [HasOrganization, IsAgentOrAbove]


class TagViewSet(OrganizationScopedMixin, ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [HasOrganization, IsAgentOrAbove]


class SLAPolicyViewSet(OrganizationScopedMixin, ModelViewSet):
    queryset = SLAPolicy.objects.all()
    serializer_class = SLAPolicySerializer
    permission_classes = [HasOrganization, IsOwnerOrAdmin]


class TicketViewSet(OrganizationScopedMixin, ModelViewSet):
    queryset = Ticket.objects.select_related(
        "organization", "category", "requester", "assignee"
    ).prefetch_related("tags")
    serializer_class = TicketSerializer
    permission_classes = [HasOrganization]

    def get_queryset(self):
        # OrganizationScopedMixin already restricts this to the requester's org.
        # A customer must additionally only ever see their OWN tickets — other
        # customers in the same org are not their business. Agents and above
        # act as support staff and see every ticket in the organization.
        queryset = super().get_queryset()
        user = self.request.user
        if user.role == user.Role.CUSTOMER:
            return queryset.filter(requester=user)
        return queryset
