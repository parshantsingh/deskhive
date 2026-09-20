from django.urls import path

from .consumers import AnnouncementConsumer, TicketConsumer

websocket_urlpatterns = [
    path("ws/tickets/<uuid:ticket_id>/", TicketConsumer.as_asgi()),
    path("ws/announcements/", AnnouncementConsumer.as_asgi()),
]
