from __future__ import annotations

import argparse
from dataclasses import dataclass
import sys

from vibe import __version__
from vibe.core.paths.config_paths import unlock_config_paths

# Configure line buffering for subprocess communication
sys.stdout.reconfigure(line_buffering=True)  # pyright: ignore[reportAttributeAccessIssue]
sys.stderr.reconfigure(line_buffering=True)  # pyright: ignore[reportAttributeAccessIssue]
sys.stdin.reconfigure(line_buffering=True)  # pyright: ignore[reportAttributeAccessIssue]


@dataclass
class Arguments:
    setup: bool
    debug: bool


def parse_arguments() -> Arguments:
    parser = argparse.ArgumentParser(description="Run Mistral Vibe in ACP mode")
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("--setup", action="store_true", help="Setup API key and exit")
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable debug logging for troubleshooting.",
    )
    args = parser.parse_args()
    return Arguments(setup=args.setup, debug=args.debug)


def main() -> None:
    # Set up debug logging if requested
    args = parse_arguments()
    if args.debug:
        import logging
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[
                logging.StreamHandler(),
            ]
        )
        logging.getLogger("vibe").setLevel(logging.DEBUG)
        logging.getLogger("vibe.core.skills.manager").setLevel(logging.DEBUG)

    unlock_config_paths()

    from vibe.acp.acp_agent import run_acp_server
    from vibe.setup.onboarding import run_onboarding

    if args.setup:
        run_onboarding()
        sys.exit(0)
    run_acp_server()


if __name__ == "__main__":
    main()
