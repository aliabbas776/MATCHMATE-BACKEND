from django.db.models import Q, F
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import SubscriptionPlan, UserConnection, UserSubscription


def get_or_create_user_subscription(user):
    """Get or create user subscription, defaulting to FREE plan if doesn't exist."""
    try:
        subscription = UserSubscription.objects.select_related('plan').get(user=user)
        return subscription
    except UserSubscription.DoesNotExist:
        # Get FREE plan
        free_plan = SubscriptionPlan.objects.get(tier=SubscriptionPlan.PlanTier.FREE)
        subscription = UserSubscription.objects.create(
            user=user,
            plan=free_plan,
            status=UserSubscription.SubscriptionStatus.ACTIVE,
        )
        return subscription
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
        
        # Use atomic transaction to check limits and create connection in one operation
        with transaction.atomic():
            # Lock and reload subscription with plan relationship to get latest values
            subscription = UserSubscription.objects.select_related('plan').select_for_update().get(
                user=request.user
            )
            
            # Check if subscription is active
            if not subscription.is_active:
                return Response(
                    {
                        'error': 'Subscription Expired',
                        'detail': 'Your subscription has expired. Please renew to continue using this feature.',
                        'upgrade_required': True,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            
            # Check connection request limit using max_connections (not max_connection_requests)
            # max_connections means the limit on connection requests user can send
            if subscription.plan.max_connections != -1:  # Not unlimited
                if subscription.connections_used >= subscription.plan.max_connections:
                    return Response(
                        {
                            'error': 'Connection Request Limit Exceeded',
                            'detail': f'You have reached your monthly limit of {subscription.plan.max_connections} connection requests.',
                            'limit': subscription.plan.max_connections,
                            'used': subscription.connections_used,
                            'upgrade_required': True,
                            'message': 'Please upgrade your subscription plan to send more connection requests.',
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
            
            # Only create connection if limit check passes
            connection = serializer.save()
            
            # Atomically increment connections counter AFTER successful creation
            # Note: connections_used tracks connection requests sent, not approved connections
            UserSubscription.objects.filter(user=request.user).update(
                connections_used=F('connections_used') + 1
            )
        
        response_data = self._serialize(connection, request, many=False)
        return Response(response_data, status=status.HTTP_201_CREATED)


class ConnectionAcceptView(ConnectionBaseView):
    def post(self, request):
        serializer = ConnectionAcceptSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        
        # Accept connection - no limit check needed
        # max_connections only limits connection requests sent, not approved connections
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
            UserConnection.objects.select_related(
                'from_user',
                'from_user__profile',
                'to_user',
                'to_user__profile',
            )
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
            UserConnection.objects.select_related(
                'from_user',
                'from_user__profile',
                'to_user',
                'to_user__profile',
            )
            .filter(from_user=request.user, status=UserConnection.Status.PENDING)
            .order_by('-created_at')
        )
        data = self._serialize(connections, request)
        return Response(data, status=status.HTTP_200_OK)


class PendingReceivedListView(ConnectionBaseView):
    def get(self, request):
        connections = (
            UserConnection.objects.select_related(
                'from_user',
                'from_user__profile',
                'to_user',
                'to_user__profile',
            )
            .filter(to_user=request.user, status=UserConnection.Status.PENDING)
            .order_by('-created_at')
        )
        data = self._serialize(connections, request)
        return Response(data, status=status.HTTP_200_OK)


