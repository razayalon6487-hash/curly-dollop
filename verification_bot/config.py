# config.py
"""Configuration loader for the Discord Verification Bot.
Loads environment variables and provides a simple SETTINGS object.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load the project's own .env regardless of the directory used to launch it.
load_dotenv(Path(__file__).resolve().with_name(".env"))

@dataclass(frozen=True)
class Settings:
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "").strip()
    CLIENT_ID: str = os.getenv("CLIENT_ID", "").strip()
    CLIENT_SECRET: str = os.getenv("CLIENT_SECRET", "").strip()
    DISCORD_PUBLIC_KEY: str = os.getenv("DISCORD_PUBLIC_KEY", "").strip()
    REDIRECT_URI: str = os.getenv("REDIRECT_URI", "").strip()
    OAUTH_BIND_HOST: str = os.getenv("OAUTH_BIND_HOST", "0.0.0.0").strip()
    OAUTH_BIND_PORT: int = int(os.getenv("OAUTH_BIND_PORT", "0"))
    VERIFIED_ROLE_ID: int = int(os.getenv("VERIFIED_ROLE_ID", "0"))
    VERIFICATION_CHANNEL_ID: int = int(os.getenv("VERIFICATION_CHANNEL_ID", "0"))
    LOG_CHANNEL_ID: int = int(os.getenv("LOG_CHANNEL_ID", "0"))
    STATE_EXPIRATION_SECONDS: int = int(os.getenv("STATE_EXPIRATION_SECONDS", "600"))  # 10 minutes default

SETTINGS = Settings()


def validate_settings() -> None:
    """Fail early with actionable errors when required credentials are missing."""
    # Role verification runs entirely in Discord; OAuth credentials are optional.
    required = {"DISCORD_TOKEN": SETTINGS.DISCORD_TOKEN}
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing required environment settings: " + ", ".join(missing)
            + ". Set them in the project's .env file."
        )
