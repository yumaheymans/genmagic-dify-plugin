from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils.video_result import video_messages
from utils.tooling import GenMagicToolMixin, require_text, run


class CheckVideoTool(GenMagicToolMixin, Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        yield from run(self._check(tool_parameters))

    def _check(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        job_id = require_text(tool_parameters, "id", "A video job id")
        client = self.client()
        job, metering = client.get_video(job_id)
        yield from video_messages(self, client, job, metering)
