from django.urls import path

from .consumers import TicketConsumer

websocket_urlpatterns = [
    path("ws/tickets/<uuid:ticket_id>/", TicketConsumer.as_asgi()),
]
