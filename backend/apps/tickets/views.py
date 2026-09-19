import logging

from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.viewsets import ModelViewSet

from apps.accounts.models import User
from apps.accounts.permissions import IsAgentOrAbove, IsOwnerOrAdmin
from apps.common.mixins import OrganizationScopedMixin
from apps.common.permissions import HasOrganization
from apps.notifications.tasks import send_new_comment_notification
from apps.realtime.broadcast import broadcast_comment

from .models import Category, SLAPolicy, Tag, Ticket
from .selectors import accessible_tickets
from .serializers import (
    AttachmentSerializer,
    CategorySerializer,
    CommentSerializer,
    SLAPolicySerializer,
    TagSerializer,
    TicketSerializer,
)

logger = logging.getLogger(__name__)


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


class TicketChildListCreateView(generics.ListCreateAPIView):
    """Base for any resource nested under a single ticket (comments, attachments).

    Centralizes the "customer only touches their own ticket" rule in one place,
    so it can't be added correctly on one nested endpoint and forgotten on the
    next one.
    """

    permission_classes = [HasOrganization]

    def get_ticket(self):
        # A ticket the user may not see is a plain 404, never a 403 — same
        # "don't reveal existence" principle as OrganizationScopedMixin.
        return get_object_or_404(accessible_tickets(self.request.user), id=self.kwargs["ticket_id"])


class TicketCommentListCreateView(TicketChildListCreateView):
    serializer_class = CommentSerializer

    def get_queryset(self):
        ticket = self.get_ticket()
        queryset = ticket.comments.all()
        if self.request.user.role == User.Role.CUSTOMER:
            queryset = queryset.filter(is_internal_note=False)
        return queryset

    def perform_create(self, serializer):
        ticket = self.get_ticket()
        user = self.request.user

        if serializer.validated_data.get("is_internal_note") and user.role == User.Role.CUSTOMER:
            raise PermissionDenied("Customers cannot create internal notes.")

        comment = serializer.save(ticket=ticket, organization=user.organization, author=user)
        broadcast_comment(ticket.id, serializer.data, comment.is_internal_note)

        try:
            send_new_comment_notification.delay(str(comment.id))
        except Exception:
            logger.exception("Failed to enqueue notification for comment %s", comment.id)


class TicketAttachmentListCreateView(TicketChildListCreateView):
    serializer_class = AttachmentSerializer

    def get_queryset(self):
        return self.get_ticket().attachments.all()

    def perform_create(self, serializer):
        ticket = self.get_ticket()
        serializer.save(
            ticket=ticket,
            organization=self.request.user.organization,
            uploaded_by=self.request.user,
        )
