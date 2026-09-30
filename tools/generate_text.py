from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils.tooling import GenMagicToolMixin, chosen_model, require_text, run, text_param

# Output types GenMagic renders as an artifact, and the file each one is also returned as.
TYPED_OUTPUTS = {"writing": None, "code": None, "svg": "image/svg+xml", "website": "text/html"}


class GenerateTextTool(GenMagicToolMixin, Tool):
    model_category = "text"

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        yield from run(self._generate(tool_parameters))

    def _generate(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        body: dict[str, Any] = {"prompt": require_text(tool_parameters, "prompt", "A prompt")}
        if model := chosen_model(tool_parameters):
            body["model"] = model
        output = text_param(tool_parameters, "type")
        if output in TYPED_OUTPUTS:
            body["type"] = output
        if system := text_param(tool_parameters, "system"):
            body["system"] = system

        result, metering = self.client().text(body)
        text = str(result.get("text") or "")
        if not text:
            raise ValueError("GenMagic returned no text.")
        yield self.create_text_message(text)
        file_mime = TYPED_OUTPUTS.get(output or "")
        if file_mime:
            yield self.file_message(text.encode("utf-8"), file_mime, f"genmagic-{output}")
        yield self.summary_message(
            {"model": result.get("model"), "type": result.get("type"), "usage": result.get("usage")},
            metering,
        )
