from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import UserConnection
from .serializers import (
    ConnectionAcceptSerializer,
    ConnectionCancelSerializer,
    ConnectionRejectSerializer,
    ConnectionRemoveSerializer,
    ConnectionRequestSerializer,
    UserConnectionSerializer,
)


class ConnectionBaseView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _serialize(self, queryset, request, many=True):
        serializer = UserConnectionSerializer(
            queryset,
            many=many,
            context={'request': request},
        )
        return serializer.data


class ConnectionRequestView(ConnectionBaseView):
    def post(self, request):
        serializer = ConnectionRequestSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        connection = serializer.save()
        response_data = self._serialize(connection, request, many=False)
        return Response(response_data, status=status.HTTP_201_CREATED)


class ConnectionAcceptView(ConnectionBaseView):
    def post(self, request):
        serializer = ConnectionAcceptSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        connection = serializer.save()
        response_data = self._serialize(connection, request, many=False)
        return Response(response_data, status=status.HTTP_200_OK)


class ConnectionRejectView(ConnectionBaseView):
    def post(self, request):
        serializer = ConnectionRejectSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        connection = serializer.save()
        response_data = self._serialize(connection, request, many=False)
        return Response(response_data, status=status.HTTP_200_OK)


class ConnectionCancelView(ConnectionBaseView):
    def post(self, request):
        serializer = ConnectionCancelSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        connection_id = serializer.save()
        return Response(
            {'detail': 'Connection request cancelled.', 'connection_id': connection_id},
            status=status.HTTP_200_OK,
        )


class ConnectionRemoveView(ConnectionBaseView):
    def post(self, request):
        serializer = ConnectionRemoveSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        connection_id = serializer.save()
        return Response(
            {'detail': 'Connection removed.', 'connection_id': connection_id},
            status=status.HTTP_200_OK,
        )


class FriendsListView(ConnectionBaseView):
    def get(self, request):
        connections = (
            UserConnection.objects.select_related('from_user', 'to_user')
            .filter(
                Q(status=UserConnection.Status.APPROVED),
                Q(from_user=request.user) | Q(to_user=request.user),
            )
            .order_by('-updated_at')
        )
        data = self._serialize(connections, request)
        return Response(data, status=status.HTTP_200_OK)


class PendingSentListView(ConnectionBaseView):
    def get(self, request):
        connections = (
            UserConnection.objects.select_related('from_user', 'to_user')
            .filter(from_user=request.user, status=UserConnection.Status.PENDING)
            .order_by('-created_at')
        )
        data = self._serialize(connections, request)
        return Response(data, status=status.HTTP_200_OK)


class PendingReceivedListView(ConnectionBaseView):
    def get(self, request):
        connections = (
            UserConnection.objects.select_related('from_user', 'to_user')
            .filter(to_user=request.user, status=UserConnection.Status.PENDING)
            .order_by('-created_at')
        )
        data = self._serialize(connections, request)
        return Response(data, status=status.HTTP_200_OK)


