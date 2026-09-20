from django.urls import path

from .views import AnalyticsOverviewView, DashboardSummaryView

urlpatterns = [
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("analytics/overview/", AnalyticsOverviewView.as_view(), name="analytics-overview"),
]
