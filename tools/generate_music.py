from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils.tooling import GenMagicToolMixin, chosen_model, require_text, run


class GenerateMusicTool(GenMagicToolMixin, Tool):
    model_category = "audio"
    audio_kind = "music"

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        yield from run(self._generate(tool_parameters))

    def _generate(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        body: dict[str, Any] = {"prompt": require_text(tool_parameters, "prompt", "A prompt")}
        if model := chosen_model(tool_parameters):
            body["model"] = model
        audio, mime, metering = self.client().music(body)
        if not audio:
            raise ValueError("GenMagic returned no audio.")
        yield self.file_message(audio, mime, "genmagic-music")
        yield self.summary_message({"audio_url": metering.media_url, "model": body.get("model", "auto")}, metering)
