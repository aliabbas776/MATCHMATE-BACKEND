# Connections API

All endpoints live under `/api/v1/connections/` and require JWT authentication.

## Endpoints

- `POST /request/` — body: `{"to_user_id": <user_pk>}`. Starts a pending request unless one already exists.
- `POST /accept/` — body: `{"connection_id": <id>}`. Only the receiver of a pending request can accept.
- `POST /reject/` — body: `{"connection_id": <id>}`. Only the receiver can reject a pending request.
- `POST /cancel/` — body: `{"connection_id": <id>}`. Sender cancels their pending request (removes it).
- `POST /remove/` — body: `{"connection_id": <id>}`. Either party can remove an approved connection.
- `GET /friends/` — lists approved connections with `friend` metadata.
- `GET /pending/sent/` — lists pending requests initiated by the authenticated user.
- `GET /pending/received/` — lists pending requests awaiting the authenticated user's response.

Every response returns either a `UserConnection` payload (id, status, timestamps, friend info, direction) or a detail message with the relevant `connection_id`.


