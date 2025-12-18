from django.db.models import Q, Max, F
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Message, SubscriptionPlan, UserConnection, UserSubscription


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
            
            # Check if user can chat with this receiver (must check BEFORE creating message)
            # First check if limit applies (not unlimited)
            max_chat_users_limit = subscription.plan.max_chat_users
            
            # ENFORCE CHAT LIMIT: If limit is set (not -1), check if user can start new chat
            if max_chat_users_limit != -1:
                # Check if user has already chatted with this receiver before
                has_chatted_before = Message.objects.filter(
                    Q(sender=request.user, receiver=receiver) |
                    Q(sender=receiver, receiver=request.user)
                ).exists()
                
                # If they haven't chatted with this user before, we need to check the limit
                # because this would be a NEW chat
                if not has_chatted_before:
                    # Count distinct users user has chatted with (EXCLUDING current receiver)
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
                    
                    # If they've already reached the limit, block this new chat
                    # Example: limit=1, they've chatted with 1 user, distinct_chat_users=1
                    # 1 >= 1 → True → BLOCK
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
            
            # Check if this user has chatted with this receiver before
            # This is to determine if we should increment chat_users_count
            has_user_chatted_before = Message.objects.filter(
                Q(sender=request.user, receiver=receiver) |
                Q(sender=receiver, receiver=request.user)
            ).exists()
            
            # Only create message if limit check passes
            message = serializer.save()
            
            # Increment chat_users_count if this is the first time this user is chatting with receiver
            # (i.e., no previous messages exist between these two users)
            if not has_user_chatted_before:
                UserSubscription.objects.filter(user=request.user).update(
                    chat_users_count=F('chat_users_count') + 1
                )
        
        response_data = MessageSerializer(message, context={'request': request}).data
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

