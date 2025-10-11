#!/bin/bash

# 🗑️ Interactive AgentSpace Agent Deletion Script
# Based on deleting_agent.md documentation
#
# This script allows you to:
# - List all agents with index numbers
# - Select multiple agents for deletion
# - Confirm before deletion
# - Delete selected agents safely

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

# Function to check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."

    # Check if .env file exists
    if [[ ! -f ".env" ]]; then
        print_error ".env file not found. Please ensure you're in the correct directory."
        exit 1
    fi

    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI not found. Please install Google Cloud SDK."
        exit 1
    fi

    # Check if jq is installed
    if ! command -v jq &> /dev/null; then
        print_error "jq not found. Please install jq for JSON parsing."
        print_info "Install with: brew install jq (macOS) or apt-get install jq (Ubuntu)"
        exit 1
    fi

    print_success "Prerequisites check passed"
}

# Function to load environment variables
load_env() {
    print_info "Loading environment variables..."
    source .env

    if [[ -z "$GOOGLE_CLOUD_PROJECT_NUMBER" ]] || [[ -z "$AS_APP" ]]; then
        print_error "Required environment variables not found:"
        print_error "GOOGLE_CLOUD_PROJECT_NUMBER and AS_APP must be set in .env file"
        exit 1
    fi

    print_success "Environment variables loaded"
    print_info "Project: $GOOGLE_CLOUD_PROJECT_NUMBER"
    print_info "App: $AS_APP"
}

# Function to get access token
get_access_token() {
    print_info "Getting access token..."
    ACCESS_TOKEN=$(gcloud auth print-access-token 2>/dev/null)
    if [[ -z "$ACCESS_TOKEN" ]]; then
        print_error "Failed to get access token. Please run 'gcloud auth login'"
        exit 1
    fi
    print_success "Access token obtained"
}

# Function to fetch and parse agents
fetch_agents() {
    print_info "Fetching agents from AgentSpace..."

    local response=$(curl -s -X GET \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        -H "X-Goog-User-Project: $GOOGLE_CLOUD_PROJECT_NUMBER" \
        "https://discoveryengine.googleapis.com/v1alpha/projects/$GOOGLE_CLOUD_PROJECT_NUMBER/locations/global/collections/default_collection/engines/$AS_APP/assistants/default_assistant/agents")

    # Check if response is valid JSON
    if ! echo "$response" | jq empty 2>/dev/null; then
        print_error "Failed to fetch agents. Response:"
        echo "$response"
        exit 1
    fi

    # Parse agents data
    AGENTS_DATA=$(echo "$response" | jq -r '.agents[]? | "\(.name)|\(.displayName)|\(.description // "No description")|\(.state)"')

    if [[ -z "$AGENTS_DATA" ]]; then
        print_warning "No agents found in AgentSpace"
        exit 0
    fi

    print_success "Agents fetched successfully"
}

# Function to display agents with index numbers
display_agents() {
    print_info "Available agents:"
    echo ""
    printf "${CYAN}%-5s %-30s %-20s %-50s %-10s${NC}\n" "INDEX" "DISPLAY NAME" "AGENT ID" "DESCRIPTION" "STATE"
    echo "$(printf '%.0s-' {1..120})"

    local index=1
    while IFS='|' read -r name displayName description state; do
        # Extract agent ID from name (last part after the last slash)
        local agentId=$(echo "$name" | rev | cut -d'/' -f1 | rev)

        # Truncate long descriptions
        local truncated_desc=$(echo "$description" | cut -c1-47)
        if [[ ${#description} -gt 47 ]]; then
            truncated_desc="${truncated_desc}..."
        fi

        printf "%-5s %-30s %-20s %-50s %-10s\n" "$index" "$displayName" "$agentId" "$truncated_desc" "$state"

        # Store agent data for later use
        AGENT_NAMES[$index]="$displayName"
        AGENT_IDS[$index]="$agentId"
        AGENT_FULL_NAMES[$index]="$name"
        AGENT_DESCRIPTIONS[$index]="$description"
        AGENT_STATES[$index]="$state"

        ((index++))
    done <<< "$AGENTS_DATA"

    TOTAL_AGENTS=$((index - 1))
    echo ""
    print_info "Total agents: $TOTAL_AGENTS"
}

# Function to get user selection
get_user_selection() {
    echo ""
    print_warning "⚠️  WARNING: Agent deletion is PERMANENT and cannot be undone!"
    echo ""
    print_info "Enter the index numbers of agents you want to delete (comma-separated)"
    print_info "Example: 1,3,5 or just 2 for single agent"
    echo ""
    read -p "Enter your selection (or 'q' to quit): " user_input

    if [[ "$user_input" == "q" ]] || [[ "$user_input" == "Q" ]]; then
        print_info "Operation cancelled by user"
        exit 0
    fi

    # Parse user input
    IFS=',' read -ra SELECTED_INDICES <<< "$user_input"

    # Validate selections
    VALID_SELECTIONS=()
    for i in "${SELECTED_INDICES[@]}"; do
        # Remove whitespace
        i=$(echo "$i" | xargs)

        # Check if it's a number
        if ! [[ "$i" =~ ^[0-9]+$ ]]; then
            print_error "Invalid selection: '$i' is not a number"
            return 1
        fi

        # Check if it's within range
        if [[ $i -lt 1 ]] || [[ $i -gt $TOTAL_AGENTS ]]; then
            print_error "Invalid selection: $i is out of range (1-$TOTAL_AGENTS)"
            return 1
        fi

        VALID_SELECTIONS+=($i)
    done

    if [[ ${#VALID_SELECTIONS[@]} -eq 0 ]]; then
        print_error "No valid selections provided"
        return 1
    fi

    return 0
}

# Function to show confirmation
show_confirmation() {
    echo ""
    print_warning "You are about to delete the following agents:"
    echo ""
    printf "${RED}%-5s %-30s %-20s %-50s${NC}\n" "INDEX" "DISPLAY NAME" "AGENT ID" "DESCRIPTION"
    echo "$(printf '%.0s-' {1..110})"

    for index in "${VALID_SELECTIONS[@]}"; do
        local truncated_desc=$(echo "${AGENT_DESCRIPTIONS[$index]}" | cut -c1-47)
        if [[ ${#AGENT_DESCRIPTIONS[$index]} -gt 47 ]]; then
            truncated_desc="${truncated_desc}..."
        fi

        printf "${RED}%-5s %-30s %-20s %-50s${NC}\n" "$index" "${AGENT_NAMES[$index]}" "${AGENT_IDS[$index]}" "$truncated_desc"
    done

    echo ""
    print_warning "This action is IRREVERSIBLE!"
    echo ""
    read -p "Are you sure you want to delete these ${#VALID_SELECTIONS[@]} agent(s)? (type 'YES' to confirm): " confirmation

    if [[ "$confirmation" != "YES" ]]; then
        print_info "Operation cancelled by user"
        exit 0
    fi
}

# Function to delete agents
delete_agents() {
    print_info "Starting deletion process..."
    echo ""

    local success_count=0
    local fail_count=0

    for index in "${VALID_SELECTIONS[@]}"; do
        local agent_name="${AGENT_NAMES[$index]}"
        local agent_id="${AGENT_IDS[$index]}"

        print_info "Deleting agent $index: $agent_name (ID: $agent_id)"

        local delete_response=$(curl -s -X DELETE \
            -H "Authorization: Bearer $ACCESS_TOKEN" \
            -H "Content-Type: application/json" \
            -H "X-Goog-User-Project: $GOOGLE_CLOUD_PROJECT_NUMBER" \
            "https://discoveryengine.googleapis.com/v1alpha/projects/$GOOGLE_CLOUD_PROJECT_NUMBER/locations/global/collections/default_collection/engines/$AS_APP/assistants/default_assistant/agents/$agent_id")

        # Check if deletion was successful
        if echo "$delete_response" | jq -e '.done == true' >/dev/null 2>&1; then
            print_success "✓ Successfully deleted: $agent_name"
            ((success_count++))
        else
            print_error "✗ Failed to delete: $agent_name"
            print_error "Response: $delete_response"
            ((fail_count++))
        fi

        # Small delay between deletions
        sleep 1
    done

    echo ""
    print_info "=== DELETION SUMMARY ==="
    print_success "Successfully deleted: $success_count agents"
    if [[ $fail_count -gt 0 ]]; then
        print_error "Failed to delete: $fail_count agents"
    fi
    print_info "Total processed: $((success_count + fail_count)) agents"
}

# Main function
main() {
    echo ""
    print_info "🗑️  AgentSpace Agent Deletion Tool"
    print_info "=================================="
    echo ""

    # Declare associative arrays
    declare -A AGENT_NAMES
    declare -A AGENT_IDS
    declare -A AGENT_FULL_NAMES
    declare -A AGENT_DESCRIPTIONS
    declare -A AGENT_STATES

    # Run all steps
    check_prerequisites
    load_env
    get_access_token
    fetch_agents
    display_agents

    # User interaction loop
    while true; do
        if get_user_selection; then
            show_confirmation
            delete_agents
            break
        else
            echo ""
            print_warning "Please try again with valid selections"
        fi
    done

    echo ""
    print_success "Agent deletion process completed!"
}

# Run main function
main "$@"