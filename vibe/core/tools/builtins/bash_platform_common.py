from __future__ import annotations

import os


def get_common_env() -> dict[str, str]:
    return {
        **os.environ,
        "CI": "true",
        "NONINTERACTIVE": "1",
        "NO_TTY": "1",
        "NO_COLOR": "1",
    }
