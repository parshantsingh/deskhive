import logging

from rest_framework.test import APIClient

from config.logging_utils import RequestIDFilter


def test_health_check_logs_with_matching_request_id(caplog):
    caplog.handler.addFilter(RequestIDFilter())

    client = APIClient()
    with caplog.at_level(logging.INFO):
        response = client.get("/api/v1/health/")

    request_id_header = response["X-Request-ID"]
    health_records = [r for r in caplog.records if r.message == "health check requested"]

    assert len(health_records) == 1
    assert health_records[0].request_id == request_id_header


def test_request_id_header_is_passed_through_when_provided():
    client = APIClient()
    response = client.get("/api/v1/health/", HTTP_X_REQUEST_ID="fixed-test-id")

    assert response["X-Request-ID"] == "fixed-test-id"


def test_request_id_differs_between_requests():
    client = APIClient()
    first = client.get("/api/v1/health/")
    second = client.get("/api/v1/health/")

    assert first["X-Request-ID"] != second["X-Request-ID"]
