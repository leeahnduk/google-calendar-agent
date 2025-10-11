# 🗑️ Deleting Agents in AgentSpace

This guide documents the process for deleting agents from Google Cloud AgentSpace using the Discovery Engine API.

## Prerequisites

- Google Cloud SDK (`gcloud`) installed and authenticated
- Proper permissions for Discovery Engine API
- Agent details (project, engine, assistant information)

## Environment Variables Required

Ensure your `.env` file contains:
```bash
GOOGLE_CLOUD_PROJECT_NUMBER=671247654914
AS_APP=agentspace-dev_1744685873939
```

## Step 1: List Existing Agents

First, list all agents to find the specific agent IDs you want to delete:

```bash
source .env && curl -X GET \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT_NUMBER}" \
  "https://discoveryengine.googleapis.com/v1alpha/projects/${GOOGLE_CLOUD_PROJECT_NUMBER}/locations/global/collections/default_collection/engines/${AS_APP}/assistants/default_assistant/agents"
```

### Response Format

The response will contain an array of agents with the following structure:
```json
{
  "agents": [
    {
      "name": "projects/671247654914/locations/global/collections/default_collection/engines/agentspace-dev_1744685873939/assistants/default_assistant/agents/AGENT_ID",
      "displayName": "Agent Display Name",
      "description": "Agent description",
      "createTime": "2025-10-10T03:42:22.101268Z",
      "state": "ENABLED"
    }
  ]
}
```

## Step 2: Extract Agent IDs

From the response, identify the **AGENT_ID** (the numeric value at the end of the `name` field) for agents you want to delete.

**Example Agent IDs found:**
- `meeting-prep-demo`: **13034195125674301636**
- `meeting-prep-agent`: **18092393091501628415**

## Step 3: Delete Specific Agents

Use the DELETE method with the specific agent ID:

```bash
source .env && curl -X DELETE \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT_NUMBER}" \
  "https://discoveryengine.googleapis.com/v1alpha/projects/${GOOGLE_CLOUD_PROJECT_NUMBER}/locations/global/collections/default_collection/engines/${AS_APP}/assistants/default_assistant/agents/AGENT_ID"
```

Replace `AGENT_ID` with the actual numeric ID from Step 2.

## Step 4: Verify Deletion

Successful deletion returns a response like:
```json
{
  "name": "projects/671247654914/locations/global/collections/default_collection/engines/agentspace-dev_1744685873939/assistants/default_assistant/agents/AGENT_ID/operations/delete-agent-OPERATION_ID",
  "done": true
}
```

## Example: Complete Deletion Process

### 1. List agents and find target IDs
```bash
# List all agents
source .env && curl -X GET \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT_NUMBER}" \
  "https://discoveryengine.googleapis.com/v1alpha/projects/${GOOGLE_CLOUD_PROJECT_NUMBER}/locations/global/collections/default_collection/engines/${AS_APP}/assistants/default_assistant/agents" \
  | jq '.agents[] | {name: .name, displayName: .displayName}'
```

### 2. Delete specific agents
```bash
# Delete meeting-prep-demo (ID: 13034195125674301636)
source .env && curl -X DELETE \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT_NUMBER}" \
  "https://discoveryengine.googleapis.com/v1alpha/projects/${GOOGLE_CLOUD_PROJECT_NUMBER}/locations/global/collections/default_collection/engines/${AS_APP}/assistants/default_assistant/agents/13034195125674301636"

# Delete meeting-prep-agent (ID: 18092393091501628415)
source .env && curl -X DELETE \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT_NUMBER}" \
  "https://discoveryengine.googleapis.com/v1alpha/projects/${GOOGLE_CLOUD_PROJECT_NUMBER}/locations/global/collections/default_collection/engines/${AS_APP}/assistants/default_assistant/agents/18092393091501628415"
```

## API Endpoint Structure

**Base URL Pattern:**
```
https://discoveryengine.googleapis.com/v1alpha/projects/{PROJECT_NUMBER}/locations/global/collections/default_collection/engines/{ENGINE_ID}/assistants/{ASSISTANT_ID}/agents/{AGENT_ID}
```

**Parameters:**
- `PROJECT_NUMBER`: Google Cloud project number (e.g., 671247654914)
- `ENGINE_ID`: AgentSpace engine ID (e.g., agentspace-dev_1744685873939)
- `ASSISTANT_ID`: Usually `default_assistant`
- `AGENT_ID`: Numeric agent identifier to delete

## Important Notes

⚠️ **Warning**: Agent deletion is **permanent** and cannot be undone.

✅ **Best Practices**:
- Always list agents first to confirm the correct IDs
- Double-check agent names and descriptions before deletion
- Keep a backup of agent configurations if needed
- Test with non-production agents first

🔒 **Permissions Required**:
- `discoveryengine.agents.delete`
- Access to the specific project and engine

## Troubleshooting

### Common Issues

1. **403 Forbidden**: Check IAM permissions
2. **404 Not Found**: Verify agent ID and project details
3. **401 Unauthorized**: Refresh gcloud auth token

### Debug Commands
```bash
# Check current auth status
gcloud auth list

# Refresh access token
gcloud auth application-default print-access-token

# Verify project configuration
echo $GOOGLE_CLOUD_PROJECT_NUMBER
echo $AS_APP
```

---

**📅 Created**: October 10, 2025
**🔧 Last Updated**: October 10, 2025
**📋 Use Case**: AgentSpace agent management and cleanup