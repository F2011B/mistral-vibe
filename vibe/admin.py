import sys
import asyncio
from vibe.core.config import VibeConfig, load_config
from vibe.cli.textual_ui.admin_app import AdminApp

def main():
    """Entry point for the Vibe Admin GUI."""
    # Load config
    # We might need to handle args similar to main app for correct workdir
    # For now, simplistic config loading
    config = load_config()

    app = AdminApp(config)
    app.run()

if __name__ == "__main__":
    main()
