"""Shared by Generate video and Check video: turn a GenMagic video job into Dify messages."""

from collections.abc import Generator
from typing import Any

from dify_plugin.entities.tool import ToolInvokeMessage

from utils.genmagic_client import GenMagicClient, Metering
from utils.tooling import GenMagicToolMixin


def video_messages(
    tool: GenMagicToolMixin,
    client: GenMagicClient,
    job: dict[str, Any],
    metering: Metering | None,
) -> Generator[ToolInvokeMessage, None, None]:
    status = str(job.get("status") or "")
    job_id = str(job.get("id") or "")
    summary: dict[str, Any] = {"id": job_id, "status": status, "model": job.get("model")}

    if status == "completed":
        url = str(job.get("url") or "")
        summary["video_url"] = url or None
        media = client.fetch_media(url) if url else None
        if media:
            data, mime = media
            yield tool.file_message(data, mime, f"genmagic-video-{job_id or 'clip'}")
        elif url:
            yield tool.create_link_message(url)
        yield tool.summary_message(summary, metering)
        return

    if status == "failed":
        raise ValueError(f"The video could not be generated: {job.get('error') or 'the render failed'}. Nothing was billed for it.")

    yield tool.summary_message(summary)
    yield tool.create_text_message(
        f'The video is still {status or "rendering"}. Use Check video with id "{job_id}" to get it when it is ready '
        "(it is billed once, when it completes)."
    )
