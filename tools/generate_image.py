from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils.tooling import GenMagicToolMixin, chosen_model, reference_image_data_url, require_text, run, text_param


class GenerateImageTool(GenMagicToolMixin, Tool):
    model_category = "image"

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        yield from run(self._generate(tool_parameters))

    def _generate(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        body: dict[str, Any] = {"prompt": require_text(tool_parameters, "prompt", "A prompt")}
        if model := chosen_model(tool_parameters):
            body["model"] = model
        if size := text_param(tool_parameters, "size"):
            body["size"] = size
        if text_param(tool_parameters, "type") == "logo":
            body["type"] = "logo"
        if reference := reference_image_data_url(tool_parameters.get("reference_image")):
            body["image"] = reference

        client = self.client()
        result, metering = client.image(body)
        urls: list[str] = []
        for index, item in enumerate(result.get("data") or [], start=1):
            url = str(item.get("url") or "")
            b64 = item.get("b64_json")
            source = url or (f"data:image/png;base64,{b64}" if b64 else "")
            if not source:
                continue
            if url and not url.startswith("data:"):
                urls.append(url)
            media = client.fetch_media(source)
            if media:
                data, mime = media
                yield self.file_message(data, mime, f"genmagic-image-{index}")
            elif url:
                yield self.create_image_message(url)
        if not urls and not result.get("data"):
            raise ValueError("GenMagic returned no image.")
        yield self.summary_message({"image_urls": urls or None, "model": body.get("model", "auto")}, metering)
