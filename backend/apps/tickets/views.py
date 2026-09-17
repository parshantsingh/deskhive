from rest_framework.viewsets import ModelViewSet

from apps.accounts.permissions import IsAgentOrAbove, IsOwnerOrAdmin
from apps.common.mixins import OrganizationScopedMixin
from apps.common.permissions import HasOrganization

from .models import Category, SLAPolicy, Tag
from .serializers import CategorySerializer, SLAPolicySerializer, TagSerializer


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
