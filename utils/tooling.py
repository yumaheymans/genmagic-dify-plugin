"""What every GenMagic tool shares: the client for the configured key, the live model
dropdown, and turning GenMagic's responses into Dify messages (files plus a JSON summary)."""

from __future__ import annotations

import base64
from collections.abc import Generator
from typing import Any

from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.tool import ToolInvokeMessage

from utils.genmagic_client import GenMagicClient, GenMagicError, Metering, filename_for

AUTO = "auto"
MAX_REFERENCE_BYTES = 10 * 1024 * 1024


class GenMagicToolMixin:
    """Mixed into each dify_plugin Tool; these attributes come from Tool itself."""

    runtime: Any
    create_blob_message: Any
    create_json_message: Any
    create_text_message: Any

    #: The GenMagic catalog category this tool's model dropdown lists (text, image, audio, video).
    model_category: str | None = None
    #: For audio: "speech" or "music", the kind of audio model the dropdown lists.
    audio_kind: str | None = None

    def client(self) -> GenMagicClient:
        return GenMagicClient(str((self.runtime.credentials or {}).get("genmagic_api_key") or ""))

    # ------------------------------------------------------------------ model dropdown
    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        if parameter != "model" or not self.model_category:
            return []
        options = [
            ParameterOption(
                value=AUTO,
                label=I18nObject(
                    en_US="Auto: GenMagic picks the model",
                    zh_Hans="自动：由 GenMagic 选择模型",
                    ja_JP="自動：GenMagic がモデルを選択",
                    pt_BR="Automático: o GenMagic escolhe o modelo",
                ),
            )
        ]
        try:
            models = self.client().models(self.model_category)
        except GenMagicError:
            # No key yet, or GenMagic unreachable: Auto still works, so offer it alone.
            return options
        for m in models:
            if self.audio_kind and m.get("audio_kind") not in (None, self.audio_kind):
                continue
            if self.model_category == "video" and not makes_video_from_prompt(m):
                continue
            name = str(m.get("name") or m["id"])
            price = price_hint(m)
            label = f"{name} · {price}" if price else name
            options.append(ParameterOption(value=str(m["id"]), label=I18nObject(en_US=label)))
        return options

    # ------------------------------------------------------------------ outputs
    def file_message(self, data: bytes, mime: str, stem: str) -> ToolInvokeMessage:
        return self.create_blob_message(blob=data, meta={"mime_type": mime, "filename": filename_for(stem, mime)})

    def summary_message(self, payload: dict[str, Any], metering: Metering | None = None) -> ToolInvokeMessage:
        body = {k: v for k, v in payload.items() if v is not None}
        if metering:
            body.update(metering.as_dict())
        return self.create_json_message(body)


def makes_video_from_prompt(model: dict[str, Any]) -> bool:
    """Whether a video model can make a clip from a text prompt, the only input Generate video
    sends. GenMagic flags models that edit, upscale or animate media you supply with
    capabilities.text_to_video = false and refuses them, so they are left out of the dropdown.
    A model without the flag is kept: the API is the one authority on what it can run."""
    return (model.get("capabilities") or {}).get("text_to_video") is not False


def chosen_model(tool_parameters: dict[str, Any]) -> str | None:
    """The model id to send, or None to let GenMagic choose (Auto, or nothing picked)."""
    model = str(tool_parameters.get("model") or "").strip()
    return None if not model or model == AUTO else model


def text_param(tool_parameters: dict[str, Any], name: str) -> str | None:
    value = tool_parameters.get(name)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def require_text(tool_parameters: dict[str, Any], name: str, label: str) -> str:
    value = text_param(tool_parameters, name)
    if not value:
        raise ValueError(f"{label} is required.")
    return value


def reference_image_data_url(file: Any) -> str | None:
    """A Dify file parameter as the data URL GenMagic's image endpoint accepts, or None when absent."""
    if not file:
        return None
    if isinstance(file, list):
        file = file[0] if file else None
        if not file:
            return None
    mime = str(getattr(file, "mime_type", None) or "")
    if not mime.startswith("image/"):
        raise ValueError("The reference image must be an image file (PNG, JPEG or WebP).")
    data = file.blob
    if len(data) > MAX_REFERENCE_BYTES:
        raise ValueError("The reference image is larger than 10 MB.")
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def run(generate: Generator[ToolInvokeMessage, None, None]) -> Generator[ToolInvokeMessage, None, None]:
    """Run a tool body, turning a GenMagic API error into one clear message for the user or agent."""
    try:
        yield from generate
    except GenMagicError as e:
        raise ValueError(e.user_message()) from e


def price_hint(model: dict[str, Any]) -> str | None:
    """A short price for the dropdown label, from the catalog's own pricing (never estimated here)."""
    pricing = model.get("pricing") or {}
    unit = pricing.get("unit")
    if unit == "token":
        p, c = pricing.get("prompt_usd_per_million"), pricing.get("completion_usd_per_million")
        if isinstance(p, (int, float)) and isinstance(c, (int, float)):
            return "free" if p == 0 and c == 0 else f"${_money(p)} in / ${_money(c)} out per 1M tokens"
        return None
    usd = pricing.get("usd_per_unit")
    if isinstance(usd, (int, float)) and unit in ("image", "minute", "second", "generation"):
        return f"${_money(usd)}/{unit}"
    return None


def _money(value: float) -> str:
    return f"{value:.2f}" if value >= 1 else f"{value:.4g}"
