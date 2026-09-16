from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import APIKey
from .permissions import IsOwnerOrAdmin
from .serializers import InviteMemberSerializer, RegisterSerializer


def _user_payload(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "organization": str(user.organization_id) if user.organization_id else None,
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": _user_payload(user),
            },
            status=status.HTTP_201_CREATED,
        )


class MeView(APIView):
    def get(self, request):
        return Response(_user_payload(request.user))


class InviteMemberView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def post(self, request):
        serializer = InviteMemberSerializer(
            data=request.data,
            context={"organization": request.user.organization},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(_user_payload(user), status=status.HTTP_201_CREATED)


class CreateAPIKeyView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def post(self, request):
        name = request.data.get("name", "API Key")
        api_key, raw_key = APIKey.create_for_organization(request.user.organization, name)
        return Response(
            {
                "id": str(api_key.id),
                "name": api_key.name,
                "prefix": api_key.prefix,
                "key": raw_key,
            },
            status=status.HTTP_201_CREATED,
        )
