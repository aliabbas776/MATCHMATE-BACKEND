from django.db.models import Q, F
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
import logging

from .models import SubscriptionPlan, UserConnection, UserSubscription

logger = logging.getLogger(__name__)


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
            # Get or create subscription, then lock it for update
            subscription = get_or_create_user_subscription(request.user)
            # Reload with lock to get latest plan values
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
                # Count actual connection requests sent by this user since last reset (monthly limit)
                # This ensures accuracy even if the connections_used field is out of sync
                # Only count connections created since the last reset date (or subscription start if no reset)
                query = UserConnection.objects.filter(from_user=request.user)
                
                # Use last_reset_at if available, otherwise use subscription start date
                # This ensures we only count connections from the current billing period
                reset_date = subscription.last_reset_at if subscription.last_reset_at else subscription.started_at
                if reset_date:
                    query = query.filter(created_at__gte=reset_date)
                
                # Count within the transaction to ensure accuracy
                actual_connections_sent = query.count()
                
                # CRITICAL: Block if user has reached or exceeded the limit
                # If limit is 15, they can send requests 1-15 (15 total)
                # When they try to send the 16th, actual_connections_sent = 15
                # 15 >= 15 → True → BLOCK (correct - prevents 16th request)
                # When they try to send the 15th, actual_connections_sent = 14
                # 14 >= 15 → False → ALLOW (correct - allows 15th request)
                # The check uses >= to ensure we block when limit is reached, not exceeded
                if actual_connections_sent >= subscription.plan.max_connections:
                    return Response(
                        {
                            'error': 'Connection Request Limit Exceeded',
                            'detail': f'You have reached your monthly limit of {subscription.plan.max_connections} connection requests. You have sent {actual_connections_sent} connection request(s).',
                            'limit': subscription.plan.max_connections,
                            'used': actual_connections_sent,
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
        
        # Send push notification to receiver (outside transaction to avoid blocking)
        notification_result = None
        notification_status = {
            'attempted': False,
            'success': False,
            'error': None,
            'devices_found': 0,
            'devices_notified': 0,
            'devices_failed': 0,
        }
        
        try:
            from .services.notification_examples import send_connection_request_notification
            from .models import Device
            
            logger.info(
                f"[PUSH NOTIFICATION] Connection Request {connection.id}: Starting push notification process. "
                f"From: {request.user.id} ({request.user.username}), "
                f"To: {connection.to_user.id} ({connection.to_user.username})"
            )
            
            # Check if receiver has registered devices
            receiver_devices = Device.objects.filter(user=connection.to_user, is_active=True)
            device_count = receiver_devices.count()
            notification_status['devices_found'] = device_count
            notification_status['attempted'] = True
            
            if device_count == 0:
                logger.warning(
                    f"[PUSH NOTIFICATION] Connection Request {connection.id}: ❌ FAILED - "
                    f"Receiver {connection.to_user.id} ({connection.to_user.username}) has NO active devices registered. "
                    f"Push notification cannot be sent. Receiver must register device first using /api/devices/register/"
                )
                notification_status['error'] = 'No active devices found for receiver'
            else:
                logger.info(
                    f"[PUSH NOTIFICATION] Connection Request {connection.id}: Found {device_count} active device(s) for receiver {connection.to_user.id}"
                )
                
                # Log device details
                for device in receiver_devices:
                    logger.info(
                        f"[PUSH NOTIFICATION] Connection Request {connection.id}: Device ID {device.id}, "
                        f"Type: {device.device_type}, Token: {device.fcm_token[:30]}..."
                    )
                
                notification_result = send_connection_request_notification(
                    from_user=request.user,
                    to_user=connection.to_user
                )
                
                if notification_result:
                    total_devices = notification_result.get('total_devices', 0)
                    successful = notification_result.get('successful', 0)
                    failed = notification_result.get('failed', 0)
                    invalid_removed = notification_result.get('invalid_tokens_removed', 0)
                    
                    notification_status['devices_notified'] = successful
                    notification_status['devices_failed'] = failed
                    
                    # Include notification payload in status for debugging
                    if 'notification_payload' in notification_result:
                        notification_status['payload'] = notification_result['notification_payload']
                    
                    if successful > 0:
                        logger.info(
                            f"[PUSH NOTIFICATION] Connection Request {connection.id}: ✅ SUCCESS - "
                            f"Notification sent to {successful} out of {total_devices} device(s). "
                            f"Failed: {failed}, Invalid tokens removed: {invalid_removed}"
                        )
                        notification_status['success'] = True
                    else:
                        logger.warning(
                            f"[PUSH NOTIFICATION] Connection Request {connection.id}: ⚠️ PARTIAL FAILURE - "
                            f"Notification attempted but failed for all {total_devices} device(s). "
                            f"Failed: {failed}, Invalid tokens removed: {invalid_removed}"
                        )
                        notification_status['error'] = f'Failed to send to all {total_devices} device(s)'
                else:
                    logger.error(
                        f"[PUSH NOTIFICATION] Connection Request {connection.id}: ❌ FAILED - "
                        f"send_connection_request_notification returned None"
                    )
                    notification_status['error'] = 'Notification function returned None'
                    
        except Exception as e:
            # Log error but don't fail the request if notification fails
            error_msg = str(e)
            notification_status['error'] = error_msg
            
            logger.error(
                f"[PUSH NOTIFICATION] Connection Request {connection.id}: ❌ EXCEPTION - "
                f"Failed to send push notification: {error_msg}",
                exc_info=True  # Include full traceback
            )
        
        # Log final status
        logger.info(
            f"[PUSH NOTIFICATION] Connection Request {connection.id}: Final status - "
            f"Attempted: {notification_status['attempted']}, "
            f"Success: {notification_status['success']}, "
            f"Devices found: {notification_status['devices_found']}, "
            f"Devices notified: {notification_status['devices_notified']}, "
            f"Error: {notification_status['error'] or 'None'}"
        )
        
        response_data = self._serialize(connection, request, many=False)
        
        # Add push notification status to response for debugging
        response_data['push_notification'] = notification_status
        
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


