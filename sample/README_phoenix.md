# APAC Project Phoenix Agents

This project serves as the agent repository for Project Phoenix. This contains highly relevant and industry ready agents ready for integration to Google Agentspace. Get started with building agents below.  

-----
## ⚠️ Warning

This project is currently a work in progress (WIP). The only automation that can be used already is template using the `make create-agent` command.

If you encounter any issues or unexpected behavior during template generation, please raise a merge request. The source files for the templates are located in the `templates/` directory.

Please do not run any of the `commons` assets directly. They have not yet been configured to integrate yet.

-----

## 🚀 Getting Started

### 1. Clone the Repository

First, clone this repository to your local machine.

```bash
git clone https://gitlab.com/google-cloud-ce/private-communities/apac-project-phoenix-agents/apac-project-phoenix-agents.git
cd apac-project-phoenix-agents
```

Optionally, you may also want to create a dev venv first. You can simply run `make install` on the root directory.

### 2. Generate the Agent Directory

Execute the make create-agent command, providing the desired name for your new agent using the `AGENT_VERTICAL` and`AGENT_NAME` flag. The name should use hyphens for spaces (e.g., `phoenix-agent`).

These are the only values eligible for AGENT_VERTICAL: ['fsi', 'mfg', 'retail', 'telco']

```bash
make create-agent AGENT_VERTICAL="fsi" AGENT_NAME="phoenix-agent"
```

The script will create a new directory (`agents/fsi-phoenix-agent`) with the complete, structured agent repository inside.

-----

## 📂 Generated Directory Structure

**Note**: This directory has been updated to be more compliant with https://github.com/google/adk-samples/tree/main/python/agents. 
Key changes:
- Added a parent directory for the agent 
- Remove configs.py and tools directory for sub_agents
- Introduction of deployment.yaml

The script generates the following directory structure for your new agent. This structure is designed to be modular and scalable.
```
updated-phoenix-agent-template/
├── tests
│   ├── __init__.py
│   └── test_agent.py
├── updated_phoenix_agent_template # main agent logic
│   ├── utils
│   │   ├── utils.py
│   │   └── __init__.py
│   ├── sub_agents
│   │   ├── sub_agent_b
│   │   │   ├── sub_agent.py
│   │   │   ├── prompts.py
│   │   │   └── __init__.py
│   │   ├── sub_agent_a
│   │   │   ├── sub_agent.py
│   │   │   ├── prompts.py
│   │   │   └── __init__.py
│   │   └── __init__.py
│   ├── tools
│   │   ├── __init__.py
│   │   └── tools.py
│   ├── prompts.py
│   ├── config.py
│   ├── __init__.py
│   └── agent.py
├── eval
│   ├── __init__.py
│   └── test_evals.py
├── data
├── .env.example # config for your agents logic
├── deployment.yaml # config for deployment
├── requirements.txt # requirements for your agent
├── README.md
└── __init__.py
```

### Directory Breakdown

  * **`agent.py`**: Defines the main agent's behavior, including its model, tools, and orchestration of sub-agents.
  * **`config.py`**: Uses Pydantic to manage all configurations. It loads values from the `.env` file, providing a structured and type-safe way to handle settings.
  * **`prompts.py`**: Contains the `GLOBAL_INSTRUCTION` and `INSTRUCTION` strings that guide the agent's behavior.
  * **`tools/`**: Contains the `tools.py` file where you define the tools (e.g., functions for API calls, data processing) available to the main agent.
  * **`sub_agents/`**: Each subdirectory represents a specialized sub-agent that can be invoked by the main agent. Each sub-agent can have its own logic, config, prompts, and tools.
  * **`tests/`**: Contains unit tests for your agent's components.
  * **`eval/`**: Contains scripts for evaluating your agent's performance on specific tasks.
  * **`.env`**: Stores all configurations for agents, deployments, integrations, etc.
  * **`README.md`**: A pre-populated README for your new agent project, which you should update with specific details.

### 3. Deployment
First ensure that you have access to the project and have already authenticated.
```bash
gcloud auth application-default login
```
To start the deployment, simply run:
```bash
sh scripts/deploy.sh <agent-name>
# e.g. sh scripts/deploy.sh updated-phoenix-agent-template
```
⚠️ We're still working on getting the deployments to run on service account and to be trigged from the merge request. Please be patient with us as we resolve this!

### 4. Adding your agent to the repo!

The `main` branch is protected so you will need to add your changes via Merge Request. When developing your agent, please create a branch in your local with the name `agent/<agent-name>` for good housekeeping. e.g. `agent/updated-phoenix-agent-template`. 

For all changes to the `agents/` folder, you may merge these changes yourself! No need for maintainers to review. For changes to all other directories, you will need maintainer approval to ensure your changes don't impact other tools. But feel free to raise MRs for all other files if you want to contribute, we'd love to review it!

If you have finalized your agent, or you want to ensure that no one can change anything there without your approval, please add yourself to `CODEOWNERS` under Rule #4. Please don't make changes to another contributor's agent without their permission!