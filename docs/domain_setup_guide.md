# Domain Setup Guide for Google OAuth

This guide will help you configure your GoDaddy domain for Google OAuth integration.

## Prerequisites
- Domain purchased from GoDaddy
- Server IP: `44.220.158.223`
- Access to GoDaddy DNS management
- Access to Google Cloud Console

## Step 1: Configure DNS in GoDaddy

1. **Log in to GoDaddy**
   - Go to https://www.godaddy.com/
   - Sign in to your account

2. **Access DNS Management**
   - Go to "My Products" → Find your domain → Click "DNS" or "Manage DNS"

3. **Add A Record**
   - Click "Add" or "+" to add a new record
   - **Type:** A
   - **Name:** 
     - Use `@` for root domain (e.g., `yourdomain.com`)
     - OR use `api` for subdomain (e.g., `api.yourdomain.com`)
   - **Value:** `44.220.158.223`
   - **TTL:** 600 (or leave default)
   - Click "Save"

4. **Wait for DNS Propagation**
   - DNS changes can take 5 minutes to 48 hours
   - Usually takes 15-30 minutes
   - Test with: `ping yourdomain.com` or `nslookup yourdomain.com`

## Step 2: Update Django Settings

### Option A: Using Environment Variables (Recommended)

Create or update your `.env` file in the project root:

```env
# Your domain name (comma-separated if multiple)
DOMAIN_NAME=yourdomain.com,api.yourdomain.com

# Google OAuth redirect base URL
# Use HTTP if no SSL, HTTPS if you have SSL certificate
GOOGLE_OAUTH_REDIRECT_BASE_URL=http://yourdomain.com
# OR for subdomain:
# GOOGLE_OAUTH_REDIRECT_BASE_URL=http://api.yourdomain.com
```

### Option B: Direct Configuration

Update `matchmate/settings.py`:

```python
ALLOWED_HOSTS = [
    # ... existing hosts ...
    'yourdomain.com',
    'api.yourdomain.com',  # if using subdomain
]

GOOGLE_OAUTH_REDIRECT_BASE_URL = 'http://yourdomain.com'  # or https:// if you have SSL
```

**Important:** 
- Use `http://` if you don't have an SSL certificate
- Use `https://` if you have SSL/HTTPS configured

## Step 3: Add Redirect URI to Google Cloud Console

1. **Go to Google Cloud Console**
   - https://console.cloud.google.com/
   - Navigate to: **APIs & Services** → **Credentials**

2. **Edit Your OAuth 2.0 Client**
   - Click on your OAuth 2.0 Client ID
   - Scroll to **"Authorized redirect URIs"**

3. **Add Your Domain Redirect URI**
   - Click **"+ Add URI"**
   - Enter: `http://yourdomain.com/oauth/callback/`
   - OR if using subdomain: `http://api.yourdomain.com/oauth/callback/`
   - **Important:** Include the trailing slash `/`
   - Click **"Save"**

4. **Remove Invalid IP Address URI** (if present)
   - Delete: `http://44.220.158.223/oauth/callback/` (this won't work)

## Step 4: Verify DNS is Working

Before proceeding, verify your domain points to your server:

```bash
# Test DNS resolution
ping yourdomain.com
# Should show: 44.220.158.223

# Or use nslookup
nslookup yourdomain.com
# Should show: 44.220.158.223
```

## Step 5: Test the OAuth Flow

1. **Restart Your Django Server**
   ```bash
   # On your server
   python manage.py runserver 0.0.0.0:8000
   # Or restart your production server (gunicorn, uwsgi, etc.)
   ```

2. **Test the OAuth Endpoint**
   - Make a GET request to: `http://yourdomain.com/api/google/login/`
   - Include your Bearer token
   - Check the response - it should show your domain in `redirect_uri`

3. **Complete OAuth Flow**
   - Open the `auth_url` from the response in a browser
   - Complete Google OAuth consent
   - Should redirect to: `http://yourdomain.com/oauth/callback/`

## Step 6: (Optional) Set Up SSL/HTTPS

For production, you should use HTTPS:

1. **Get SSL Certificate**
   - Use Let's Encrypt (free): https://letsencrypt.org/
   - Or use your hosting provider's SSL

2. **Update Settings**
   ```python
   GOOGLE_OAUTH_REDIRECT_BASE_URL = 'https://yourdomain.com'
   ```

3. **Update Google Cloud Console**
   - Change redirect URI to: `https://yourdomain.com/oauth/callback/`

## Troubleshooting

### DNS Not Working
- Wait longer (up to 48 hours)
- Check DNS record is correct in GoDaddy
- Clear DNS cache: `ipconfig /flushdns` (Windows) or `sudo dscacheutil -flushcache` (Mac)

### OAuth Still Failing
- Verify redirect URI in Google Cloud Console matches exactly (including trailing slash)
- Check `ALLOWED_HOSTS` includes your domain
- Verify `GOOGLE_OAUTH_REDIRECT_BASE_URL` is set correctly
- Check server logs for errors

### Domain Not Accessible
- Verify server firewall allows port 80 (HTTP) or 443 (HTTPS)
- Check server is running and accessible via IP
- Verify DNS propagation with `nslookup` or `dig`

## Example Configuration

If your domain is `matchmate.com`:

**DNS Record:**
- Type: A
- Name: @
- Value: 44.220.158.223

**Django Settings (.env):**
```env
DOMAIN_NAME=matchmate.com
GOOGLE_OAUTH_REDIRECT_BASE_URL=http://matchmate.com
```

**Google Cloud Console:**
- Redirect URI: `http://matchmate.com/oauth/callback/`

If using subdomain `api.matchmate.com`:

**DNS Record:**
- Type: A
- Name: api
- Value: 44.220.158.223

**Django Settings (.env):**
```env
DOMAIN_NAME=api.matchmate.com
GOOGLE_OAUTH_REDIRECT_BASE_URL=http://api.matchmate.com
```

**Google Cloud Console:**
- Redirect URI: `http://api.matchmate.com/oauth/callback/`
