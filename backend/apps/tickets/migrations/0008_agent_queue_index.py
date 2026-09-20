from django.contrib.postgres.operations import AddIndexConcurrently, RemoveIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    # CREATE/DROP INDEX CONCURRENTLY cannot run inside a transaction. In exchange
    # they don't block writes to tickets while the index builds, which matters on
    # a table that is being written to all day.
    atomic = False

    dependencies = [
        ("tickets", "0007_attachment_updated_at_category_updated_at_and_more"),
    ]

    operations = [
        # New index first, so there is never a moment without coverage.
        AddIndexConcurrently(
            model_name="ticket",
            index=models.Index(
                fields=["organization", "assignee", "status", "-created_at"],
                name="ticket_agent_queue_idx",
            ),
        ),
        # (organization, assignee) is a strict prefix of the new index.
        RemoveIndexConcurrently(
            model_name="ticket",
            name="ticket_org_assignee_idx",
        ),
    ]
