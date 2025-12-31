"""
Firebase Cloud Messaging (FCM) notification service.

This module provides a reusable service layer for sending push notifications
via Firebase Cloud Messaging HTTP v1 API. It handles single device, multiple devices,
and topic-based notifications with proper error handling and token cleanup.
"""
import logging
from typing import List, Dict, Optional, Any
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from ..models import Device

logger = logging.getLogger(__name__)
User = get_user_model()


class FCMNotificationService:
    """
    Service class for sending FCM push notifications.
    
    This class provides methods to send notifications to:
    - Single device
    - Multiple devices for a user
    - Multiple devices by token list
    - Topics (optional)
    
    It automatically handles invalid tokens and removes them from the database.
    """
    
    def __init__(self):
        """Initialize the FCM service and get Firebase messaging instance."""
        try:
            from matching_app.services.firebase_init import get_firebase_app
            from firebase_admin import messaging
            
            self.app = get_firebase_app()
            self.messaging = messaging
            logger.info("FCM Notification Service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize FCM service: {str(e)}")
            raise
    
    def send_to_device(
        self,
        fcm_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        sound: str = 'default',
        priority: str = 'high',
    ) -> bool:
        """
        Send a notification to a single device.
        
        Args:
            fcm_token: FCM token of the target device
            title: Notification title
            body: Notification body text
            data: Optional dictionary of custom data to send with notification
            image_url: Optional URL of image to display in notification
            sound: Sound to play (default: 'default')
            priority: Message priority ('high' or 'normal')
            
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        try:
            # Build notification payload
            notification = self.messaging.Notification(
                title=title,
                body=body,
                image=image_url,
            )
            
            # Build Android-specific config
            android_config = self.messaging.AndroidConfig(
                priority=priority,
                notification=self.messaging.AndroidNotification(
                    sound=sound,
                ),
            )
            
            # Build iOS-specific config
            apns_config = self.messaging.APNSConfig(
                headers={
                    'apns-priority': '10' if priority == 'high' else '5',
                },
                payload=self.messaging.APNSPayload(
                    aps=self.messaging.Aps(
                        sound=sound,
                        badge=None,  # Can be set to increment badge count
                    ),
                ),
            )
            
            # Build message
            message = self.messaging.Message(
                token=fcm_token,
                notification=notification,
                data={k: str(v) for k, v in (data or {}).items()},  # FCM requires string values
                android=self.messaging.AndroidConfig(
                    priority=priority,
                    notification=self.messaging.AndroidNotification(
                        sound=sound,
                    ),
                ),
                apns=apns_config,
            )
            
            # Send message
            response = self.messaging.send(message)
            logger.info(f"Successfully sent notification to device {fcm_token[:20]}...: {response}")
            return True
            
        except self.messaging.UnregisteredError:
            # Token is no longer valid, remove it from database
            logger.warning(f"FCM token is unregistered: {fcm_token[:20]}...")
            self._remove_invalid_token(fcm_token)
            return False
        except (self.messaging.SenderIdMismatchError, self.messaging.ThirdPartyAuthError) as e:
            logger.error(f"Invalid FCM token or argument: {str(e)}")
            self._remove_invalid_token(fcm_token)
            return False
        except Exception as e:
            logger.error(f"Failed to send notification to device {fcm_token[:20]}...: {str(e)}")
            return False
    
    def send_to_user(
        self,
        user: User,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        sound: str = 'default',
        priority: str = 'high',
    ) -> Dict[str, Any]:
        """
        Send a notification to all active devices of a user.
        
        Args:
            user: User instance to send notification to
            title: Notification title
            body: Notification body text
            data: Optional dictionary of custom data
            image_url: Optional URL of image to display
            sound: Sound to play (default: 'default')
            priority: Message priority ('high' or 'normal')
            
        Returns:
            dict: Statistics about the send operation:
                {
                    'total_devices': int,
                    'successful': int,
                    'failed': int,
                    'invalid_tokens_removed': int
                }
        """
        devices = Device.objects.filter(user=user, is_active=True)
        tokens = [device.fcm_token for device in devices]
        
        if not tokens:
            logger.warning(f"No active devices found for user {user.id}")
            return {
                'total_devices': 0,
                'successful': 0,
                'failed': 0,
                'invalid_tokens_removed': 0,
            }
        
        return self.send_to_multiple_devices(
            tokens=tokens,
            title=title,
            body=body,
            data=data,
            image_url=image_url,
            sound=sound,
            priority=priority,
        )
    
    def send_to_multiple_devices(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        sound: str = 'default',
        priority: str = 'high',
    ) -> Dict[str, Any]:
        """
        Send a notification to multiple devices using multicast.
        
        Args:
            tokens: List of FCM tokens
            title: Notification title
            body: Notification body text
            data: Optional dictionary of custom data
            image_url: Optional URL of image to display
            sound: Sound to play (default: 'default')
            priority: Message priority ('high' or 'normal')
            
        Returns:
            dict: Statistics about the send operation
        """
        if not tokens:
            return {
                'total_devices': 0,
                'successful': 0,
                'failed': 0,
                'invalid_tokens_removed': 0,
            }
        
        # FCM supports up to 500 tokens per multicast message
        # Split into batches if needed
        batch_size = 500
        total_successful = 0
        total_failed = 0
        invalid_tokens = set()
        
        for i in range(0, len(tokens), batch_size):
            batch_tokens = tokens[i:i + batch_size]
            
            try:
                # Build notification
                notification = self.messaging.Notification(
                    title=title,
                    body=body,
                    image=image_url,
                )
                
                # Build Android config
                android_config = self.messaging.AndroidConfig(
                    priority=priority,
                    notification=self.messaging.AndroidNotification(
                        sound=sound,
                    ),
                )
                
                # Build iOS config
                apns_config = self.messaging.APNSConfig(
                    headers={
                        'apns-priority': '10' if priority == 'high' else '5',
                    },
                    payload=self.messaging.APNSPayload(
                        aps=self.messaging.Aps(
                            sound=sound,
                        ),
                    ),
                )
                
                # Try to use multicast if available, otherwise send individually
                if hasattr(self.messaging, 'send_multicast'):
                    # Build multicast message
                    message = self.messaging.MulticastMessage(
                        tokens=batch_tokens,
                        notification=notification,
                        data={k: str(v) for k, v in (data or {}).items()},
                        android=android_config,
                        apns=apns_config,
                    )
                    
                    # Send multicast message
                    response = self.messaging.send_multicast(message)
                    
                    # Process results
                    successful_count = response.success_count
                    failed_count = response.failure_count
                    
                    total_successful += successful_count
                    total_failed += failed_count
                    
                    # Check for invalid tokens in failed responses
                    if response.responses:
                        for idx, resp in enumerate(response.responses):
                            if not resp.success:
                                token = batch_tokens[idx]
                                if isinstance(resp.exception, (self.messaging.UnregisteredError, 
                                                               self.messaging.SenderIdMismatchError,
                                                               self.messaging.ThirdPartyAuthError)):
                                    invalid_tokens.add(token)
                    
                    logger.info(
                        f"Multicast batch {i//batch_size + 1}: "
                        f"{successful_count} successful, {failed_count} failed"
                    )
                else:
                    # Fallback: Send messages individually
                    logger.info(f"Multicast not available, sending {len(batch_tokens)} messages individually")
                    for token in batch_tokens:
                        try:
                            message = self.messaging.Message(
                                token=token,
                                notification=notification,
                                data={k: str(v) for k, v in (data or {}).items()},
                                android=android_config,
                                apns=apns_config,
                            )
                            self.messaging.send(message)
                            total_successful += 1
                        except (self.messaging.UnregisteredError, 
                                self.messaging.SenderIdMismatchError,
                                self.messaging.ThirdPartyAuthError):
                            invalid_tokens.add(token)
                            total_failed += 1
                        except Exception as e:
                            logger.error(f"Failed to send to device {token[:20]}...: {str(e)}")
                            total_failed += 1
                
            except Exception as e:
                logger.error(f"Failed to send notification batch: {str(e)}")
                total_failed += len(batch_tokens)
        
        # Remove invalid tokens
        invalid_count = 0
        if invalid_tokens:
            invalid_count = self._remove_invalid_tokens(list(invalid_tokens))
        
        return {
            'total_devices': len(tokens),
            'successful': total_successful,
            'failed': total_failed,
            'invalid_tokens_removed': invalid_count,
        }
    
    def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None,
        sound: str = 'default',
        priority: str = 'high',
    ) -> bool:
        """
        Send a notification to all devices subscribed to a topic.
        
        Args:
            topic: Topic name (e.g., 'news', 'updates')
            title: Notification title
            body: Notification body text
            data: Optional dictionary of custom data
            image_url: Optional URL of image to display
            sound: Sound to play (default: 'default')
            priority: Message priority ('high' or 'normal')
            
        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
        try:
            # Build notification
            notification = self.messaging.Notification(
                title=title,
                body=body,
                image=image_url,
            )
            
            # Build Android config
            android_config = self.messaging.AndroidConfig(
                priority=priority,
                notification=self.messaging.AndroidNotification(
                    sound=sound,
                ),
            )
            
            # Build iOS config
            apns_config = self.messaging.APNSConfig(
                headers={
                    'apns-priority': '10' if priority == 'high' else '5',
                },
                payload=self.messaging.APNSPayload(
                    aps=self.messaging.Aps(
                        sound=sound,
                    ),
                ),
            )
            
            # Build message
            message = self.messaging.Message(
                topic=topic,
                notification=notification,
                data={k: str(v) for k, v in (data or {}).items()},
                android=android_config,
                apns=apns_config,
            )
            
            # Send message
            response = self.messaging.send(message)
            logger.info(f"Successfully sent notification to topic '{topic}': {response}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send notification to topic '{topic}': {str(e)}")
            return False
    
    def _remove_invalid_token(self, fcm_token: str) -> bool:
        """
        Remove an invalid FCM token from the database.
        
        Args:
            fcm_token: Invalid FCM token to remove
            
        Returns:
            bool: True if token was removed, False otherwise
        """
        try:
            with transaction.atomic():
                deleted_count = Device.objects.filter(
                    fcm_token=fcm_token
                ).update(is_active=False)
                
                if deleted_count > 0:
                    logger.info(f"Deactivated invalid FCM token: {fcm_token[:20]}...")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to remove invalid token: {str(e)}")
            return False
    
    def _remove_invalid_tokens(self, fcm_tokens: List[str]) -> int:
        """
        Remove multiple invalid FCM tokens from the database.
        
        Args:
            fcm_tokens: List of invalid FCM tokens to remove
            
        Returns:
            int: Number of tokens removed
        """
        try:
            with transaction.atomic():
                updated_count = Device.objects.filter(
                    fcm_token__in=fcm_tokens
                ).update(is_active=False)
                
                if updated_count > 0:
                    logger.info(f"Deactivated {updated_count} invalid FCM tokens")
                return updated_count
        except Exception as e:
            logger.error(f"Failed to remove invalid tokens: {str(e)}")
            return 0


# Global service instance (singleton pattern)
_notification_service = None


def get_notification_service() -> FCMNotificationService:
    """
    Get the global FCM notification service instance.
    
    Returns:
        FCMNotificationService: Singleton instance of the notification service
    """
    global _notification_service
    
    if _notification_service is None:
        _notification_service = FCMNotificationService()
    
    return _notification_service

