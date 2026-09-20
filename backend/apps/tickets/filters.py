import django_filters

from .models import Ticket


class TicketFilter(django_filters.FilterSet):
    # Plain id filters rather than the default ModelChoiceFilter. That one
    # validates the value against every row of the related table, across all
    # tenants: another organization's id would be a 400 while an unknown id is
    # an empty page, and the difference tells a caller which ids exist elsewhere.
    # These only narrow the queryset the view has already scoped to the caller.
    assignee = django_filters.NumberFilter(field_name="assignee_id")
    category = django_filters.UUIDFilter(field_name="category_id")

    class Meta:
        model = Ticket
        fields = ["status", "priority", "assignee", "category"]
