from rest_framework import serializers


class AnnouncementSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=500)
