from django.db.models import Q, Max
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Message, UserConnection
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
        message = serializer.save()
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

