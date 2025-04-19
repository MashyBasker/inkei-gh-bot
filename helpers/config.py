import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def load_config():
    """
    Load configuration from environment variables or config file.
    Returns a dictionary with configuration values.
    """
    # Check if config is already provided via environment variable
    if os.environ.get("GITHUB_APP_CONFIG"):
        try:
            return json.loads(os.environ.get("GITHUB_APP_CONFIG"))
        except json.JSONDecodeError:
            logger.error("Failed to parse GITHUB_APP_CONFIG environment variable as JSON")
    
    # Try to load from config file
    config_file = Path("config.json")
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
    
    # Default configuration
    return {
        "app_id": os.environ.get("GITHUB_APP_ID", ""),
        "private_key": os.environ.get("GITHUB_PRIVATE_KEY", ""),
        "webhook_secret": os.environ.get("GITHUB_WEBHOOK_SECRET", ""),
        "check_signature": os.environ.get("CHECK_SIGNATURE", "true").lower() == "true",
        "auto_pr_review": os.environ.get("AUTO_PR_REVIEW", "true").lower() == "true",
        "edit_pr_desc": os.environ.get("EDIT_PR_DESC", "true").lower() == "true",
        "api_base_url": os.environ.get("GITHUB_API_URL", "https://api.github.com")
    }

def get_config_value(key, default=None):
    """
    Get a specific configuration value.
    Useful for getting a single config value without loading the entire config.
    """
    config = load_config()
    return config.get(key, default)