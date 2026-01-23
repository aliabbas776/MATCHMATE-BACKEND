from django.db.models import Q, Max, F
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.authentication import JWTAuthentication
import logging

from .models import Message, SubscriptionPlan, UserConnection, UserSubscription

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
    ConversationListSerializer,
    MessageCreateSerializer,
    MessageMarkReadSerializer,
    MessageSerializer,
)


class MessageBaseView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


class SendMessageView(MessageBaseView):
    """Endpoint for sending a message to an approved friend."""
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def post(self, request):
        serializer = MessageCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        
        # Get receiver from validated data
        receiver = serializer.validated_data.get('receiver')
        
        # Use atomic transaction to check limits and create message in one operation
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
            
            # Check if user can chat with this receiver (must check BEFORE creating message)
            # First check if limit applies (not unlimited)
            max_chat_users_limit = subscription.plan.max_chat_users
            
            # Check if user has already chatted with this receiver before
            # This check happens BEFORE message creation to determine if this is a NEW chat
            has_chatted_before = Message.objects.filter(
                Q(sender=request.user, receiver=receiver) |
                Q(sender=receiver, receiver=request.user)
            ).exists()
            
            # ENFORCE CHAT LIMIT: If limit is set (not -1), check if user can start new chat
            if max_chat_users_limit != -1:
                # If they haven't chatted with this user before, we need to check the limit
                # because this would be a NEW chat
                if not has_chatted_before:
                    # Count distinct users user has chatted with (EXCLUDING current receiver)
                    # This must be done within the transaction to ensure accuracy
                    sent_to_users = set(
                        Message.objects.filter(sender=request.user)
                        .values_list('receiver_id', flat=True)
                        .distinct()
                    )
                    received_from_users = set(
                        Message.objects.filter(receiver=request.user)
                        .values_list('sender_id', flat=True)
                        .distinct()
                    )
                    # Get all users they've chatted with (combining sent and received)
                    distinct_chat_users = len(sent_to_users | received_from_users)
                    
                    # CRITICAL: Block if user has reached or exceeded the limit
                    # If limit is 5, they can chat with users 1, 2, 3, 4, 5 (5 users total)
                    # When they try to start the 6th chat, distinct_chat_users = 5
                    # 5 >= 5 → True → BLOCK (correct - they already have 5 users)
                    # When they try to start the 5th chat, distinct_chat_users = 4
                    # 4 >= 5 → False → ALLOW (correct - can start 5th chat)
                    # When they try to start the 3rd chat, distinct_chat_users = 2
                    # 2 >= 5 → False → ALLOW (correct - can start 3rd chat)
                    if distinct_chat_users >= max_chat_users_limit:
                        return Response(
                            {
                                'error': 'Chat Limit Exceeded',
                                'detail': f'You have reached your monthly limit of {max_chat_users_limit} different users you can chat with. You are currently chatting with {distinct_chat_users} user(s).',
                                'limit': max_chat_users_limit,
                                'used': distinct_chat_users,
                                'upgrade_required': True,
                                'message': 'Please upgrade your subscription plan to chat with more users.',
                            },
                            status=status.HTTP_403_FORBIDDEN,
                        )
                # If has_chatted_before is True, they've already chatted with this user,
                # so we allow them to continue (no limit check needed for existing chats)
                # This allows users to continue conversations even if they exceeded the limit
                # (e.g., if limit was changed after they already started chatting)
            
            # Only create message if limit check passes (limit check was done above)
            message = serializer.save()
            
            # Increment chat_users_count if this is the first time this user is chatting with receiver
            # (i.e., no previous messages existed between these two users BEFORE this message was created)
            # This ensures chat_users_count stays in sync with actual distinct chat users
            if not has_chatted_before:
                # Atomically increment chat_users_count using F() expression
                # This ensures thread-safe updates even with concurrent requests
                # The increment happens within the same transaction, so it's guaranteed to be consistent
                UserSubscription.objects.filter(user=request.user).update(
                    chat_users_count=F('chat_users_count') + 1
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
            from .services.notification_examples import send_new_message_notification
            from .models import Device
            
            logger.info(
                f"[PUSH NOTIFICATION] Message {message.id}: Starting push notification process. "
                f"Sender: {request.user.id} ({request.user.username}), "
                f"Receiver: {receiver.id} ({receiver.username})"
            )
            
            # Check if receiver has registered devices
            receiver_devices = Device.objects.filter(user=receiver, is_active=True)
            device_count = receiver_devices.count()
            notification_status['devices_found'] = device_count
            notification_status['attempted'] = True
            
            if device_count == 0:
                logger.warning(
                    f"[PUSH NOTIFICATION] Message {message.id}: ❌ FAILED - "
                    f"Receiver {receiver.id} ({receiver.username}) has NO active devices registered. "
                    f"Push notification cannot be sent. Receiver must register device first using /api/devices/register/"
                )
                notification_status['error'] = 'No active devices found for receiver'
            else:
                logger.info(
                    f"[PUSH NOTIFICATION] Message {message.id}: Found {device_count} active device(s) for receiver {receiver.id}"
                )
                
                # Log device details
                for device in receiver_devices:
                    logger.info(
                        f"[PUSH NOTIFICATION] Message {message.id}: Device ID {device.id}, "
                        f"Type: {device.device_type}, Token: {device.fcm_token[:30]}..."
                    )
                
                # Prepare message preview for logging
                message_preview = message.content[:100] + ('...' if len(message.content) > 100 else '')
                
                logger.info(
                    f"[PUSH NOTIFICATION] Message {message.id}: Sending notification. "
                    f"Preview: '{message_preview}'"
                )
                
                notification_result = send_new_message_notification(
                    sender_user=request.user,
                    receiver_user=receiver,
                    message_content=message.content  # Pass full content, function will truncate for body
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
                            f"[PUSH NOTIFICATION] Message {message.id}: ✅ SUCCESS - "
                            f"Notification sent to {successful} out of {total_devices} device(s). "
                            f"Failed: {failed}, Invalid tokens removed: {invalid_removed}"
                        )
                        notification_status['success'] = True
                    else:
                        logger.warning(
                            f"[PUSH NOTIFICATION] Message {message.id}: ⚠️ PARTIAL FAILURE - "
                            f"Notification attempted but failed for all {total_devices} device(s). "
                            f"Failed: {failed}, Invalid tokens removed: {invalid_removed}"
                        )
                        notification_status['error'] = f'Failed to send to all {total_devices} device(s)'
                else:
                    logger.error(
                        f"[PUSH NOTIFICATION] Message {message.id}: ❌ FAILED - "
                        f"send_new_message_notification returned None"
                    )
                    notification_status['error'] = 'Notification function returned None'
                    
        except Exception as e:
            # Log error but don't fail the request if notification fails
            error_msg = str(e)
            notification_status['error'] = error_msg
            
            logger.error(
                f"[PUSH NOTIFICATION] Message {message.id}: ❌ EXCEPTION - "
                f"Failed to send push notification: {error_msg}",
                exc_info=True  # Include full traceback
            )
        
        # Log final status
        logger.info(
            f"[PUSH NOTIFICATION] Message {message.id}: Final status - "
            f"Attempted: {notification_status['attempted']}, "
            f"Success: {notification_status['success']}, "
            f"Devices found: {notification_status['devices_found']}, "
            f"Devices notified: {notification_status['devices_notified']}, "
            f"Error: {notification_status['error'] or 'None'}"
        )
        
        response_data = MessageSerializer(message, context={'request': request}).data
        
        # Add push notification status to response for debugging
        response_data['push_notification'] = notification_status
        
        return Response(response_data, status=status.HTTP_201_CREATED)


class ConversationThreadView(MessageBaseView):
    """Endpoint for viewing a conversation thread between two users."""
    def get(self, request, user_id):
        try:
            other_user_id = int(user_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid user ID.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify they are friends
        connection_exists = UserConnection.objects.filter(
            Q(from_user=request.user, to_user_id=other_user_id) |
            Q(from_user_id=other_user_id, to_user=request.user),
            status=UserConnection.Status.APPROVED
        ).exists()

        if not connection_exists:
            return Response(
                {'error': 'You cannot view this conversation unless you are friends.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get all messages between the two users, ordered by newest first
        messages = Message.objects.filter(
            Q(sender=request.user, receiver_id=other_user_id) |
            Q(sender_id=other_user_id, receiver=request.user)
        ).select_related('sender', 'receiver').order_by('-created_at')

        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ConversationsListView(MessageBaseView):
    """Endpoint for listing all conversations grouped by user with latest message."""
    def get(self, request):
        # Get all users the current user has messages with (either as sender or receiver)
        # and get the latest message for each conversation
        user_id = request.user.id

        # Get all unique conversation partners
        sent_messages = Message.objects.filter(sender=request.user).values('receiver_id').annotate(
            latest_created_at=Max('created_at')
        )
        received_messages = Message.objects.filter(receiver=request.user).values('sender_id').annotate(
            latest_created_at=Max('created_at')
        )

        # Combine and get unique user IDs with their latest message timestamp
        conversation_partners = {}
        for msg in sent_messages:
            partner_id = msg['receiver_id']
            latest_time = msg['latest_created_at']
            if partner_id not in conversation_partners or latest_time > conversation_partners[partner_id]:
                conversation_partners[partner_id] = latest_time

        for msg in received_messages:
            partner_id = msg['sender_id']
            latest_time = msg['latest_created_at']
            if partner_id not in conversation_partners or latest_time > conversation_partners[partner_id]:
                conversation_partners[partner_id] = latest_time

        # Build conversation list with latest message and unread count
        conversations = []
        for partner_id, latest_time in conversation_partners.items():
            # Get the latest message
            latest_message = Message.objects.filter(
                Q(sender=request.user, receiver_id=partner_id) |
                Q(sender_id=partner_id, receiver=request.user),
                created_at=latest_time
            ).select_related('sender', 'receiver').first()

            if not latest_message:
                continue

            # Get unread count (messages sent to current user that are unread)
            unread_count = Message.objects.filter(
                sender_id=partner_id,
                receiver=request.user,
                is_read=False
            ).count()

            # Get the other user
            other_user = latest_message.sender if latest_message.sender_id != user_id else latest_message.receiver

            conversations.append({
                'user': other_user,
                'latest_message': latest_message,
                'unread_count': unread_count,
            })

        # Sort by latest message time (newest first)
        conversations.sort(key=lambda x: x['latest_message'].created_at, reverse=True)

        serializer = ConversationListSerializer(
            conversations,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class AllMessagesView(MessageBaseView):
    """Endpoint for getting all messages for the authenticated user."""
    def get(self, request):
        # Get all messages where the user is either sender or receiver
        messages = Message.objects.filter(
            Q(sender=request.user) | Q(receiver=request.user)
        ).select_related('sender', 'receiver').order_by('-created_at')

        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class MarkMessageReadView(MessageBaseView):
    """Endpoint for marking a message or all messages in a conversation as read."""
    def post(self, request):
        serializer = MessageMarkReadSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        if 'message' in validated_data:
            # Mark single message as read
            message = validated_data['message']
            message.is_read = True
            message.save(update_fields=['is_read'])
            return Response(
                {'detail': 'Message marked as read.', 'message_id': message.id},
                status=status.HTTP_200_OK
            )
        else:
            # Mark all messages in conversation as read
            other_user = validated_data['other_user']
            updated_count = Message.objects.filter(
                sender=other_user,
                receiver=request.user,
                is_read=False
            ).update(is_read=True)
            return Response(
                {
                    'detail': f'Marked {updated_count} message(s) as read.',
                    'conversation_user_id': other_user.id,
                },
                status=status.HTTP_200_OK
            )

