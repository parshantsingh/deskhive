from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CategoryViewSet,
    SLAPolicyViewSet,
    TagViewSet,
    TicketCommentListCreateView,
    TicketViewSet,
)

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("tags", TagViewSet, basename="tag")
router.register("sla-policies", SLAPolicyViewSet, basename="sla-policy")
router.register("tickets", TicketViewSet, basename="ticket")

urlpatterns = router.urls + [
    path(
        "tickets/<uuid:ticket_id>/comments/",
        TicketCommentListCreateView.as_view(),
        name="ticket-comments",
    ),
]
