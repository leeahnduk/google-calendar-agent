# 🎯 Google Chat Scope Selection Guide

## What You Should See After Clicking "Add or remove scopes"

### Step 1: Scope Selection Dialog
After clicking "Add or remove scopes", you should see a dialog with:
- A search box at the top
- Categories of APIs on the left
- Available scopes listed

### Step 2: Find Google Chat Scopes

**Option A: Search Method**
1. In the search box, type: `chat`
2. Look for scopes that contain:
   - `chat.messages.readonly`
   - `chat.spaces.readonly`

**Option B: Browse Method**
1. Look for "Google Chat API" in the left sidebar
2. Click on it to see available Chat scopes
3. Select the readonly scopes

### Step 3: What to Look For

You need to find and select these exact scopes:
- ✅ `https://www.googleapis.com/auth/chat.messages.readonly`
  - Description: "See your messages in Google Chat"
- ✅ `https://www.googleapis.com/auth/chat.spaces.readonly`  
  - Description: "See your Chat conversations and participants"

### 🚨 If You Don't See Google Chat Scopes

This could mean:

1. **Google Chat API not fully enabled**
   - Go to: https://console.cloud.google.com/apis/library/chat.googleapis.com?project=aiproject-429506
   - Make sure it shows "API enabled"
   - Wait 5-10 minutes after enabling

2. **Wrong API version**
   - Make sure you're looking at "Google Chat API" not "Hangouts Chat API"

3. **Scope restrictions**
   - Some scopes might not be available for external use
   - Try looking for "Google Workspace" related scopes

### 🎯 Alternative Scope Names to Try

If the exact scopes above don't appear, look for:
- Any scope with "chat" and "readonly"
- "Google Workspace Chat" scopes
- "Hangouts Chat" scopes (older name)

### Step 4: After Adding Scopes

1. Click "Update" to save
2. Wait 5-10 minutes for changes to propagate
3. Go back to AgentSpace and try authorization again

## 🐛 Troubleshooting

### If No Chat Scopes Appear At All:

1. **Enable Google Chat API first:**
   ```
   Go to: APIs & Services > Library
   Search: "Google Chat API"
   Click: Enable (if not already enabled)
   Wait: 10 minutes
   ```

2. **Check API quotas:**
   ```
   Go to: APIs & Services > Quotas
   Search: "Chat"
   Make sure quotas are not zero
   ```

3. **Try alternative approach:**
   - Look for "Google Workspace Admin SDK"
   - Look for "Directory API" scopes
   - Sometimes Chat permissions are bundled with other Google Workspace APIs

### If You See Chat Scopes But Can't Add Them:

1. Check if your OAuth consent screen is in "Testing" mode
2. Make sure your account is added as a test user
3. Some scopes require domain verification

## 📸 What Success Looks Like

After successfully adding the scopes, you should see:
- The two Google Chat scopes listed in your "non-sensitive scopes" table
- When you authorize in AgentSpace, you'll see Chat permissions in the consent screen

## 📞 Need Help?

If you're stuck at the scope selection step, let me know:
1. What scopes you can see when you search for "chat"
2. What categories appear in the left sidebar
3. Any error messages you encounter

The key is finding those two readonly Chat scopes and adding them to your OAuth consent screen!