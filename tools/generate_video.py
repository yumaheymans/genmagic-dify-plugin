import time
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils.video_result import video_messages
from utils.tooling import GenMagicToolMixin, chosen_model, require_text, run, text_param

# How long to wait for the render inside one tool call. main.py allows 240 s per request, so
# this leaves room for the final download; a slower clip is finished with Check video.
WAIT_SECONDS = 180
POLL_SECONDS = 5


class GenerateVideoTool(GenMagicToolMixin, Tool):
    model_category = "video"

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        yield from run(self._generate(tool_parameters))

    def _generate(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        body: dict[str, Any] = {"prompt": require_text(tool_parameters, "prompt", "A prompt")}
        if model := chosen_model(tool_parameters):
            body["model"] = model
        if aspect_ratio := text_param(tool_parameters, "aspect_ratio"):
            body["aspect_ratio"] = aspect_ratio
        duration = tool_parameters.get("duration")
        if isinstance(duration, (int, float)) and duration > 0:
            body["duration"] = int(duration)

        client = self.client()
        job = client.create_video(body)
        job_id = str(job.get("id") or "")
        if not job_id:
            raise ValueError("GenMagic did not return a video job id.")

        deadline = time.monotonic() + WAIT_SECONDS
        metering = None
        while job.get("status") not in ("completed", "failed") and time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)
            job, metering = client.get_video(job_id)
        yield from video_messages(self, client, job, metering)
