import os
from dataclasses import dataclass


def _get_env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and (value is None or value == ""):
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value or ""


@dataclass(frozen=True)
class Settings:
    # Core
    google_cloud_project: str
    google_cloud_location: str
    staging_bucket: str
    auth_id: str
    agent_display_name: str

    # AI Models
    root_agent_model: str
    sub_agent_model: str

    # Behavior
    brief_lead_minutes: int
    historical_lookback_days: int

    # Slack
    slack_bot_token: str
    slack_signing_secret: str


def load_settings() -> Settings:
    return Settings(
        google_cloud_project=_get_env("GOOGLE_CLOUD_PROJECT", required=True),
        google_cloud_location=_get_env("GOOGLE_CLOUD_LOCATION", default="us-central1"),
        staging_bucket=_get_env("STAGING_BUCKET", required=True),
        auth_id=_get_env("AUTH_ID", required=True),
        agent_display_name=_get_env("AGENT_DISPLAY_NAME", default="Meeting Prep Agent"),
        root_agent_model=_get_env("ROOT_AGENT_MODEL", default="gemini-2.5-flash"),
        sub_agent_model=_get_env("SUB_AGENT_MODEL", default="gemini-2.5-flash"),
        brief_lead_minutes=int(_get_env("BRIEF_LEAD_MINUTES", default="30")),
        historical_lookback_days=int(_get_env("HISTORICAL_LOOKBACK_DAYS", default="90")),
        slack_bot_token=_get_env("SLACK_BOT_TOKEN", default=""),
        slack_signing_secret=_get_env("SLACK_SIGNING_SECRET", default=""),
    )
