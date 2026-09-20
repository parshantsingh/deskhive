import uuid

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

SOME_TICKET_ID = uuid.uuid4()

TENANT_SCOPED_ENDPOINTS = [
    ("get", "/api/v1/categories/"),
    ("get", "/api/v1/tags/"),
    ("get", "/api/v1/sla-policies/"),
    ("get", "/api/v1/tickets/"),
    ("get", f"/api/v1/tickets/{SOME_TICKET_ID}/comments/"),
    ("get", f"/api/v1/tickets/{SOME_TICKET_ID}/attachments/"),
    ("post", "/api/v1/announcements/"),
    ("get", "/api/v1/dashboard/summary/"),
    ("get", "/api/v1/analytics/overview/"),
]


@pytest.mark.parametrize("method, url", TENANT_SCOPED_ENDPOINTS)
def test_anonymous_requests_get_401_not_a_server_error(method, url):
    response = getattr(APIClient(), method)(url)

    assert response.status_code == 401
