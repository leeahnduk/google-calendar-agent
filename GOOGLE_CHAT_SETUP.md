# 🗣️ Google Chat Integration Setup Guide

## Problem Identified

The OAuth authorization screen only shows Google Drive and Google Calendar permissions but **not Google Chat permissions**. This is because the OAuth scopes in AgentSpace are missing the required Google Chat API scopes.

## ✅ Solution

The Google Chat scopes need to be added to the OAuth authorization configuration in AgentSpace.

### Required Google Chat Scopes

```
https://www.googleapis.com/auth/chat.messages.readonly
https://www.googleapis.com/auth/chat.spaces.readonly
```

## 🛠️ Implementation Steps

### Step 1: Check Current OAuth Configuration

First, verify the current OAuth scopes:

```bash
# Load environment variables (if using .env file)
source .env

# Check current scopes
./scripts/check_oauth_scopes.sh
```

### Step 2: Update OAuth Authorization with Google Chat Scopes

Run the update script to add Google Chat scopes:

```bash
# Update OAuth with Google Chat support
./scripts/update_oauth_with_chat.sh
```

This script will:
- ✅ Delete the existing OAuth authorization
- ✅ Create a new one with Google Chat scopes included
- ✅ Keep all existing scopes (Calendar, Drive, User Info)
- ✅ Add the new Google Chat scopes

### Step 3: Re-authorize in AgentSpace

**IMPORTANT**: After updating the OAuth scopes, you **must re-authorize**:

1. 🔄 In AgentSpace, go to your Meeting Prep Agent
2. 🔐 Click "Authorize" or "Re-authorize"
3. ✅ You should now see **Google Chat permissions** in the consent screen
4. ✅ Accept all permissions including the new Chat scopes

### Step 4: Verify Google Chat Integration

After re-authorization, test the meeting prep functionality to ensure Google Chat integration works.

## 📋 Prerequisites

### 1. Environment Variables Required

Make sure these are set in your `.env` file or environment:

```bash
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
STAGING_BUCKET=gs://your-staging-bucket

# OAuth Configuration  
AUTH_ID=your-auth-id                    # e.g., "meeting-prep-auth"
OAUTH_CLIENT_ID=your-oauth-client-id
OAUTH_CLIENT_SECRET=your-oauth-client-secret

# Agent Configuration
AGENT_DISPLAY_NAME="Meeting Prep Agent"

# Google Chat Integration
GOOGLE_CHAT_ENABLED=true
CHAT_INTEGRATION_PREFERENCE=both        # or "google_chat" or "slack"
```

### 2. Google Cloud APIs to Enable

Ensure these APIs are enabled in your Google Cloud Project:

- ✅ **Google Calendar API**
- ✅ **Google Drive API** 
- ✅ **Google Chat API** ← **This is crucial for Chat integration**
- ✅ **OAuth2 API**

### 3. OAuth Consent Screen Configuration

Your OAuth consent screen must be properly configured:

- ✅ Application name and description
- ✅ Authorized domains (if applicable)
- ✅ Scopes properly configured
- ✅ Test users added (if in testing mode)

## 🐛 Troubleshooting

### Issue: Still don't see Google Chat permissions after update

**Solutions:**
1. **Verify Google Chat API is enabled** in Cloud Console
2. **Check OAuth consent screen** configuration
3. **Confirm CLIENT_ID and CLIENT_SECRET** are correct
4. **Clear browser cache** and try re-authorizing
5. **Wait a few minutes** for changes to propagate

### Issue: "insufficient permissions" error

**Solutions:**
1. **Re-run the authorization update script**
2. **Verify all required APIs are enabled**
3. **Check that gcloud is authenticated**: `gcloud auth login`

### Issue: Chat integration not working after authorization

**Solutions:**
1. **Verify GOOGLE_CHAT_ENABLED=true** in environment
2. **Check CHAT_INTEGRATION_PREFERENCE** setting
3. **Test with a meeting that has Chat conversations**
4. **Review error messages** in the meeting prep output

## 📝 Technical Details

### How OAuth Scopes Work in AgentSpace

AgentSpace uses a centralized OAuth configuration that defines what permissions your agent requests. The scopes are configured through the Discovery Engine API and determine what appears in the Google consent screen.

### Current Full Scope List

After the update, your OAuth authorization will include:

```
# Calendar Access
https://www.googleapis.com/auth/calendar.readonly
https://www.googleapis.com/auth/calendar

# Drive Access  
https://www.googleapis.com/auth/drive.readonly

# User Information
https://www.googleapis.com/auth/userinfo.email
https://www.googleapis.com/auth/userinfo.profile

# Google Chat Access (NEW)
https://www.googleapis.com/auth/chat.messages.readonly
https://www.googleapis.com/auth/chat.spaces.readonly
```

### Google Chat Integration Features

Once properly configured, the meeting prep agent will:

- 🔍 **Search Google Chat spaces** for conversations related to the meeting
- 📝 **Analyze recent messages** from relevant chat spaces
- 🤖 **Use AI to extract key discussion points** from chat context
- 📋 **Include chat insights** in the meeting brief
- 🔗 **Provide direct links** to relevant chat conversations

## 🎯 Expected Result

After completing these steps, when you authorize the agent in AgentSpace, you should see:

```
This will allow agentspace to:
✅ See and download all your Google Drive files
✅ See and download any calendar you can access using your Google Calendar  
✅ Read your Google Chat conversations and messages ← NEW!
```

The meeting prep agent will then be able to include Google Chat context in your meeting briefs! 🎉