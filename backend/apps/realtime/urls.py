from django.urls import path

from .views import AnnouncementView

urlpatterns = [
    path("announcements/", AnnouncementView.as_view(), name="announcement"),
]
