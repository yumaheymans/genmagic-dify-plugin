"""Tool behaviour against a stubbed GenMagic API (no network, no credits).

Run from the plugin root:  python -m unittest discover -s tests
"""

from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dify_plugin.entities.tool import ToolInvokeMessage  # noqa: E402
from dify_plugin.errors.tool import ToolProviderCredentialValidationError  # noqa: E402

import utils.genmagic_client as gm  # noqa: E402
import utils.tooling as tooling  # noqa: E402
from provider.genmagic import GenMagicProvider  # noqa: E402
from tools.check_video import CheckVideoTool  # noqa: E402
from tools.generate_image import GenerateImageTool  # noqa: E402
from tools.generate_music import GenerateMusicTool  # noqa: E402
from tools.generate_speech import GenerateSpeechTool  # noqa: E402
from tools.generate_text import GenerateTextTool  # noqa: E402
import tools.generate_video as generate_video  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\nfake"
MEDIA = "https://tlwdqzfibvgektzgdfqa.supabase.co/storage/v1/object/public/media/x.png"


class FakeResponse:
    def __init__(self, status: int = 200, body: Any = None, headers: dict[str, str] | None = None, content: bytes | None = None):
        self.status_code = status
        self._body = body
        self.headers = headers or {}
        self.content = content if content is not None else (json.dumps(body).encode() if body is not None else b"")

    def json(self) -> Any:
        if self._body is None:
            raise ValueError("no json")
        return self._body

    def iter_content(self, chunk_size: int = 1024):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeApi:
    """Routes requests.request / requests.get to scripted responses and records what was sent."""

    def __init__(self, routes: dict[tuple[str, str], Any]):
        self.routes = routes
        self.calls: list[dict[str, Any]] = []

    def request(self, method, url, headers=None, json=None, params=None, timeout=None):
        path = url.replace(gm.BASE_URL, "")
        self.calls.append({"method": method, "path": path, "headers": headers, "json": json, "params": params})
        route = self.routes[(method, path)]
        return route(self) if callable(route) else route

    def get(self, url, headers=None, timeout=None, stream=False):
        self.calls.append({"method": "DOWNLOAD", "path": url, "headers": headers})
        return self.routes[("DOWNLOAD", url)]


def run_tool(cls, params: dict[str, Any], api: FakeApi) -> list[ToolInvokeMessage]:
    tool = cls.from_credentials({"genmagic_api_key": "gm_test_key"})
    with mock.patch.object(gm.requests, "request", api.request), mock.patch.object(gm.requests, "get", api.get):
        return list(tool.invoke(params))


def of_type(messages: list[ToolInvokeMessage], kind: ToolInvokeMessage.MessageType) -> list[ToolInvokeMessage]:
    return [m for m in messages if m.type == kind]


class ProviderTest(unittest.TestCase):
    def validate(self, response: FakeResponse) -> None:
        api = FakeApi({("GET", "/api/v1/usage"): response})
        with mock.patch.object(gm.requests, "request", api.request):
            GenMagicProvider().validate_credentials({"genmagic_api_key": "gm_test_key"})

    def test_a_valid_key_passes_without_spending(self):
        self.validate(FakeResponse(200, {"object": "usage", "balance_cents": 50}))

    def test_a_rejected_key_explains_how_to_get_one(self):
        with self.assertRaises(ToolProviderCredentialValidationError) as ctx:
            self.validate(FakeResponse(401, {"error": {"code": "invalid_api_key", "message": "Invalid or revoked API key."}}))
        self.assertIn("genmagic.co/developers", str(ctx.exception))

    def test_an_unverified_account_is_told_to_verify(self):
        with self.assertRaises(ToolProviderCredentialValidationError) as ctx:
            self.validate(FakeResponse(403, {"error": {"code": "email_verification_required", "message": "Verify"}}))
        self.assertIn("verify-email", str(ctx.exception))

    def test_an_empty_key_is_refused_before_any_request(self):
        with self.assertRaises(ToolProviderCredentialValidationError):
            GenMagicProvider().validate_credentials({"genmagic_api_key": "  "})


class ImageTest(unittest.TestCase):
    def test_image_returns_a_file_and_a_summary_with_cost(self):
        api = FakeApi({
            ("POST", "/api/v1/images/generations"): FakeResponse(
                200, {"created": 1, "data": [{"url": MEDIA}]}, {"X-Cost-Cents": "6.72", "X-Credits-Remaining": "43.28"}
            ),
            ("DOWNLOAD", MEDIA): FakeResponse(200, None, {"Content-Type": "image/png"}, PNG),
        })
        messages = run_tool(GenerateImageTool, {"prompt": "a cobalt prism", "model": "auto", "size": "1792x1024", "type": "logo"}, api)
        sent = api.calls[0]
        self.assertEqual(sent["json"], {"prompt": "a cobalt prism", "size": "1792x1024", "type": "logo"})  # auto is omitted
        self.assertEqual(sent["headers"]["X-GenMagic-Client"], f"dify-plugin/{gm.PLUGIN_VERSION}")
        self.assertEqual(sent["headers"]["Authorization"], "Bearer gm_test_key")
        blob = of_type(messages, ToolInvokeMessage.MessageType.BLOB)[0]
        self.assertEqual(blob.message.blob, PNG)
        self.assertEqual(blob.meta, {"mime_type": "image/png", "filename": "genmagic-image-1.png"})
        summary = of_type(messages, ToolInvokeMessage.MessageType.JSON)[0].message.json_object
        self.assertEqual(summary["image_urls"], [MEDIA])
        self.assertEqual(summary["cost_usd"], 0.0672)
        self.assertEqual(summary["balance_usd"], 0.4328)

    def test_a_chosen_model_and_reference_image_are_sent(self):
        api = FakeApi({
            ("POST", "/api/v1/images/generations"): FakeResponse(200, {"data": [{"url": "data:image/png;base64," + base64.b64encode(PNG).decode()}]}),
        })
        ref = mock.Mock(mime_type="image/jpeg", blob=b"jpegbytes")
        messages = run_tool(GenerateImageTool, {"prompt": "same bottle, blue", "model": "google/gemini-3.1-flash-image", "reference_image": ref}, api)
        body = api.calls[0]["json"]
        self.assertEqual(body["model"], "google/gemini-3.1-flash-image")
        self.assertEqual(body["image"], "data:image/jpeg;base64," + base64.b64encode(b"jpegbytes").decode())
        # A data URL result is decoded in place, without any download.
        self.assertEqual(of_type(messages, ToolInvokeMessage.MessageType.BLOB)[0].message.blob, PNG)
        self.assertFalse([c for c in api.calls if c["method"] == "DOWNLOAD"])

    def test_a_non_image_reference_is_refused(self):
        api = FakeApi({})
        with self.assertRaisesRegex(ValueError, "must be an image"):
            run_tool(GenerateImageTool, {"prompt": "x", "reference_image": mock.Mock(mime_type="application/pdf", blob=b"%PDF")}, api)

    def test_api_errors_become_clear_messages(self):
        api = FakeApi({
            ("POST", "/api/v1/images/generations"): FakeResponse(402, {"error": {"code": "insufficient_credits", "message": "Not enough credits"}}),
        })
        with self.assertRaisesRegex(ValueError, "balance is too low"):
            run_tool(GenerateImageTool, {"prompt": "x"}, api)


class AudioTest(unittest.TestCase):
    def test_speech_returns_the_audio_file_and_hosted_url(self):
        hosted = "https://tlwdqzfibvgektzgdfqa.supabase.co/storage/v1/object/public/media/a.mp3"
        api = FakeApi({
            ("POST", "/api/v1/audio/speech"): FakeResponse(
                200, None, {"Content-Type": "audio/mpeg", "X-Media-Url": hosted, "X-Cost-Cents": "0.5"}, b"ID3audio"
            ),
        })
        messages = run_tool(GenerateSpeechTool, {"input": "Hello there", "voice": "alloy"}, api)
        self.assertEqual(api.calls[0]["json"], {"input": "Hello there", "voice": "alloy"})
        blob = of_type(messages, ToolInvokeMessage.MessageType.BLOB)[0]
        self.assertEqual((blob.message.blob, blob.meta["filename"]), (b"ID3audio", "genmagic-speech.mp3"))
        summary = of_type(messages, ToolInvokeMessage.MessageType.JSON)[0].message.json_object
        self.assertEqual((summary["audio_url"], summary["cost_usd"]), (hosted, 0.005))

    def test_music_uses_the_music_endpoint(self):
        api = FakeApi({("POST", "/api/v1/audio/music"): FakeResponse(200, None, {"Content-Type": "audio/wav"}, b"RIFFwav")})
        messages = run_tool(GenerateMusicTool, {"prompt": "calm lo-fi for studying"}, api)
        self.assertEqual(of_type(messages, ToolInvokeMessage.MessageType.BLOB)[0].meta["filename"], "genmagic-music.wav")


class VideoTest(unittest.TestCase):
    def setUp(self):
        self.sleep = mock.patch.object(generate_video.time, "sleep", lambda s: None)
        self.sleep.start()

    def tearDown(self):
        self.sleep.stop()

    def test_generate_video_waits_for_the_clip_and_returns_it(self):
        video_url = "https://tlwdqzfibvgektzgdfqa.supabase.co/storage/v1/object/public/media/v.mp4"
        polls = iter([
            FakeResponse(200, {"id": "job1", "status": "processing", "model": "m"}),
            FakeResponse(200, {"id": "job1", "status": "completed", "model": "m", "url": video_url}, {"X-Cost-Cents": "40", "X-Credits-Remaining": "60"}),
        ])
        api = FakeApi({
            ("POST", "/api/v1/videos"): FakeResponse(202, {"id": "job1", "status": "queued", "model": "m"}),
            ("GET", "/api/v1/videos/job1"): lambda _api: next(polls),
            ("DOWNLOAD", video_url): FakeResponse(200, None, {"Content-Type": "video/mp4"}, b"mp4bytes"),
        })
        messages = run_tool(generate_video.GenerateVideoTool, {"prompt": "a paper plane at golden hour", "aspect_ratio": "9:16", "duration": 4}, api)
        self.assertEqual(api.calls[0]["json"], {"prompt": "a paper plane at golden hour", "aspect_ratio": "9:16", "duration": 4})
        blob = of_type(messages, ToolInvokeMessage.MessageType.BLOB)[0]
        self.assertEqual((blob.message.blob, blob.meta["filename"]), (b"mp4bytes", "genmagic-video-job1.mp4"))
        summary = of_type(messages, ToolInvokeMessage.MessageType.JSON)[0].message.json_object
        self.assertEqual((summary["status"], summary["video_url"], summary["cost_usd"]), ("completed", video_url, 0.4))

    def test_a_slow_render_returns_the_job_id_for_check_video(self):
        api = FakeApi({
            ("POST", "/api/v1/videos"): FakeResponse(202, {"id": "job2", "status": "queued", "model": "m"}),
            ("GET", "/api/v1/videos/job2"): FakeResponse(200, {"id": "job2", "status": "processing", "model": "m"}),
        })
        with mock.patch.object(generate_video, "WAIT_SECONDS", 0.0):
            messages = run_tool(generate_video.GenerateVideoTool, {"prompt": "x"}, api)
        texts = [m.message.text for m in of_type(messages, ToolInvokeMessage.MessageType.TEXT)]
        self.assertTrue(any('Check video with id "job2"' in t for t in texts))

    def test_a_failed_render_is_an_error_and_says_nothing_was_charged(self):
        api = FakeApi({("GET", "/api/v1/videos/job3"): FakeResponse(200, {"id": "job3", "status": "failed", "error": "provider timeout"})})
        with self.assertRaisesRegex(ValueError, "Nothing was billed"):
            run_tool(CheckVideoTool, {"id": "job3"}, api)


class TextTest(unittest.TestCase):
    def test_svg_output_is_also_returned_as_a_file(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        api = FakeApi({
            ("POST", "/api/v1/text"): FakeResponse(
                200, {"model": "anthropic/claude-sonnet-5.5", "type": "svg", "text": svg, "usage": {"input_tokens": 10, "output_tokens": 20}}
            ),
        })
        messages = run_tool(GenerateTextTool, {"prompt": "a lighthouse icon", "type": "svg", "model": "auto"}, api)
        self.assertEqual(api.calls[0]["json"], {"prompt": "a lighthouse icon", "type": "svg"})
        self.assertEqual(of_type(messages, ToolInvokeMessage.MessageType.TEXT)[0].message.text, svg)
        blob = of_type(messages, ToolInvokeMessage.MessageType.BLOB)[0]
        self.assertEqual((blob.meta["mime_type"], blob.meta["filename"]), ("image/svg+xml", "genmagic-svg.svg"))

    def test_plain_text_is_not_sent_as_a_type_and_has_no_file(self):
        api = FakeApi({("POST", "/api/v1/text"): FakeResponse(200, {"model": "m", "text": "Hi!"})})
        messages = run_tool(GenerateTextTool, {"prompt": "say hi", "type": "text", "system": "Be brief."}, api)
        self.assertEqual(api.calls[0]["json"], {"prompt": "say hi", "system": "Be brief."})
        self.assertFalse(of_type(messages, ToolInvokeMessage.MessageType.BLOB))


class ModelDropdownTest(unittest.TestCase):
    def setUp(self):
        gm._models_cache.clear()

    def options(self, cls, models: list[dict[str, Any]]):
        api = FakeApi({("GET", "/api/v1/models"): FakeResponse(200, {"object": "list", "data": models})})
        tool = cls.from_credentials({"genmagic_api_key": "gm_test_key"})
        with mock.patch.object(gm.requests, "request", api.request):
            return tool.fetch_parameter_options("model"), api

    def test_auto_comes_first_then_newest_models_with_prices(self):
        options, api = self.options(GenerateImageTool, [
            {"id": "old/one", "name": "Old One", "created": 100, "pricing": {"unit": "image", "usd_per_unit": 0.04}},
            {"id": "new/two", "name": "New Two", "created": 200, "pricing": {"unit": "image", "usd_per_unit": 0.0672}},
        ])
        self.assertEqual(api.calls[0]["params"], {"category": "image"})
        self.assertEqual([o.value for o in options], ["auto", "new/two", "old/one"])
        self.assertEqual(options[1].label.en_us, "New Two · $0.0672/image")

    def test_speech_lists_only_speech_models(self):
        options, _ = self.options(GenerateSpeechTool, [
            {"id": "openai/tts", "name": "TTS", "audio_kind": "speech", "created": 1},
            {"id": "google/lyria", "name": "Lyria", "audio_kind": "music", "created": 2},
        ])
        self.assertEqual([o.value for o in options], ["auto", "openai/tts"])

    def test_video_lists_only_models_that_generate_from_a_prompt(self):
        # GenMagic flags source-media models (video edit, upscale, photo avatars) with
        # text_to_video false; a model without the flag stays listed.
        options, api = self.options(generate_video.GenerateVideoTool, [
            {"id": "lab/maker", "name": "Maker", "created": 3, "capabilities": {"text_to_video": True}},
            {"id": "lab/editor", "name": "Editor", "created": 2, "capabilities": {"text_to_video": False}},
            {"id": "lab/unflagged", "name": "Unflagged", "created": 1, "capabilities": {}},
        ])
        self.assertEqual(api.calls[0]["params"], {"category": "video"})
        self.assertEqual([o.value for o in options], ["auto", "lab/maker", "lab/unflagged"])

    def test_without_a_working_key_only_auto_is_offered(self):
        api = FakeApi({("GET", "/api/v1/models"): FakeResponse(401, {"error": {"code": "invalid_api_key", "message": "bad"}})})
        tool = generate_video.GenerateVideoTool.from_credentials({"genmagic_api_key": "bad"})
        with mock.patch.object(gm.requests, "request", api.request):
            self.assertEqual([o.value for o in tool.fetch_parameter_options("model")], ["auto"])

    def test_text_prices_are_per_million_tokens(self):
        self.assertEqual(
            tooling.price_hint({"pricing": {"unit": "token", "prompt_usd_per_million": 2, "completion_usd_per_million": 10}}),
            "$2.00 in / $10.00 out per 1M tokens",
        )
        self.assertEqual(tooling.price_hint({"pricing": {"unit": "token", "prompt_usd_per_million": 0, "completion_usd_per_million": 0}}), "free")


class MediaSafetyTest(unittest.TestCase):
    def test_media_is_only_downloaded_from_genmagic_hosts(self):
        client = gm.GenMagicClient("k")
        with mock.patch.object(gm.requests, "get") as get:
            self.assertIsNone(client.fetch_media("https://example.com/x.png"))
            self.assertIsNone(client.fetch_media("http://genmagic.co/x.png"))
            get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
