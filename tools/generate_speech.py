from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils.tooling import GenMagicToolMixin, chosen_model, require_text, run, text_param


class GenerateSpeechTool(GenMagicToolMixin, Tool):
    model_category = "audio"
    audio_kind = "speech"

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        yield from run(self._generate(tool_parameters))

    def _generate(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        body: dict[str, Any] = {"input": require_text(tool_parameters, "input", "Text to speak")}
        if model := chosen_model(tool_parameters):
            body["model"] = model
        if voice := text_param(tool_parameters, "voice"):
            body["voice"] = voice
        audio, mime, metering = self.client().speech(body)
        if not audio:
            raise ValueError("GenMagic returned no audio.")
        yield self.file_message(audio, mime, "genmagic-speech")
        yield self.summary_message({"audio_url": metering.media_url, "model": body.get("model", "auto")}, metering)
