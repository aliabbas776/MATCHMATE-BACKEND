from django.db.models import Q, F
from django.db import transaction
from rest_framework import status
from rest_framework.parsers import JSONParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Message, Session, SubscriptionPlan, UserConnection, UserSubscription


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
    SessionAuditLogSerializer,
    SessionCancelSerializer,
    SessionCreateSerializer,
    SessionEndSerializer,
    SessionJoinTokenSerializer,
    SessionJoinTokenValidateSerializer,
    SessionReadySerializer,
    SessionSerializer,
    SessionStartSerializer,
)


class SessionBaseView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


class CreateSessionView(SessionBaseView):
    """Endpoint for creating a new session with a friend."""
    
    def post(self, request):
        # Try to get data from request.data
        data = {}
        if request.data:
            if hasattr(request.data, 'dict'):
                data = request.data.dict()
            elif isinstance(request.data, dict):
                data = request.data
            else:
                data = dict(request.data)
        
        # If no data, try to get from query params as fallback
        if not data and 'participant_id' in request.query_params:
            data = {'participant_id': request.query_params.get('participant_id')}
        
        # Check if participant_id is in data
        if 'participant_id' not in data:
            return Response(
                {
                    'error': 'participant_id field is required.',
                    'hint': 'Send JSON body: {"participant_id": 5} OR use query param: ?participant_id=5'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = SessionCreateSerializer(
            data=data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        
        # Use atomic transaction to check limits and create session in one operation
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
            
            # Check session creation limit (must check BEFORE creating session)
            # Use explicit comparison to ensure we're checking correctly
            max_sessions = subscription.plan.max_sessions
            sessions_used = subscription.sessions_used
            
            # CRITICAL: Block if user has reached or exceeded the limit
            if max_sessions != -1:  # Not unlimited
                if sessions_used >= max_sessions:
                    return Response(
                        {
                            'error': 'Session Limit Exceeded',
                            'detail': f'You have reached your monthly limit of {max_sessions} call sessions. You have used {sessions_used} sessions.',
                            'limit': max_sessions,
                            'used': sessions_used,
                            'upgrade_required': True,
                            'message': 'Please upgrade your subscription plan to create more call sessions.',
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
            
            # Pass the locked subscription to serializer to ensure it uses the same object
            # This prevents any race conditions
            serializer.context['subscription'] = subscription
            
            # Only create session if limit check passes
            # Create session (counter will be incremented in serializer)
            session = serializer.save()
        
        response_data = SessionSerializer(session, context={'request': request}).data
        return Response(response_data, status=status.HTTP_201_CREATED)


class StartSessionView(SessionBaseView):
    """Endpoint for starting a session (generating Zoom link)."""
    def post(self, request, session_id):
        serializer = SessionStartSerializer(
            data={'session_id': session_id},
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        session = serializer.save()
        
        # Automatically send a message in the chat with the Google Meet link
        try:
            # Determine the other participant
            other_user = session.participant if request.user == session.initiator else session.initiator
            
            # Create a message with the Google Meet link
            # session.zoom_meeting_url  # COMMENTED OUT - Replaced with Google Meet
            message_content = (
                f"{session.google_meet_link}\n\n"
                f"If you are ready for this session, please click on this link to join."
            )
            
            Message.objects.create(
                sender=request.user,
                receiver=other_user,
                content=message_content,
            )
        except Exception as e:
            # Log error but don't fail the request
            # In production, use proper logging
            pass
        
        response_data = SessionSerializer(session, context={'request': request}).data
        return Response(response_data, status=status.HTTP_200_OK)


class MarkReadyView(SessionBaseView):
    """Endpoint for marking a participant as ready to join."""
    def post(self, request, session_id):
        serializer = SessionReadySerializer(
            data={'session_id': session_id},
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        session = serializer.save()
        response_data = SessionSerializer(session, context={'request': request}).data
        return Response(response_data, status=status.HTTP_200_OK)


class GetJoinTokenView(SessionBaseView):
    """Endpoint for generating a secure join token."""
    def post(self, request, session_id):
        serializer = SessionJoinTokenSerializer(
            data={'session_id': session_id},
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        join_token = serializer.save()
        
        return Response(
            {
                'token': join_token.token,
                'expires_at': join_token.expires_at.isoformat(),
                'session_id': join_token.session_id,
            },
            status=status.HTTP_201_CREATED,
        )


class ValidateJoinTokenView(SessionBaseView):
    """Endpoint for validating a join token and getting session details."""
    def post(self, request):
        serializer = SessionJoinTokenValidateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        session = serializer.save()
        
        response_data = SessionSerializer(session, context={'request': request}).data
        return Response(
            {
                'valid': True,
                'session': response_data,
                # 'zoom_meeting_url': session.zoom_meeting_url,  # COMMENTED OUT
                # 'zoom_meeting_id': session.zoom_meeting_id,  # COMMENTED OUT
                # 'zoom_meeting_password': session.zoom_meeting_password,  # COMMENTED OUT
                'google_meet_link': session.google_meet_link,
                'google_meet_event_id': session.google_meet_event_id,
            },
            status=status.HTTP_200_OK,
        )


class EndSessionView(SessionBaseView):
    """Endpoint for ending a session."""
    def post(self, request, session_id):
        serializer = SessionEndSerializer(
            data={'session_id': session_id},
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        session = serializer.save()
        response_data = SessionSerializer(session, context={'request': request}).data
        return Response(response_data, status=status.HTTP_200_OK)


class CancelSessionView(SessionBaseView):
    """Endpoint for cancelling a session."""
    def post(self, request, session_id):
        serializer = SessionCancelSerializer(
            data={'session_id': session_id},
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        session = serializer.save()
        response_data = SessionSerializer(session, context={'request': request}).data
        return Response(response_data, status=status.HTTP_200_OK)


class SessionListView(SessionBaseView):
    """Endpoint for listing all sessions for the current user."""
    def get(self, request):
        sessions = Session.objects.filter(
            Q(initiator=request.user) | Q(participant=request.user)
        ).select_related('initiator', 'participant').order_by('-created_at')
        
        serializer = SessionSerializer(sessions, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class SessionDetailView(SessionBaseView):
    """Endpoint for getting details of a specific session."""
    def get(self, request, session_id):
        try:
            session = Session.objects.select_related('initiator', 'participant').get(
                id=session_id,
            )
        except Session.DoesNotExist:
            return Response(
                {'error': 'Session not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # Verify user is a participant
        if request.user not in [session.initiator, session.participant]:
            return Response(
                {'error': 'You are not a participant in this session.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        serializer = SessionSerializer(session, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class SessionAuditLogsView(SessionBaseView):
    """Endpoint for viewing audit logs for a session."""
    def get(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return Response(
                {'error': 'Session not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # Verify user is a participant
        if request.user not in [session.initiator, session.participant]:
            return Response(
                {'error': 'You are not a participant in this session.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        audit_logs = session.audit_logs.select_related('user').order_by('-created_at')
        serializer = SessionAuditLogSerializer(audit_logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class GetSDKSignatureView(SessionBaseView):
    """
    Endpoint for getting Google Meet link (Zoom SDK replaced with Google Meet).
    
    NOTE: This endpoint originally generated Zoom SDK signatures, but has been
    updated to return Google Meet links instead. Google Meet doesn't require
    SDK signatures - users can join directly via the link.
    
    This endpoint returns the Google Meet link for joining the session.
    """
    def post(self, request, session_id):
        try:
            session = Session.objects.select_related('initiator', 'participant').get(id=session_id)
        except Session.DoesNotExist:
            return Response(
                {'error': 'Session not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # Verify user is a participant
        if request.user not in [session.initiator, session.participant]:
            return Response(
                {'error': 'You are not a participant in this session.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        # Check session status
        if session.status != Session.Status.ACTIVE:
            return Response(
                {'error': f'Cannot join session. Current status: {session.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Check if meeting has been created
        # if not session.zoom_meeting_id:  # COMMENTED OUT - Zoom check
        if not session.google_meet_link:
            return Response(
                {'error': 'Google Meet link has not been created yet. Please start the session first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # ZOOM SDK CODE COMMENTED OUT - Google Meet doesn't use SDK signatures
        # Determine user role based on who created the meeting
        # Only the initiator (meeting creator) gets host role (1)
        # All others get participant role (0)
        is_host = (request.user == session.initiator)
        # role = 1 if is_host else 0
        
        # Get user name for the meeting
        user_name = request.user.username
        if hasattr(request.user, 'first_name') and request.user.first_name:
            user_name = f"{request.user.first_name} {request.user.last_name or ''}".strip()
        
        # Generate SDK signature - COMMENTED OUT (Zoom SDK)
        # from .zoom_helpers import generate_zoom_sdk_signature
        # 
        # try:
        #     signature_data = generate_zoom_sdk_signature(
        #         meeting_number=session.zoom_meeting_id,
        #         role=role,
        #         user_name=user_name,
        #     )
        # except ValueError as e:
        #     return Response(
        #         {'error': str(e)},
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )
        # except Exception as e:
        #     return Response(
        #         {'error': f'Failed to generate SDK signature: {str(e)}'},
        #         status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        #     )
        
        # Return Google Meet link (no SDK signature needed for Google Meet)
        return Response(
            {
                # 'signature': signature_data['signature'],  # COMMENTED OUT - Zoom SDK
                # 'meeting_number': signature_data['meeting_number'],  # COMMENTED OUT
                # 'role': signature_data['role'],  # COMMENTED OUT
                # 'sdk_key': signature_data['sdk_key'],  # COMMENTED OUT
                'user_name': user_name,
                # 'meeting_password': session.zoom_meeting_password,  # COMMENTED OUT - Google Meet doesn't use passwords
                'is_host': is_host,
                'google_meet_link': session.google_meet_link,
                'google_meet_event_id': session.google_meet_event_id,
                # Note: zoom_meeting_url is included for fallback, but SDK should be used
                # 'zoom_meeting_url': session.zoom_meeting_url,  # COMMENTED OUT
            },
            status=status.HTTP_200_OK,
        )
