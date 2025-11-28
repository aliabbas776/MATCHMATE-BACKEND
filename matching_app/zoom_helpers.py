"""
Zoom API integration helpers for generating meeting links.

This module provides complete Zoom API integration using Server-to-Server OAuth 2.0
to create meetings programmatically.

Documentation: https://marketplace.zoom.us/docs/api-reference/zoom-api/
"""

import base64
import secrets
from datetime import timedelta
from typing import Dict, Optional, Tuple

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


def get_zoom_access_token() -> str:
    """
    Get a Zoom API access token using Server-to-Server OAuth 2.0.
    
    Tokens are cached for 55 minutes (they expire in 1 hour) to avoid
    unnecessary API calls.
    
    Returns:
        str: Access token for Zoom API
    
    Raises:
        Exception: If Zoom API credentials are missing or authentication fails
    """
    # Check cache first
    cached_token = cache.get('zoom_access_token')
    if cached_token:
        return cached_token
    
    # Validate credentials
    if not settings.ZOOM_ACCOUNT_ID:
        raise ValueError("ZOOM_ACCOUNT_ID is not set in environment variables")
    if not settings.ZOOM_CLIENT_ID:
        raise ValueError("ZOOM_CLIENT_ID is not set in environment variables")
    if not settings.ZOOM_CLIENT_SECRET:
        raise ValueError("ZOOM_CLIENT_SECRET is not set in environment variables")
    
    # Create Basic Auth header
    credentials = f"{settings.ZOOM_CLIENT_ID}:{settings.ZOOM_CLIENT_SECRET}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    
    # Request access token
    # Note: For Server-to-Server OAuth, scopes must be configured in Zoom Marketplace app settings
    # The required scopes are: meeting:write:meeting and meeting:write:meeting:admin
    auth_url = f"{settings.ZOOM_OAUTH_URL}?grant_type=account_credentials&account_id={settings.ZOOM_ACCOUNT_ID}"
    headers = {
        'Authorization': f'Basic {encoded_credentials}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    try:
        response = requests.post(auth_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        access_token = data.get('access_token')
        
        if not access_token:
            raise ValueError(f"Failed to get access token: {data}")
        
        # Cache token for 55 minutes (tokens expire in 1 hour)
        cache.set('zoom_access_token', access_token, 55 * 60)
        
        return access_token
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to authenticate with Zoom API: {str(e)}")
    except Exception as e:
        raise Exception(f"Error getting Zoom access token: {str(e)}")


def create_zoom_meeting(
    topic: str = "1-on-1 Session",
    duration_minutes: int = 60,
    password: Optional[str] = None,
    start_time: Optional[timezone.datetime] = None,
) -> Tuple[str, str, str]:
    """
    Create a Zoom meeting via API.
    
    Args:
        topic: Meeting topic/name
        duration_minutes: Meeting duration in minutes
        password: Optional meeting password (auto-generated if None)
        start_time: Optional scheduled start time (None for instant meeting)
    
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
                'join_before_host': False,
                'waiting_room': True,
                'participant_video': True,
                'host_video': True,
                'mute_upon_entry': False,
                'watermark': False,
                'use_pmi': False,
                'approval_type': 0,  # Automatically approve
                'audio': 'both',  # Both telephony and VoIP
                'auto_recording': 'none',
            }
        }
        
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
        
        response.raise_for_status()
        meeting = response.json()
        
        meeting_id = str(meeting['id'])
        join_url = meeting['join_url']
        meeting_password = meeting.get('password', meeting_password)
        
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


def delete_zoom_meeting(meeting_id: str) -> bool:
    """
    Delete a Zoom meeting.
    
    Args:
        meeting_id: Zoom meeting ID
    
    Returns:
        bool: True if successful
    
    Raises:
        Exception: If Zoom API call fails
    """
    try:
        access_token = get_zoom_access_token()
        headers = {
            'Authorization': f'Bearer {access_token}',
        }
        
        response = requests.delete(
            f'{settings.ZOOM_BASE_URL}/meetings/{meeting_id}',
            headers=headers,
            timeout=10
        )
        
        response.raise_for_status()
        return response.status_code == 204
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            # Meeting doesn't exist, consider it deleted
            return True
        error_msg = f"Zoom API HTTP error: {e.response.status_code}"
        try:
            error_data = e.response.json()
            error_msg += f" - {error_data.get('message', 'Unknown error')}"
        except:
            error_msg += f" - {e.response.text}"
        raise Exception(error_msg)
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to delete Zoom meeting: {str(e)}")
    except Exception as e:
        raise Exception(f"Error deleting Zoom meeting: {str(e)}")


def get_meeting_info(meeting_id: str) -> Dict:
    """
    Get information about a Zoom meeting.
    
    Args:
        meeting_id: Zoom meeting ID
    
    Returns:
        Dict: Meeting information
    
    Raises:
        Exception: If Zoom API call fails
    """
    try:
        access_token = get_zoom_access_token()
        headers = {
            'Authorization': f'Bearer {access_token}',
        }
        
        response = requests.get(
            f'{settings.ZOOM_BASE_URL}/meetings/{meeting_id}',
            headers=headers,
            timeout=10
        )
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.HTTPError as e:
        error_msg = f"Zoom API HTTP error: {e.response.status_code}"
        try:
            error_data = e.response.json()
            error_msg += f" - {error_data.get('message', 'Unknown error')}"
        except:
            error_msg += f" - {e.response.text}"
        raise Exception(error_msg)
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to get Zoom meeting info: {str(e)}")
    except Exception as e:
        raise Exception(f"Error getting Zoom meeting info: {str(e)}")
