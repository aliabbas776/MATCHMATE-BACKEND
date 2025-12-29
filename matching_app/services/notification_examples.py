"""
Example business usage functions for sending push notifications.

This module demonstrates how to integrate FCM push notifications into your
business logic. These functions can be called from views, signals, or Celery tasks.

NOTE: These functions are async-ready and can be easily converted to Celery tasks.
To use with Celery, simply add @shared_task decorator and call them asynchronously.
"""
import logging
from typing import Optional
from django.contrib.auth import get_user_model

from .notifications import get_notification_service

logger = logging.getLogger(__name__)
User = get_user_model()


def send_new_message_notification(sender_user, receiver_user, message_content: str):
    """
    Send a push notification when a new message is received.
    
    Example usage in views_messages.py:
        from matching_app.services.notification_examples import send_new_message_notification
        
        # After creating a message
        send_new_message_notification(
            sender_user=request.user,
            receiver_user=receiver,
            message_content=message.content[:100]  # First 100 chars
        )
    
    Args:
        sender_user: User who sent the message
        receiver_user: User who should receive the notification
        message_content: Preview of the message content
    """
    try:
        notification_service = get_notification_service()
        
        # Get sender's name for personalization
        sender_name = sender_user.get_full_name() or sender_user.username
        
        title = "New Message"
        body = f"{sender_name}: {message_content}"
        
        # Custom data payload for deep linking
        data = {
            'type': 'new_message',
            'sender_id': str(sender_user.id),
            'sender_name': sender_name,
            'message_preview': message_content[:100],
        }
        
        result = notification_service.send_to_user(
            user=receiver_user,
            title=title,
            body=body,
            data=data,
            priority='high',
        )
        
        logger.info(
            f"New message notification sent to user {receiver_user.id}: "
            f"{result['successful']} devices notified"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to send new message notification: {str(e)}")
        return None


def send_connection_request_notification(from_user, to_user):
    """
    Send a push notification when a connection request is received.
    
    Example usage in views_connections.py:
        from matching_app.services.notification_examples import send_connection_request_notification
        
        # After creating a connection request
        send_connection_request_notification(
            from_user=request.user,
            to_user=target_user
        )
    
    Args:
        from_user: User who sent the connection request
        to_user: User who should receive the notification
    """
    try:
        notification_service = get_notification_service()
        
        from_user_name = from_user.get_full_name() or from_user.username
        
        title = "New Connection Request"
        body = f"{from_user_name} wants to connect with you"
        
        data = {
            'type': 'connection_request',
            'from_user_id': str(from_user.id),
            'from_user_name': from_user_name,
        }
        
        result = notification_service.send_to_user(
            user=to_user,
            title=title,
            body=body,
            data=data,
            priority='high',
        )
        
        logger.info(
            f"Connection request notification sent to user {to_user.id}: "
            f"{result['successful']} devices notified"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to send connection request notification: {str(e)}")
        return None


def send_connection_accepted_notification(from_user, to_user):
    """
    Send a push notification when a connection request is accepted.
    
    Example usage in views_connections.py:
        from matching_app.services.notification_examples import send_connection_accepted_notification
        
        # After accepting a connection
        send_connection_accepted_notification(
            from_user=request.user,  # User who accepted
            to_user=connection.from_user  # User who originally sent the request
        )
    
    Args:
        from_user: User who accepted the connection
        to_user: User who originally sent the connection request
    """
    try:
        notification_service = get_notification_service()
        
        from_user_name = from_user.get_full_name() or from_user.username
        
        title = "Connection Accepted"
        body = f"{from_user_name} accepted your connection request"
        
        data = {
            'type': 'connection_accepted',
            'user_id': str(from_user.id),
            'user_name': from_user_name,
        }
        
        result = notification_service.send_to_user(
            user=to_user,
            title=title,
            body=body,
            data=data,
            priority='normal',
        )
        
        logger.info(
            f"Connection accepted notification sent to user {to_user.id}: "
            f"{result['successful']} devices notified"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to send connection accepted notification: {str(e)}")
        return None


def send_session_invitation_notification(initiator_user, participant_user, session_id: int):
    """
    Send a push notification when a video session is created.
    
    Example usage in views_sessions.py:
        from matching_app.services.notification_examples import send_session_invitation_notification
        
        # After creating a session
        send_session_invitation_notification(
            initiator_user=request.user,
            participant_user=target_user,
            session_id=session.id
        )
    
    Args:
        initiator_user: User who initiated the session
        participant_user: User who should receive the invitation
        session_id: ID of the session
    """
    try:
        notification_service = get_notification_service()
        
        initiator_name = initiator_user.get_full_name() or initiator_user.username
        
        title = "Video Session Invitation"
        body = f"{initiator_name} invited you to a video session"
        
        data = {
            'type': 'session_invitation',
            'initiator_id': str(initiator_user.id),
            'initiator_name': initiator_name,
            'session_id': str(session_id),
        }
        
        result = notification_service.send_to_user(
            user=participant_user,
            title=title,
            body=body,
            data=data,
            priority='high',
        )
        
        logger.info(
            f"Session invitation notification sent to user {participant_user.id}: "
            f"{result['successful']} devices notified"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to send session invitation notification: {str(e)}")
        return None


def send_system_alert_notification(user, title: str, message: str, alert_type: str = 'info'):
    """
    Send a system alert notification to a user.
    
    Example usage:
        from matching_app.services.notification_examples import send_system_alert_notification
        
        # Send profile verification notification
        send_system_alert_notification(
            user=user,
            title="Profile Verified",
            message="Your CNIC verification has been approved!",
            alert_type='success'
        )
    
    Args:
        user: User to send notification to
        title: Notification title
        message: Notification message
        alert_type: Type of alert ('info', 'success', 'warning', 'error')
    """
    try:
        notification_service = get_notification_service()
        
        data = {
            'type': 'system_alert',
            'alert_type': alert_type,
        }
        
        result = notification_service.send_to_user(
            user=user,
            title=title,
            body=message,
            data=data,
            priority='normal',
        )
        
        logger.info(
            f"System alert notification sent to user {user.id}: "
            f"{result['successful']} devices notified"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to send system alert notification: {str(e)}")
        return None


def send_match_notification(user, matched_user):
    """
    Send a push notification when a new match is found.
    
    Example usage:
        from matching_app.services.notification_examples import send_match_notification
        
        # After finding a match
        send_match_notification(
            user=user,
            matched_user=matched_profile.user
        )
    
    Args:
        user: User to notify
        matched_user: User they matched with
    """
    try:
        notification_service = get_notification_service()
        
        matched_name = matched_user.get_full_name() or matched_user.username
        
        title = "New Match Found!"
        body = f"You have a new match with {matched_name}"
        
        data = {
            'type': 'new_match',
            'matched_user_id': str(matched_user.id),
            'matched_user_name': matched_name,
        }
        
        result = notification_service.send_to_user(
            user=user,
            title=title,
            body=body,
            data=data,
            priority='high',
        )
        
        logger.info(
            f"Match notification sent to user {user.id}: "
            f"{result['successful']} devices notified"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to send match notification: {str(e)}")
        return None


# Example Celery task integration (commented out - uncomment when Celery is configured)
"""
from celery import shared_task

@shared_task
def send_new_message_notification_async(sender_user_id, receiver_user_id, message_content):
    \"\"\"
    Async version of send_new_message_notification for Celery.
    
    Usage:
        send_new_message_notification_async.delay(
            sender_user_id=request.user.id,
            receiver_user_id=receiver.id,
            message_content=message.content[:100]
        )
    \"\"\"
    sender_user = User.objects.get(id=sender_user_id)
    receiver_user = User.objects.get(id=receiver_user_id)
    return send_new_message_notification(sender_user, receiver_user, message_content)
"""

