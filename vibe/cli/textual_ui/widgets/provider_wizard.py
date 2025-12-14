from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from vibe.core.config import Backend, ModelConfig, ProviderConfig, VibeConfig


def _normalize_backend(value: str | None) -> Backend:
    if not value:
        return Backend.GENERIC
    lowered = value.strip().lower()
    if lowered == "mistral":
        return Backend.MISTRAL
    return Backend.GENERIC


def _parse_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


class ModelWizard(ModalScreen[ModelConfig | None]):
    """Lightweight wizard to collect a single model entry."""

    DEFAULT_TEMP = "0.2"
    DEFAULT_PRICE = "0.0"

    def __init__(
        self,
        provider_name: str | None,
        provider_choices: Iterable[str],
    ) -> None:
        super().__init__()
        self._provider_name = provider_name or ""
        self._provider_choices = ", ".join(sorted(provider_choices))
        self._feedback: Static | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="model-wizard"):
            yield Static("Add Model", classes="wizard-title")
            helper = (
                "Enter a model name and alias. Provider must match an existing provider."
            )
            if self._provider_choices:
                helper += f" Known providers: {self._provider_choices}"
            yield Static(helper, classes="wizard-help")

            self.name_input = Input(placeholder="model name (e.g. my-model-1)")
            self.alias_input = Input(placeholder="model alias (used in UI)")
            self.provider_input = Input(
                placeholder="provider (e.g. mistral)",
                value=self._provider_name,
            )
            self.temp_input = Input(
                placeholder=f"temperature (default {self.DEFAULT_TEMP})",
                value=self.DEFAULT_TEMP,
            )
            self.input_price_input = Input(
                placeholder="input price per million tokens (optional)",
                value=self.DEFAULT_PRICE,
            )
            self.output_price_input = Input(
                placeholder="output price per million tokens (optional)",
                value=self.DEFAULT_PRICE,
            )

            yield self.name_input
            yield self.alias_input
            yield self.provider_input
            yield self.temp_input
            yield self.input_price_input
            yield self.output_price_input

            self._feedback = Static("", classes="wizard-feedback")
            yield self._feedback

            with Horizontal():
                yield Button("Cancel", id="cancel-model", variant="error")
                yield Button("Save Model", id="save-model", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "cancel-model":
                self.dismiss(None)
            case "save-model":
                model = self._build_model()
                if model is None:
                    return
                self.dismiss(model)

    def _build_model(self) -> ModelConfig | None:
        name = (self.name_input.value or "").strip()
        alias = (self.alias_input.value or "").strip() or name
        provider = (self.provider_input.value or "").strip()

        if not name or not provider:
            if self._feedback:
                self._feedback.update("Model name and provider are required.")
                self._feedback.add_class("error")
            return None

        temperature = _parse_float(self.temp_input.value, float(self.DEFAULT_TEMP))
        input_price = _parse_float(self.input_price_input.value, float(self.DEFAULT_PRICE))
        output_price = _parse_float(
            self.output_price_input.value, float(self.DEFAULT_PRICE)
        )

        try:
            return ModelConfig(
                name=name,
                provider=provider,
                alias=alias,
                temperature=temperature,
                input_price=input_price,
                output_price=output_price,
            )
        except Exception as exc:
            if self._feedback:
                self._feedback.update(f"Invalid model configuration: {exc}")
                self._feedback.add_class("error")
            return None


@dataclass(slots=True)
class ProviderDraft:
    provider: ProviderConfig
    models: list[ModelConfig] = field(default_factory=list)


class ProviderWizard(ModalScreen[ProviderDraft]):
    """Wizard to collect a provider and any associated models."""

    class Submitted(Message):
        def __init__(self, draft: ProviderDraft) -> None:
            super().__init__()
            self.draft = draft

    def __init__(self, config: VibeConfig) -> None:
        super().__init__()
        self._config = config
        self._models: list[ModelConfig] = []
        self._model_list: Static | None = None
        self._feedback: Static | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="provider-wizard"):
            yield Static("Add Provider", classes="wizard-title")
            yield Static(
                "Provide an API base, env var, backend, and any models to register.",
                classes="wizard-help",
            )

            self.name_input = Input(placeholder="Provider name (e.g. openrouter)")
            self.api_base_input = Input(
                placeholder="API base URL (e.g. https://api.openrouter.ai/v1)"
            )
            self.api_key_env_input = Input(
                placeholder="Environment variable for API key (e.g. OPENROUTER_API_KEY)"
            )
            self.backend_input = Input(
                placeholder="Backend (mistral or generic)", value="generic"
            )
            self.api_style_input = Input(
                placeholder="API style (default: openai)", value="openai"
            )

            yield self.name_input
            yield self.api_base_input
            yield self.api_key_env_input
            yield self.backend_input
            yield self.api_style_input

            self._model_list = Static("No models added yet.", classes="wizard-help")
            yield self._model_list

            self._feedback = Static("", classes="wizard-feedback")
            yield self._feedback

            with Horizontal():
                yield Button("Add Model", id="add-model", variant="primary")
                yield Button("Save Provider", id="save-provider", variant="success")
                yield Button("Cancel", id="cancel-provider", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "cancel-provider":
                self.dismiss(None)
            case "add-model":
                self._launch_model_wizard()
            case "save-provider":
                draft = self._build_draft()
                if draft is None:
                    return
                self.app.post_message(self.Submitted(draft))
                self.dismiss(draft)

    def _launch_model_wizard(self) -> None:
        def _capture(model: ModelConfig | None) -> None:
            if model is None:
                return
            existing_aliases = {m.alias for m in self._models}
            if model.alias in existing_aliases:
                self._models = [m for m in self._models if m.alias != model.alias]
            self._models.append(model)
            self._update_model_list()

        self.app.push_screen(
            ModelWizard(
                provider_name=(self.name_input.value or "").strip(),
                provider_choices=[p.name for p in self._config.providers],
            ),
            callback=_capture,
            wait_for_dismiss=False,
        )

    def _update_model_list(self) -> None:
        if not self._model_list:
            return
        if not self._models:
            self._model_list.update("No models added yet.")
            return
        lines = [
            f"- {model.alias} ({model.name}) on {model.provider}"
            for model in self._models
        ]
        self._model_list.update("\n".join(lines))

    def _build_draft(self) -> ProviderDraft | None:
        name = (self.name_input.value or "").strip()
        api_base = (self.api_base_input.value or "").strip()
        api_key_env = (self.api_key_env_input.value or "").strip()
        backend = _normalize_backend(self.backend_input.value)
        api_style = (self.api_style_input.value or "").strip() or "openai"

        if not name or not api_base:
            if self._feedback:
                self._feedback.update("Provider name and API base are required.")
                self._feedback.add_class("error")
            return None

        try:
            provider = ProviderConfig(
                name=name,
                api_base=api_base,
                api_key_env_var=api_key_env,
                backend=backend,
                api_style=api_style,
            )
        except Exception as exc:
            if self._feedback:
                self._feedback.update(f"Invalid provider configuration: {exc}")
                self._feedback.add_class("error")
            return None

        return ProviderDraft(provider=provider, models=list(self._models))
