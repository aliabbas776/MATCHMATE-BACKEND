"""
Meeting integration helpers for generating meeting links.

This module provides integration for creating meetings programmatically.
Currently uses Google Meet (replacing Zoom).

ZOOM CODE IS COMMENTED OUT - Can be restored if needed.
Google Meet integration uses user OAuth tokens stored in GoogleOAuthToken model.

Documentation:
- Zoom: https://marketplace.zoom.us/docs/api-reference/zoom-api/
- Google Meet: https://developers.google.com/calendar/api/v3/reference/events/insert
"""

import base64
import hashlib
import hmac
import secrets
import time
from datetime import timedelta, datetime
from typing import Dict, Optional, Tuple

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


# ============================================================================
# GOOGLE MEET INTEGRATION (ACTIVE)
# ============================================================================

def create_google_meet_meeting(
    user,
    topic: str = "1-on-1 Session",
    duration_minutes: int = 60,
    start_time: Optional[datetime] = None,
    attendee_email: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Create a Google Meet meeting via Google Calendar API.
    
    This function creates a Google Calendar event with a Google Meet link.
    It uses the user's stored Google OAuth tokens (from GoogleOAuthToken model).
    
    Args:
        user: Django User object - must have authorized Google Calendar access (this user becomes the host/owner)
        topic: Meeting topic/name
        duration_minutes: Meeting duration in minutes
        start_time: Optional scheduled start time (None for immediate meeting)
        attendee_email: Optional email of attendee to invite (this person will need to ask to join)
    
    Returns:
        Tuple of (meet_link, event_id)
    
    Raises:
        Exception: If user hasn't authorized Google Calendar or API call fails
    """
    from matching_app.models import GoogleOAuthToken
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from datetime import timedelta
    
    # Get valid Google credentials for the user (inline to avoid circular import)
    # IMPORTANT: The 'user' parameter determines who is the host/owner of the meeting
    try:
        oauth_token = GoogleOAuthToken.objects.get(user=user)
    except GoogleOAuthToken.DoesNotExist:
        raise Exception(
            f"Google Calendar not authorized for user '{user.username}'. "
            "User must authorize Google Calendar access first by visiting /api/google/login/"
        )
    
    # Create credentials object from stored data
    creds_data = {
        'token': oauth_token.access_token,
        'refresh_token': oauth_token.refresh_token,
        'token_uri': oauth_token.token_uri,
        'client_id': oauth_token.client_id,
        'client_secret': oauth_token.client_secret,
        'scopes': oauth_token.scopes.split(',') if oauth_token.scopes else []
    }
    
    credentials = Credentials(**creds_data)
    
    # Refresh token if expired or about to expire
    if credentials.expired or (oauth_token.expires_at and oauth_token.expires_at <= timezone.now() + timedelta(minutes=5)):
        try:
            credentials.refresh(Request())
            # Update stored token
            oauth_token.access_token = credentials.token
            if credentials.expiry:
                oauth_token.expires_at = credentials.expiry
            oauth_token.save(update_fields=['access_token', 'expires_at', 'updated_at'])
        except Exception as e:
            # Token refresh failed, user needs to re-authorize
            oauth_token.delete()
            raise Exception(
                "Google Calendar token expired. "
                "Please re-authorize Google Calendar access by visiting /api/google/login/"
            )
    if not credentials:
        raise Exception(
            "Google Calendar not authorized. "
            "User must authorize Google Calendar access first by visiting /api/google/login/"
        )
    
    # Calculate start and end times
    if start_time:
        start_dt = start_time
    else:
        start_dt = timezone.now()
    
    end_dt = start_dt + timedelta(minutes=duration_minutes)
    
    try:
        # Build Calendar service
        service = build('calendar', 'v3', credentials=credentials)
        
        # Create event with Google Meet
        event = {
            'summary': topic[:200],  # Limit to 200 chars
            'description': f'Session meeting between users',
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'UTC',
            },
            'conferenceData': {
                'createRequest': {
                    'requestId': f'meet-{user.id}-{int(timezone.now().timestamp())}',
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'
                    }
                }
            }
        }
        
        # Add attendee if provided (this person will need to ask to join)
        if attendee_email:
            event['attendees'] = [
                {'email': attendee_email}
            ]
        
        # Insert event
        created_event = service.events().insert(
            calendarId='primary',
            body=event,
            conferenceDataVersion=1
        ).execute()
        
        # Extract Meet link
        meet_link = created_event.get('hangoutLink') or created_event.get('conferenceData', {}).get('entryPoints', [{}])[0].get('uri', '')
        event_id = created_event.get('id', '')
        
        if not meet_link:
            raise Exception("Failed to get Google Meet link from created event")
        
        # Normalize the Meet link to ensure it's a proper URL
        meet_link = meet_link.strip()
        
        # Ensure the link starts with https://
        if not meet_link.startswith('http://') and not meet_link.startswith('https://'):
            # If it's just a meeting code or path, prepend the full URL
            if meet_link.startswith('meet.google.com/'):
                meet_link = 'https://' + meet_link
            elif '/' in meet_link:
                # Assume it's a path like /rcy-rztt-mde
                meet_link = 'https://meet.google.com' + (meet_link if meet_link.startswith('/') else '/' + meet_link)
            else:
                # Assume it's just the meeting code
                meet_link = f'https://meet.google.com/{meet_link}'
        
        # Ensure it's using https (not http)
        if meet_link.startswith('http://'):
            meet_link = meet_link.replace('http://', 'https://', 1)
        
        return (meet_link, event_id)
        
    except Exception as e:
        raise Exception(f"Failed to create Google Meet: {str(e)}")


# ============================================================================
# ZOOM INTEGRATION (COMMENTED OUT - Replaced with Google Meet)
# ============================================================================

# def get_zoom_access_token() -> str:
#     """
#     Get a Zoom API access token using Server-to-Server OAuth 2.0.
#     
#     Tokens are cached for 55 minutes (they expire in 1 hour) to avoid
#     unnecessary API calls.
#     
#     Returns:
#         str: Access token for Zoom API
#     
#     Raises:
#         Exception: If Zoom API credentials are missing or authentication fails
#     """
#     # Check cache first
#     cached_token = cache.get('zoom_access_token')
#     if cached_token:
#         return cached_token
#     
#     # Validate credentials
#     if not settings.ZOOM_ACCOUNT_ID:
#         raise ValueError("ZOOM_ACCOUNT_ID is not set in environment variables")
#     if not settings.ZOOM_CLIENT_ID:
#         raise ValueError("ZOOM_CLIENT_ID is not set in environment variables")
#     if not settings.ZOOM_CLIENT_SECRET:
#         raise ValueError("ZOOM_CLIENT_SECRET is not set in environment variables")
#     
#     # Create Basic Auth header
#     credentials = f"{settings.ZOOM_CLIENT_ID}:{settings.ZOOM_CLIENT_SECRET}"
#     encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
#     
#     # Request access token
#     # Note: For Server-to-Server OAuth, scopes must be configured in Zoom Marketplace app settings
#     # The required scopes are: meeting:write:meeting and meeting:write:meeting:admin
#     # Parameters must be in the request body, not query string
#     headers = {
#         'Authorization': f'Basic {encoded_credentials}',
#         'Content-Type': 'application/x-www-form-urlencoded'
#     }
#     request_data = {
#         'grant_type': 'account_credentials',
#         'account_id': settings.ZOOM_ACCOUNT_ID
#     }
#     
#     try:
#         response = requests.post(settings.ZOOM_OAUTH_URL, headers=headers, data=request_data, timeout=10)
#         response.raise_for_status()
#         
#         response_data = response.json()
#         access_token = response_data.get('access_token')
#         
#         if not access_token:
#             raise ValueError(f"Failed to get access token: {response_data}")
#         
#         # Cache token for 55 minutes (tokens expire in 1 hour)
#         cache.set('zoom_access_token', access_token, 55 * 60)
#         
#         return access_token
#         
#     except requests.exceptions.HTTPError as e:
#         error_msg = f"Failed to authenticate with Zoom API: {e.response.status_code}"
#         try:
#             error_data = e.response.json()
#             # Zoom API error responses can have different structures
#             error_detail = (
#                 error_data.get('reason') or 
#                 error_data.get('message') or 
#                 error_data.get('error') or 
#                 error_data.get('error_description') or
#                 str(error_data)
#             )
#             error_msg += f" - {error_detail}"
#             # Include full response for debugging
#             error_msg += f"\nFull Zoom response: {error_data}"
#         except:
#             error_msg += f" - {e.response.text}"
#         raise Exception(error_msg)
#     except requests.exceptions.RequestException as e:
#         raise Exception(f"Failed to authenticate with Zoom API: {str(e)}")
#     except Exception as e:
#         raise Exception(f"Error getting Zoom access token: {str(e)}")


# def update_meeting_settings(meeting_id: str, settings: Dict) -> bool:
#     """
#     Update settings for an existing Zoom meeting.
#     
#     Args:
#         meeting_id: Zoom meeting ID
#         settings: Dictionary of settings to update
#     
#     Returns:
#         bool: True if successful
#     
#     Raises:
#         Exception: If Zoom API call fails
#     """
#     try:
#         access_token = get_zoom_access_token()
#         headers = {
#             'Authorization': f'Bearer {access_token}',
#             'Content-Type': 'application/json'
#         }
#         
#         # Only update settings, not the entire meeting
#         update_data = {
#             'settings': settings
#         }
#         
#         response = requests.patch(
#             f'{settings.ZOOM_BASE_URL}/meetings/{meeting_id}',
#             headers=headers,
#             json=update_data,
#             timeout=10
#         )
#         
#         response.raise_for_status()
#         return True
#         
#     except requests.exceptions.HTTPError as e:
#         # Don't raise exception - this is a best-effort update
#         # Account-level settings might prevent some updates
#         return False
#     except Exception:
#         # Silently fail - meeting settings update is not critical
#         return False


def create_zoom_meeting(
    topic: str = "1-on-1 Session",
    duration_minutes: int = 60,
    password: Optional[str] = None,
    start_time: Optional[timezone.datetime] = None,
    host_email: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    Create a Zoom meeting via API.
    
    Args:
        topic: Meeting topic/name
        duration_minutes: Meeting duration in minutes
        password: Optional meeting password (auto-generated if None)
        start_time: Optional scheduled start time (None for instant meeting)
        host_email: Optional email of alternative host (initiator's email)
    
    Returns:
        Tuple of (meeting_id, join_url, password)
    
    Raises:
        Exception: If Zoom API call fails
    """
    try:
        access_token = get_zoom_access_token()
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Generate password if not provided
        meeting_password = password or secrets.token_urlsafe(8)[:10]  # Max 10 chars for Zoom
        
        # Prepare meeting data
        meeting_data = {
            'topic': topic[:200],  # Zoom limit is 200 chars
            'type': 1,  # Instant meeting
            'duration': duration_minutes,
            'password': meeting_password,
            'settings': {
                'join_before_host': True,  # Allow joining before host
                'jbh_time': 0,  # Allow joining immediately (0 = can join anytime before host)
                'waiting_room': False,  # Disable waiting room - critical to prevent "waiting for host" issue
                'participant_video': True,
                'host_video': True,
                'mute_upon_entry': False,
                'watermark': False,
                'use_pmi': False,
                'approval_type': 0,  # Automatically approve (0 = no approval needed)
                'audio': 'both',  # Both telephony and VoIP
                'auto_recording': 'none',
            }
        }
        
        # Add alternative host if provided (this makes the initiator a co-host)
        # Note: If alternative host assignment fails, we'll retry without it
        if host_email:
            meeting_data['settings']['alternative_hosts'] = host_email
        
        # If start_time is provided, make it a scheduled meeting
        if start_time:
            meeting_data['start_time'] = start_time.strftime('%Y-%m-%dT%H:%M:%S')
            meeting_data['type'] = 2  # Scheduled meeting
            meeting_data['timezone'] = str(timezone.get_current_timezone())
        
        # Create meeting
        response = requests.post(
            f'{settings.ZOOM_BASE_URL}/users/me/meetings',
            headers=headers,
            json=meeting_data,
            timeout=10
        )
        
        # If alternative host assignment fails, retry without it
        if response.status_code == 400 and host_email:
            try:
                error_data = response.json()
                error_message = error_data.get('message', '')
                # Check if error is related to alternative host
                if 'alternative host' in error_message.lower() or 'cannot be selected' in error_message.lower():
                    # Remove alternative host and retry
                    meeting_data['settings'].pop('alternative_hosts', None)
                    response = requests.post(
                        f'{settings.ZOOM_BASE_URL}/users/me/meetings',
                        headers=headers,
                        json=meeting_data,
                        timeout=10
                    )
            except:
                pass  # If parsing fails, continue with original error
        
        response.raise_for_status()
        meeting = response.json()
        
        meeting_id = str(meeting['id'])
        join_url = meeting['join_url']
        meeting_password = meeting.get('password', meeting_password)
        
        # CRITICAL: Embed passcode in join URL for one-click join
        # This ensures the passcode is included when the app opens the link
        # Format: https://zoom.us/j/MEETING_ID?pwd=PASSWORD
        # IMPORTANT: When opening from mobile app, use system browser (not WebView)
        # Example: Linking.openURL(zoomUrl) in React Native, or Intent in Android
        from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
        parsed_url = urlparse(join_url)
        query_params = parse_qs(parsed_url.query)
        # Add or update the pwd parameter (required for passcode)
        query_params['pwd'] = [meeting_password]
        # Reconstruct URL with embedded passcode
        new_query = urlencode(query_params, doseq=True)
        join_url = urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            new_query,
            parsed_url.fragment
        ))
        
        # Verify and update settings if needed to ensure waiting room is disabled
        # This is a safety measure in case account-level settings override meeting settings
        try:
            update_meeting_settings(meeting_id, {
                'join_before_host': True,
                'jbh_time': 0,
                'waiting_room': False,
            })
        except Exception as e:
            # Log but don't fail - meeting was created successfully
            # In production, use proper logging
            pass
        
        return (meeting_id, join_url, meeting_password)
        
    except requests.exceptions.HTTPError as e:
        error_msg = f"Zoom API HTTP error: {e.response.status_code}"
        try:
            error_data = e.response.json()
            error_message = error_data.get('message', 'Unknown error')
            error_msg += f" - {error_message}"
            
            # Provide helpful message for scope errors
            if 'scope' in error_message.lower() or 'scopes' in error_message.lower():
                error_msg += "\n\nTo fix this:\n"
                error_msg += "1. Go to https://marketplace.zoom.us/\n"
                error_msg += "2. Navigate to your Server-to-Server OAuth app\n"
                error_msg += "3. Go to 'Scopes' tab\n"
                error_msg += "4. Enable these scopes: 'meeting:write:meeting' and 'meeting:write:meeting:admin'\n"
                error_msg += "5. Activate the app if not already activated"
        except:
            error_msg += f" - {e.response.text}"
        raise Exception(error_msg)
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to create Zoom meeting: {str(e)}")
    except Exception as e:
        raise Exception(f"Error creating Zoom meeting: {str(e)}")


# def delete_zoom_meeting(meeting_id: str) -> bool:
#     """
#     Delete a Zoom meeting.
#     
#     Args:
#         meeting_id: Zoom meeting ID
#     
#     Returns:
#         bool: True if successful
#     
#     Raises:
#         Exception: If Zoom API call fails
#     """
#     try:
#         access_token = get_zoom_access_token()
#         headers = {
#             'Authorization': f'Bearer {access_token}',
#         }
#         
#         response = requests.delete(
#             f'{settings.ZOOM_BASE_URL}/meetings/{meeting_id}',
#             headers=headers,
#             timeout=10
#         )
#         
#         response.raise_for_status()
#         return response.status_code == 204
#         
#     except requests.exceptions.HTTPError as e:
#         if e.response.status_code == 404:
#             # Meeting doesn't exist, consider it deleted
#             return True
#         error_msg = f"Zoom API HTTP error: {e.response.status_code}"
#         try:
#             error_data = e.response.json()
#             error_msg += f" - {error_data.get('message', 'Unknown error')}"
#         except:
#             error_msg += f" - {e.response.text}"
#         raise Exception(error_msg)
#     except requests.exceptions.RequestException as e:
#         raise Exception(f"Failed to delete Zoom meeting: {str(e)}")
#     except Exception as e:
#         raise Exception(f"Error deleting Zoom meeting: {str(e)}")


# def get_meeting_info(meeting_id: str) -> Dict:
#     """
#     Get information about a Zoom meeting.
#     
#     Args:
#         meeting_id: Zoom meeting ID
#     
#     Returns:
#         Dict: Meeting information
#     
#     Raises:
#         Exception: If Zoom API call fails
#     """
#     try:
#         access_token = get_zoom_access_token()
#         headers = {
#             'Authorization': f'Bearer {access_token}',
#         }
#         
#         response = requests.get(
#             f'{settings.ZOOM_BASE_URL}/meetings/{meeting_id}',
#             headers=headers,
#             timeout=10
#         )
#         
#         response.raise_for_status()
#         return response.json()
#         
#     except requests.exceptions.HTTPError as e:
#         error_msg = f"Zoom API HTTP error: {e.response.status_code}"
#         try:
#             error_data = e.response.json()
#             error_msg += f" - {error_data.get('message', 'Unknown error')}"
#         except:
#             error_msg += f" - {e.response.text}"
#         raise Exception(error_msg)
#     except requests.exceptions.RequestException as e:
#         raise Exception(f"Failed to get Zoom meeting info: {str(e)}")
#     except Exception as e:
#         raise Exception(f"Error getting Zoom meeting info: {str(e)}")


# def generate_zoom_sdk_signature(
#     meeting_number: str,
#     role: int,
#     user_name: Optional[str] = None,
# ) -> Dict[str, str]:
#     """
#     Generate Zoom SDK signature for joining meetings via Mobile SDK.
#     
#     This function generates a secure signature that allows mobile apps to join Zoom meetings
#     using the Zoom Mobile SDK. The signature is role-based:
#     - role=1 (host): Allows starting the meeting. Only returned to meeting creator.
#     - role=0 (participant): Allows joining as participant. Returned to other users.
#     
#     WHY SDK IS REQUIRED:
#     - URL-based joining can cause waiting room issues in WebViews
#     - SDK provides native integration with proper role handling
#     - Host role (1) ensures meeting starts automatically without waiting room
#     - Better user experience with native controls
#     
#     SECURITY:
#     - Signature must be generated server-side (NEVER on client)
#     - Host signatures (role=1) only returned to meeting creator
#     - Participant signatures (role=0) for all other users
#     - start_url is NEVER exposed to client
#     
#     Args:
#         meeting_number: Zoom meeting ID (numeric string)
#         role: User role - 1 for host, 0 for participant
#         user_name: Optional user display name for the meeting
#     
#     Returns:
#         Dictionary containing:
#         - signature: HMAC-SHA256 signature
#         - meeting_number: Meeting ID
#         - role: User role (1=host, 0=participant)
#         - user_name: User display name
#         - sdk_key: SDK Key (for client SDK initialization)
#     
#     Raises:
#         ValueError: If SDK credentials are missing or invalid
#         Exception: If signature generation fails
#     
#     Common Mistakes to Avoid:
#     1. ❌ Generating signature on client - ALWAYS generate server-side
#     2. ❌ Exposing SDK Secret to client - Secret must stay on server
#     3. ❌ Returning host signature to participants - Security risk
#     4. ❌ Using wrong timestamp format - Must be Unix timestamp in seconds
#     5. ❌ Not validating meeting_number - Must be numeric string
#     
#     Note: For Server-to-Server OAuth apps (especially created after Feb 2023),
#     Client ID and Client Secret can be used as SDK Key and SDK Secret.
#     The function will automatically fall back to OAuth credentials if SDK credentials are not set.
#     """
#     # Validate SDK credentials
#     # For Server-to-Server OAuth apps (especially created after Feb 2023),
#     # Client ID and Client Secret can be used as SDK Key and SDK Secret
#     sdk_key = settings.ZOOM_SDK_KEY or settings.ZOOM_CLIENT_ID
#     sdk_secret = settings.ZOOM_SDK_SECRET or settings.ZOOM_CLIENT_SECRET
#     
#     if not sdk_key:
#         raise ValueError("ZOOM_SDK_KEY or ZOOM_CLIENT_ID must be set in environment variables")
#     if not sdk_secret:
#         raise ValueError("ZOOM_SDK_SECRET or ZOOM_CLIENT_SECRET must be set in environment variables")
#     
#     # Validate role
#     if role not in [0, 1]:
#         raise ValueError("Role must be 0 (participant) or 1 (host)")
#     
#     # Validate meeting number (must be numeric string)
#     if not meeting_number or not str(meeting_number).isdigit():
#         raise ValueError("Meeting number must be a numeric string")
#     
#     try:
#         # Get current timestamp in seconds (Unix timestamp)
#         timestamp = int(time.time())
#         
#         # Prepare the signature payload
#         # Format: {SDK_KEY}{meeting_number}{timestamp}{role}
#         # This is the standard Zoom SDK signature format
#         signature_payload = f"{sdk_key}{meeting_number}{timestamp}{role}"
#         
#         # Generate HMAC-SHA256 signature
#         # For Server-to-Server OAuth apps, Client ID/Secret can be used as SDK Key/Secret
#         signature = hmac.new(
#             sdk_secret.encode('utf-8'),
#             signature_payload.encode('utf-8'),
#             hashlib.sha256
#         ).hexdigest()
#         
#         # Return signature and required parameters
#         result = {
#             'signature': signature,
#             'meeting_number': str(meeting_number),
#             'role': role,
#             'sdk_key': sdk_key,
#             'timestamp': timestamp,
#         }
#         
#         # Add user name if provided
#         if user_name:
#             result['user_name'] = user_name
#         
#         return result
#         
#     except Exception as e:
#         raise Exception(f"Error generating Zoom SDK signature: {str(e)}")
