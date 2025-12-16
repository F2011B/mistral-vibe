from __future__ import annotations

import base64
import os

import pyperclip
from textual.app import App

_PREVIEW_MAX_LENGTH = 40


def _copy_osc52(text: str) -> None:
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    osc52_seq = f"\033]52;c;{encoded}\a"
    if os.environ.get("TMUX"):
        osc52_seq = f"\033Ptmux;\033{osc52_seq}\033\\"

    with open("/dev/tty", "w") as tty:
        tty.write(osc52_seq)
        tty.flush()


def _shorten_preview(texts: list[str]) -> str:
    dense_text = "⏎".join(texts).replace("\n", "⏎")
    if len(dense_text) > _PREVIEW_MAX_LENGTH:
        return f"{dense_text[: _PREVIEW_MAX_LENGTH - 1]}…"
    return dense_text


def _copy_texts(app: App, text: str, preview_parts: list[str]) -> bool:
    if not text:
        return False

    for copy_fn in [_copy_osc52, pyperclip.copy, app.copy_to_clipboard]:
        try:
            copy_fn(text)
        except Exception:
            pass
        else:
            app.notify(
                f'"{_shorten_preview(preview_parts)}" copied to clipboard',
                severity="information",
                timeout=2,
            )
            return True
    else:
        app.notify(
            "Failed to copy - no clipboard method available",
            severity="warning",
            timeout=3,
        )
        return False


def copy_selection_to_clipboard(app: App) -> None:
    selected_texts: list[str] = []

    for widget in app.query("*"):
        if not hasattr(widget, "text_selection") or not widget.text_selection:
            continue

        selection = widget.text_selection

        try:
            result = widget.get_selection(selection)
        except Exception:
            continue

        if not result:
            continue

        selected_text, _ = result
        if selected_text.strip():
            selected_texts.append(selected_text)

    if not selected_texts:
        return

    combined_text = "\n".join(selected_texts)

    _copy_texts(app, combined_text, selected_texts)


def copy_text_to_clipboard(
    app: App, text: str, preview_label: str | None = None
) -> bool:
    label = preview_label or text
    return _copy_texts(app, text, [label])
