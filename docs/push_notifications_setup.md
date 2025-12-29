# Firebase Cloud Messaging (FCM) Push Notifications Setup Guide

This document explains how to set up and use Firebase Cloud Messaging push notifications in the MatchMate backend.

## Overview

The push notification system uses Firebase Cloud Messaging (FCM) HTTP v1 API with the `firebase-admin` SDK. It supports:
- Single device notifications
- Multiple devices per user
- Topic-based notifications (optional)
- Automatic token cleanup for invalid tokens
- Production-ready error handling

## Prerequisites

1. **Firebase Project Setup**
   - Create a Firebase project at https://console.firebase.google.com/
   - Enable Cloud Messaging API
   - Generate a Service Account JSON key:
     - Go to Project Settings → Service Accounts
     - Click "Generate New Private Key"
     - Download the JSON file

2. **Install Dependencies**
   ```bash
   pip install firebase-admin
   ```

## Configuration

### 1. Firebase Credentials

You have two options for providing Firebase credentials:

#### Option 1: Service Account JSON File (Recommended)

Place your Firebase service account JSON file in the project root (e.g., `firebase-service-account.json`).

**Important:** Add this file to `.gitignore` to prevent committing credentials to version control.

Then set the path in `settings.py` or via environment variable:
```python
# In settings.py (already configured)
FIREBASE_SERVICE_ACCOUNT_PATH = BASE_DIR / 'firebase-service-account.json'

# Or via environment variable
FIREBASE_SERVICE_ACCOUNT_PATH=/path/to/firebase-service-account.json
```

#### Option 2: Service Account JSON Content

Set the JSON content directly in environment variables:
```bash
# In .env file
FIREBASE_SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"..."}'
```

### 2. Settings Configuration

The Firebase configuration is already added to `matchmate/settings.py`:

```python
# Firebase Cloud Messaging (FCM) Configuration
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv(
    'FIREBASE_SERVICE_ACCOUNT_PATH',
    BASE_DIR / 'firebase-service-account.json'
)
```

## Database Models

### Device Model

The `Device` model stores FCM tokens for each user's devices:

- `user`: ForeignKey to User model
- `fcm_token`: Unique FCM token (CharField, max 255 chars)
- `device_type`: 'android' or 'ios'
- `is_active`: Boolean flag for active/inactive devices
- `created_at`, `updated_at`: Timestamps

**Features:**
- Multiple devices per user supported
- Automatic deactivation of old tokens
- Indexed for performance

## API Endpoints

### 1. Register Device Token

**POST** `/api/devices/register/`

Register or update an FCM token for the authenticated user.

**Request Body:**
```json
{
    "fcm_token": "device_fcm_token_here",
    "device_type": "android"  // or "ios"
}
```

**Response (201 Created):**
```json
{
    "message": "Device registered successfully.",
    "device": {
        "id": 1,
        "fcm_token": "device_fcm_token_here",
        "device_type": "android",
        "is_active": true,
        "created_at": "2024-01-01T12:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z"
    }
}
```

**Behavior:**
- If token exists for this user, it updates the device type and reactivates it
- If token exists for another user, it deactivates the old device and creates a new one for the current user
- Automatically handles token migration between users

### 2. List User Devices

**GET** `/api/devices/`

List all active devices for the authenticated user.

**Response (200 OK):**
```json
{
    "devices": [
        {
            "id": 1,
            "fcm_token": "token1...",
            "device_type": "android",
            "is_active": true,
            "created_at": "2024-01-01T12:00:00Z",
            "updated_at": "2024-01-01T12:00:00Z"
        }
    ],
    "count": 1
}
```

### 3. Deactivate Device Token

**POST** `/api/devices/deactivate/`

Deactivate a device token (typically called on logout).

**Request Body:**
```json
{
    "fcm_token": "device_fcm_token_here"
}
```

**Response (200 OK):**
```json
{
    "message": "Device token deactivated successfully."
}
```

## Notification Service

### Using the Notification Service

The `FCMNotificationService` class provides methods to send notifications:

```python
from matching_app.services.notifications import get_notification_service

# Get service instance
notification_service = get_notification_service()

# Send to a single device
notification_service.send_to_device(
    fcm_token="device_token",
    title="Hello",
    body="This is a test notification",
    data={"type": "test", "id": "123"}
)

# Send to all devices of a user
notification_service.send_to_user(
    user=user_instance,
    title="Hello",
    body="This is a test notification",
    data={"type": "test"}
)

# Send to multiple devices
notification_service.send_to_multiple_devices(
    tokens=["token1", "token2", "token3"],
    title="Hello",
    body="This is a test notification"
)

# Send to a topic
notification_service.send_to_topic(
    topic="news",
    title="Breaking News",
    body="Important update"
)
```

### Notification Parameters

- `title`: Notification title (required)
- `body`: Notification body text (required)
- `data`: Optional dictionary of custom data (all values must be strings)
- `image_url`: Optional URL of image to display
- `sound`: Sound to play (default: 'default')
- `priority`: 'high' or 'normal' (default: 'high')

## Business Usage Examples

Example functions are provided in `matching_app/services/notification_examples.py`:

### 1. New Message Notification

```python
from matching_app.services.notification_examples import send_new_message_notification

# In your message creation view
send_new_message_notification(
    sender_user=request.user,
    receiver_user=receiver,
    message_content=message.content[:100]
)
```

### 2. Connection Request Notification

```python
from matching_app.services.notification_examples import send_connection_request_notification

# In your connection request view
send_connection_request_notification(
    from_user=request.user,
    to_user=target_user
)
```

### 3. Connection Accepted Notification

```python
from matching_app.services.notification_examples import send_connection_accepted_notification

# In your connection accept view
send_connection_accepted_notification(
    from_user=request.user,
    to_user=connection.from_user
)
```

### 4. Session Invitation Notification

```python
from matching_app.services.notification_examples import send_session_invitation_notification

# In your session creation view
send_session_invitation_notification(
    initiator_user=request.user,
    participant_user=target_user,
    session_id=session.id
)
```

### 5. System Alert Notification

```python
from matching_app.services.notification_examples import send_system_alert_notification

# Send profile verification notification
send_system_alert_notification(
    user=user,
    title="Profile Verified",
    message="Your CNIC verification has been approved!",
    alert_type='success'
)
```

### 6. Match Notification

```python
from matching_app.services.notification_examples import send_match_notification

# After finding a match
send_match_notification(
    user=user,
    matched_user=matched_profile.user
)
```

## Async Support (Celery)

The notification functions are designed to be async-ready. To use with Celery:

1. Install Celery:
   ```bash
   pip install celery
   ```

2. Create a Celery task:
   ```python
   from celery import shared_task
   from matching_app.services.notification_examples import send_new_message_notification
   from django.contrib.auth import get_user_model
   
   User = get_user_model()
   
   @shared_task
   def send_new_message_notification_async(sender_user_id, receiver_user_id, message_content):
       sender_user = User.objects.get(id=sender_user_id)
       receiver_user = User.objects.get(id=receiver_user_id)
       return send_new_message_notification(sender_user, receiver_user, message_content)
   ```

3. Call it asynchronously:
   ```python
   send_new_message_notification_async.delay(
       sender_user_id=request.user.id,
       receiver_user_id=receiver.id,
       message_content=message.content[:100]
   )
   ```

## Error Handling

The notification service automatically handles:

1. **Invalid Tokens**: Automatically removes unregistered or invalid tokens from the database
2. **Network Errors**: Logs errors and returns failure status
3. **FCM API Errors**: Handles FCM-specific exceptions gracefully

All errors are logged to the Django logger for monitoring.

## Security Best Practices

1. **Credentials**: Never commit Firebase service account JSON files to version control
2. **HTTPS**: Always use HTTPS in production (FCM requires HTTPS)
3. **Token Validation**: The service validates FCM tokens before sending
4. **User Authentication**: All device endpoints require JWT authentication
5. **Token Cleanup**: Invalid tokens are automatically deactivated

## Testing

### Test Device Registration

```bash
curl -X POST http://localhost:8000/api/devices/register/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "fcm_token": "test_token_123",
    "device_type": "android"
  }'
```

### Test Notification Sending

You can test notifications using the Django shell:

```python
from django.contrib.auth import get_user_model
from matching_app.services.notifications import get_notification_service

User = get_user_model()
user = User.objects.get(id=1)

service = get_notification_service()
service.send_to_user(
    user=user,
    title="Test Notification",
    body="This is a test",
    data={"type": "test"}
)
```

## Migration

After setting up, run migrations:

```bash
python manage.py migrate
```

This will create the `Device` table in your database.

## Troubleshooting

### Firebase Not Initialized

**Error**: `Firebase credentials not found`

**Solution**: Ensure you've set `FIREBASE_SERVICE_ACCOUNT_PATH` or `FIREBASE_SERVICE_ACCOUNT_JSON` in settings or environment variables.

### Invalid Token Errors

**Error**: `FCM token is unregistered`

**Solution**: This is normal behavior. The service automatically removes invalid tokens. Ensure your mobile app is properly configured with FCM.

### Import Errors

**Error**: `firebase-admin package not installed`

**Solution**: Install the package: `pip install firebase-admin`

## Architecture

```
matching_app/
├── models.py                    # Device model
├── serializers.py              # Device serializers
├── views.py                    # Device API views
├── urls.py                     # Device URL routes
└── services/
    ├── firebase_init.py        # Firebase initialization
    ├── notifications.py        # FCM notification service
    └── notification_examples.py # Business usage examples
```

## Support

For issues or questions:
1. Check Firebase Console for FCM configuration
2. Review Django logs for error messages
3. Verify service account credentials are correct
4. Ensure mobile app is properly configured with FCM

