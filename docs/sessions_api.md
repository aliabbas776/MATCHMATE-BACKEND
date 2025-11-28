# 1-on-1 Session System API Documentation

## Overview

This document describes the 1-on-1 session system implementation, similar to Codementor sessions. The system allows approved friends to create video sessions with automatic Zoom meeting link generation, ready/waiting logic, and comprehensive audit logging.

## Features

- ✅ Sessions can only be created between approved friends (connections)
- ✅ Automatic Zoom meeting link generation when any participant starts a session
- ✅ Zoom link automatically sent in chat message
- ✅ The user who generated the Zoom link cannot enter until the other participant marks ready
- ✅ Complete session records with timestamps and audit logs
- ✅ One-time tokenized join links for secure access

## Models

### Session
Main session model tracking:
- `initiator` and `participant` (both must be approved friends)
- `status` (pending, active, completed, cancelled)
- `started_by` (user who generated the Zoom link)
- `zoom_meeting_id`, `zoom_meeting_url`, `zoom_meeting_password`
- `initiator_ready` and `participant_ready` flags
- Timestamps: `created_at`, `started_at`, `ended_at`, `updated_at`

### SessionJoinToken
One-time secure tokens for joining sessions:
- `token` (unique, URL-safe)
- `is_used` flag
- `expires_at` timestamp
- Automatically invalidated after use or expiration

### SessionAuditLog
Complete audit trail of all session events:
- Event types: created, started, ready, joined, left, ended, cancelled, zoom_link_generated
- User who performed the action
- Message and metadata for each event

## API Endpoints

All endpoints require JWT authentication.

### Create Session
**POST** `/v1/sessions/create/`

Create a new session with an approved friend.

**Request Body:**
```json
{
  "participant_id": 123
}
```

**Response:** Session object with status `pending`

### Start Session (Generate Zoom Link)
**POST** `/v1/sessions/{session_id}/start/`

Start a session and generate a Zoom meeting link. The link is automatically sent as a message in the chat.

**Response:** Session object with `status: active` and Zoom meeting details

### Mark Ready
**POST** `/v1/sessions/{session_id}/ready/`

Mark yourself as ready to join the session. The user who started the session cannot join until the other participant marks ready.

**Response:** Updated session object

### Get Join Token
**POST** `/v1/sessions/{session_id}/join-token/`

Generate a secure one-time token for joining the session.

**Response:**
```json
{
  "token": "secure_token_here",
  "expires_at": "2024-01-01T12:00:00Z",
  "session_id": 123
}
```

### Validate Join Token
**POST** `/v1/sessions/join-token/validate/`

Validate a join token and get session details. Token is automatically marked as used.

**Request Body:**
```json
{
  "token": "secure_token_here"
}
```

**Response:** Session details and Zoom meeting information

### End Session
**POST** `/v1/sessions/{session_id}/end/`

End an active session.

**Response:** Updated session object with `status: completed`

### Cancel Session
**POST** `/v1/sessions/{session_id}/cancel/`

Cancel a pending or active session.

**Response:** Updated session object with `status: cancelled`

### List Sessions
**GET** `/v1/sessions/`

Get all sessions for the current user (as initiator or participant).

**Response:** Array of session objects

### Session Details
**GET** `/v1/sessions/{session_id}/`

Get detailed information about a specific session.

**Response:** Session object with full details

### Audit Logs
**GET** `/v1/sessions/{session_id}/audit-logs/`

Get all audit logs for a session.

**Response:** Array of audit log objects

## Ready/Waiting Logic

The system enforces the following rules:

1. **Session Creation**: Either user can create a session with an approved friend
2. **Starting Session**: Either participant can click "Start Session" to generate the Zoom link
3. **Who Started**: The `started_by` field tracks who generated the Zoom link
4. **Join Restrictions**:
   - The user who started (`started_by`) **cannot join** until the other participant marks ready
   - The other participant **can join** once they mark ready
5. **Ready Status**: Each participant must explicitly mark themselves as ready via the `/ready/` endpoint

## Zoom Integration

The system includes Zoom integration stubs in `matching_app/zoom_helpers.py`. To enable actual Zoom integration:

1. Create a Zoom app in the Zoom Marketplace
2. Get your API credentials (API Key, API Secret, Account ID)
3. Add to `settings.py`:
   ```python
   ZOOM_API_KEY = os.getenv('ZOOM_API_KEY')
   ZOOM_API_SECRET = os.getenv('ZOOM_API_SECRET')
   ZOOM_ACCOUNT_ID = os.getenv('ZOOM_ACCOUNT_ID')
   ZOOM_BASE_URL = 'https://api.zoom.us/v2'
   ```
4. Implement the OAuth 2.0 flow in `zoom_helpers.py`
5. Replace stub implementations with actual Zoom API calls

See `zoom_helpers.py` for detailed implementation guidance.

## Security Features

- **Friend Verification**: Sessions can only be created between approved friends
- **Participant Verification**: All endpoints verify the user is a participant
- **One-Time Tokens**: Join tokens are single-use and expire after 1 hour
- **Audit Logging**: Complete audit trail of all session events
- **Ready/Waiting Enforcement**: Backend enforces join restrictions

## Database Migrations

Run migrations to create the session tables:
```bash
python manage.py migrate matching_app
```

## Admin Interface

All session models are registered in Django admin:
- View and manage sessions
- View join tokens and their usage
- View complete audit logs
- Filter and search by various fields

## Example Flow

1. User A creates a session with User B (approved friend)
2. User A clicks "Start Session" → Zoom link generated, message sent to chat
3. User B receives message with Zoom link
4. User B clicks "Mark Ready" → User A can now join
5. User A clicks "Mark Ready" → User B can now join
6. Both users can join the Zoom meeting
7. Session ends when either user clicks "End Session"

## Error Handling

All endpoints return appropriate HTTP status codes:
- `200 OK`: Success
- `201 Created`: Resource created
- `400 Bad Request`: Invalid input
- `403 Forbidden`: Not authorized (not a participant, not a friend, etc.)
- `404 Not Found`: Session not found

Error responses include descriptive error messages in the response body.

