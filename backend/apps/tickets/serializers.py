from rest_framework import serializers

from .models import Category, SLAPolicy, Tag


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]


class SLAPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = SLAPolicy
        fields = [
            "id",
            "name",
            "priority",
            "response_time_minutes",
            "resolution_time_minutes",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
