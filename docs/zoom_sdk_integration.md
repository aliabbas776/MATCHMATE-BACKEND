# Zoom SDK Integration Guide

## Overview

This guide explains how to integrate Zoom Mobile SDK with the MatchMate backend to enable secure, role-based meeting joining that prevents waiting room issues.

## Why Zoom SDK Instead of URL-Based Joining?

### Problems with URL-Based Joining:
1. **WebView Issues**: When apps open Zoom URLs in WebViews, Zoom may apply different security rules
2. **Waiting Room Problems**: Users often get stuck in waiting room even when disabled
3. **No Role Control**: Cannot properly distinguish between host and participant
4. **Poor User Experience**: Requires browser redirect, breaks app flow

### Benefits of SDK-Based Joining:
1. **Native Integration**: Seamless experience within your app
2. **Role-Based Access**: Host (role=1) automatically starts meeting, participants (role=0) join directly
3. **No Waiting Room**: Host role ensures meeting starts immediately
4. **Better Security**: Server-side signature generation, never expose secrets
5. **Full Control**: Native UI controls, better error handling

## Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│ Mobile App  │────────▶│ Django API  │────────▶│  Zoom API   │
│             │◀────────│              │◀────────│             │
└─────────────┘         └──────────────┘         └─────────────┘
      │                        │
      │ 1. Request SDK         │ 2. Generate Signature
      │    Signature           │    (role-based)
      │                        │
      │ 3. Receive Signature   │
      │    + Meeting Details   │
      │                        │
      │ 4. Join via SDK        │
      │    (role=1 or 0)       │
      │                        │
```

## Backend Setup

### 1. Environment Variables

Add these to your `.env` file:

```bash
# Zoom OAuth (for meeting creation)
ZOOM_ACCOUNT_ID=your_account_id
ZOOM_CLIENT_ID=your_client_id
ZOOM_CLIENT_SECRET=your_client_secret

# Zoom SDK (for mobile SDK integration)
# Get these from: Zoom Marketplace > Your App > SDK Credentials
ZOOM_SDK_KEY=your_sdk_key
ZOOM_SDK_SECRET=your_sdk_secret
```

**IMPORTANT**: SDK Key and Secret are DIFFERENT from OAuth credentials!

### 2. Get SDK Credentials

1. Go to [Zoom Marketplace](https://marketplace.zoom.us/)
2. Navigate to your Server-to-Server OAuth app
3. Go to "SDK Credentials" section
4. Copy SDK Key and SDK Secret
5. Add to environment variables

## API Endpoints

### Get SDK Signature

**POST** `/v1/sessions/{session_id}/sdk-signature/`

Generate a Zoom SDK signature for joining a meeting via Mobile SDK.

**Authentication**: Required (JWT)

**Request**: No body required (session_id from URL, user from JWT)

**Response**:
```json
{
  "signature": "abc123...",
  "meeting_number": "123456789",
  "role": 1,
  "sdk_key": "your_sdk_key",
  "user_name": "John Doe",
  "meeting_password": "123456",
  "is_host": true,
  "zoom_meeting_url": "https://zoom.us/j/..." // fallback only
}
```

**Security Rules**:
- `role=1` (host) → Only returned to meeting creator (initiator)
- `role=0` (participant) → Returned to other users
- `start_url` → NEVER exposed to client

**Error Responses**:
- `404`: Session not found
- `403`: User is not a participant
- `400`: Session not active or meeting not created
- `500`: Signature generation failed

## Mobile SDK Integration

### React Native (JavaScript/TypeScript)

#### 1. Install Zoom SDK

```bash
npm install @zoom/react-native-videosdk
# or
yarn add @zoom/react-native-videosdk
```

#### 2. Initialize SDK

```typescript
import ZoomVideo from '@zoom/react-native-videosdk';

// Initialize SDK (call once at app startup)
const initializeZoomSDK = async () => {
  try {
    await ZoomVideo.init({
      // SDK Key is returned from backend, but you can also store it in app
      // For security, prefer getting it from backend
    });
    console.log('Zoom SDK initialized');
  } catch (error) {
    console.error('Failed to initialize Zoom SDK:', error);
  }
};
```

#### 3. Join Meeting

```typescript
import { Linking } from 'react-native';
import axios from 'axios';

interface SDKSignatureResponse {
  signature: string;
  meeting_number: string;
  role: number;
  sdk_key: string;
  user_name: string;
  meeting_password: string;
  is_host: boolean;
}

const joinZoomMeeting = async (sessionId: number, authToken: string) => {
  try {
    // 1. Get SDK signature from backend
    const response = await axios.post(
      `https://your-api.com/v1/sessions/${sessionId}/sdk-signature/`,
      {},
      {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      }
    );

    const sdkData: SDKSignatureResponse = response.data;

    // 2. Join meeting using SDK
    const joinResult = await ZoomVideo.joinMeeting({
      meetingNumber: sdkData.meeting_number,
      userName: sdkData.user_name,
      password: sdkData.meeting_password,
      signature: sdkData.signature,
      sdkKey: sdkData.sdk_key,
      // role is embedded in signature, but you can also pass it
      // The signature already contains the role information
    });

    if (joinResult.success) {
      console.log('Successfully joined meeting');
      // Meeting UI will be displayed automatically
    } else {
      console.error('Failed to join meeting:', joinResult.error);
      // Fallback to URL-based joining if SDK fails
      if (sdkData.zoom_meeting_url) {
        Linking.openURL(sdkData.zoom_meeting_url);
      }
    }
  } catch (error) {
    console.error('Error joining meeting:', error);
    // Fallback to URL-based joining
    // You can get zoom_meeting_url from session details
  }
};
```

### Android (Kotlin)

#### 1. Add Dependencies

```gradle
// app/build.gradle
dependencies {
    implementation 'us.zoom.sdk:zoom-sdk-android:5.x.x'
}
```

#### 2. Initialize SDK

```kotlin
import us.zoom.sdk.ZoomSDK
import us.zoom.sdk.ZoomSDKInitializeListener

class MainActivity : AppCompatActivity() {
    private fun initializeZoomSDK() {
        val zoomSDK = ZoomSDK.getInstance()
        
        val initParams = ZoomSDKInitParams().apply {
            appKey = "your_sdk_key" // Or get from backend
            appSecret = "" // Never store secret in app!
        }
        
        zoomSDK.initialize(
            this,
            initParams,
            object : ZoomSDKInitializeListener {
                override fun onZoomSDKInitializeResult(
                    errorCode: Int,
                    internalErrorCode: Int
                ) {
                    if (errorCode == ZoomError.ZOOM_ERROR_SUCCESS) {
                        // SDK initialized successfully
                    }
                }
                
                override fun onZoomAuthIdentityExpired() {
                    // Handle auth expiration
                }
            }
        )
    }
}
```

#### 3. Join Meeting

```kotlin
import us.zoom.sdk.JoinMeetingOptions
import us.zoom.sdk.JoinMeetingParams
import us.zoom.sdk.MeetingService
import us.zoom.sdk.MeetingViewsOptions
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

class ZoomMeetingManager {
    private val apiService: YourApiService
    
    suspend fun joinMeeting(sessionId: Int, authToken: String) {
        try {
            // 1. Get SDK signature from backend
            val sdkData = apiService.getSDKSignature(
                sessionId = sessionId,
                authToken = "Bearer $authToken"
            )
            
            // 2. Get Zoom SDK instance
            val zoomSDK = ZoomSDK.getInstance()
            val meetingService = zoomSDK.meetingService
            
            // 3. Prepare join parameters
            val joinParams = JoinMeetingParams().apply {
                meetingNo = sdkData.meeting_number
                displayName = sdkData.user_name
                password = sdkData.meeting_password
                // Signature is embedded in the join process
            }
            
            val joinOptions = JoinMeetingOptions().apply {
                // Configure options
            }
            
            val meetingViewsOptions = MeetingViewsOptions().apply {
                // Configure view options
            }
            
            // 4. Join meeting
            val result = meetingService.joinMeetingWithParams(
                context = this,
                params = joinParams,
                options = joinOptions
            )
            
            if (result == MeetingError.MEETING_ERROR_SUCCESS) {
                // Meeting joined successfully
                // Zoom SDK will handle the UI
            } else {
                // Handle error
                // Fallback to URL-based joining
                openZoomUrl(sdkData.zoom_meeting_url)
            }
        } catch (e: Exception) {
            // Handle error
            // Fallback to URL-based joining
        }
    }
    
    private fun openZoomUrl(url: String) {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
        startActivity(intent)
    }
}
```

### iOS (Swift)

#### 1. Add SDK via CocoaPods

```ruby
# Podfile
pod 'ZoomVideoSDK', '~> 5.x'
```

#### 2. Initialize SDK

```swift
import ZoomVideoSDK

class ZoomManager {
    func initializeSDK() {
        let initParams = ZoomVideoSDKInitParams()
        initParams.domain = "zoom.us"
        // SDK Key - get from backend for security
        // Never store SDK Secret in app!
        
        ZoomVideoSDK.shareInstance()?.initialize(
            with: initParams,
            completion: { (response: ZoomVideoSDKError) in
                if response == .success {
                    print("Zoom SDK initialized")
                } else {
                    print("Failed to initialize: \(response)")
                }
            }
        )
    }
}
```

#### 3. Join Meeting

```swift
import ZoomVideoSDK

class ZoomMeetingManager {
    func joinMeeting(sessionId: Int, authToken: String) {
        // 1. Get SDK signature from backend
        getSDKSignature(sessionId: sessionId, authToken: authToken) { [weak self] result in
            switch result {
            case .success(let sdkData):
                // 2. Join meeting
                self?.joinWithSDK(sdkData: sdkData)
            case .failure(let error):
                print("Error: \(error)")
                // Fallback to URL
            }
        }
    }
    
    private func getSDKSignature(sessionId: Int, authToken: String, completion: @escaping (Result<SDKData, Error>) -> Void) {
        let url = URL(string: "https://your-api.com/v1/sessions/\(sessionId)/sdk-signature/")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            // Parse response and call completion
        }.resume()
    }
    
    private func joinWithSDK(sdkData: SDKData) {
        let joinParams = ZoomVideoSDKJoinParams()
        joinParams.meetingNumber = sdkData.meeting_number
        joinParams.userName = sdkData.user_name
        joinParams.password = sdkData.meeting_password
        joinParams.signature = sdkData.signature
        
        ZoomVideoSDK.shareInstance()?.joinMeeting(
            with: joinParams,
            completion: { (response: ZoomVideoSDKError) in
                if response == .success {
                    print("Joined meeting successfully")
                } else {
                    print("Failed to join: \(response)")
                    // Fallback to URL
                    if let url = URL(string: sdkData.zoom_meeting_url) {
                        UIApplication.shared.open(url)
                    }
                }
            }
        )
    }
}
```

## Security Best Practices

### ✅ DO:
1. **Always generate signatures server-side** - Never on client
2. **Store SDK Secret only on server** - Never in mobile app
3. **Use HTTPS** - All API calls must be encrypted
4. **Validate user permissions** - Only return host signature to creator
5. **Implement token expiration** - Refresh JWT tokens regularly
6. **Log signature requests** - For security auditing

### ❌ DON'T:
1. **Never expose SDK Secret** - Keep it server-side only
2. **Don't cache signatures** - Generate fresh for each join
3. **Don't return host role to participants** - Security risk
4. **Don't expose start_url** - Not needed for SDK joining
5. **Don't hardcode credentials** - Use environment variables

## Common Mistakes to Avoid

### 1. Using OAuth Credentials Instead of SDK Credentials
```bash
# ❌ WRONG
ZOOM_SDK_KEY=$ZOOM_CLIENT_ID
ZOOM_SDK_SECRET=$ZOOM_CLIENT_SECRET

# ✅ CORRECT
ZOOM_SDK_KEY=your_sdk_key_from_marketplace
ZOOM_SDK_SECRET=your_sdk_secret_from_marketplace
```

### 2. Generating Signature on Client
```typescript
// ❌ WRONG - Never do this!
const signature = generateSignatureOnClient(meetingId, role);

// ✅ CORRECT - Always get from backend
const response = await api.getSDKSignature(sessionId);
const signature = response.data.signature;
```

### 3. Returning Host Signature to All Users
```python
# ❌ WRONG
role = 1  # Always host

# ✅ CORRECT
role = 1 if user == session.initiator else 0
```

### 4. Exposing SDK Secret
```typescript
// ❌ WRONG
const SDK_SECRET = "abc123"; // Never in client code!

// ✅ CORRECT
// SDK Secret stays on server, never sent to client
```

## Troubleshooting

### Issue: "Invalid signature"
- **Cause**: SDK Secret mismatch or wrong timestamp
- **Solution**: Verify SDK credentials in environment variables

### Issue: "Meeting not found"
- **Cause**: Meeting ID format incorrect
- **Solution**: Ensure meeting_number is numeric string

### Issue: "User is not authorized"
- **Cause**: User not a participant in session
- **Solution**: Verify session permissions

### Issue: "Waiting room still appears"
- **Cause**: Using wrong role or URL-based joining
- **Solution**: Use SDK with role=1 for host, ensure SDK is used not URL

## Testing

### Test Host Join (role=1)
1. Create session as User A
2. Start session (generates meeting)
3. Request SDK signature as User A
4. Verify `role=1` and `is_host=true`
5. Join via SDK
6. Meeting should start immediately (no waiting room)

### Test Participant Join (role=0)
1. Create session as User A
2. Start session (generates meeting)
3. Request SDK signature as User B
4. Verify `role=0` and `is_host=false`
5. Join via SDK
6. Should join directly (no waiting room if host already started)

## API Flow Example

```bash
# 1. Create session
POST /v1/sessions/create/
{
  "participant_id": 123
}

# 2. Start session (generates Zoom meeting)
POST /v1/sessions/456/start/

# 3. Get SDK signature (as initiator - gets role=1)
POST /v1/sessions/456/sdk-signature/
Response: {
  "signature": "...",
  "meeting_number": "123456789",
  "role": 1,
  "is_host": true,
  ...
}

# 4. Join via Mobile SDK using signature
# (Mobile app handles this)
```

## Additional Resources

- [Zoom Mobile SDK Documentation](https://marketplace.zoom.us/docs/sdk/native-sdks)
- [Zoom SDK Signature Generation](https://marketplace.zoom.us/docs/sdk/native-sdks/auth)
- [Zoom API Reference](https://marketplace.zoom.us/docs/api-reference/zoom-api/)

## Support

For issues or questions:
1. Check Zoom SDK documentation
2. Verify environment variables are set correctly
3. Check server logs for signature generation errors
4. Ensure SDK credentials are from Marketplace (not OAuth)



