# GenMagic

**Author:** genmagic
**Version:** 0.0.1
**Type:** tool
**Source:** https://github.com/yumaheymans/genmagic-dify-plugin

Generate images, video, music, speech and text in your Dify workflows and agents with 500+ AI models from the major labs (OpenAI, Google, Anthropic, Black Forest Labs, ByteDance, Alibaba, xAI and many more), all through one [GenMagic](https://genmagic.co/?utm_source=dify-marketplace&utm_medium=integration&utm_campaign=agent-platforms) API key and one pay-as-you-go balance. Each tool's model list is loaded live from GenMagic, so newly released models appear without a plugin update.

**GenMagic is a paid service.** The plugin is free, but every generation is billed to your GenMagic credit balance at the model's listed price. A new account gets a one-time $0.50 starter balance once its email address is verified.

This plugin is built and maintained by GenMagic.

## Tools

| Tool | What it does | Output |
|---|---|---|
| Generate image | Text to image with any image model. Optional reference image (image-to-image) and a logo mode for brand marks. Sizes: square, wide, tall. | Image file(s), hosted URL, cost |
| Generate video | Text to video with any video model, in 16:9, 9:16 or 1:1. Waits up to about three minutes for the clip. | Video file, hosted URL, cost; or a job id if the render takes longer |
| Check video | Returns a video started with Generate video once it is ready. | Video file, hosted URL, cost; or the current status |
| Generate music | An original track from a description of genre, mood, instruments and tempo. | Audio file, hosted URL, cost |
| Generate speech | Text to speech, read word for word, with an optional voice. | Audio file, hosted URL, cost |
| Generate text | Plain text, prose, code, an SVG graphic or a complete HTML page, with any text model. | Text; SVG and HTML also as files; token usage and cost |

Every tool has a **Model** dropdown listing that kind of model with its price. Leave it on **Auto** to let GenMagic choose.

## Setup

1. Create an account at [genmagic.co](https://genmagic.co/developers?utm_source=dify-marketplace&utm_medium=integration&utm_campaign=agent-platforms) and verify your email address, which unlocks the $0.50 starter balance.
2. In GenMagic, open **Settings** and create an API key.
3. In Dify, install the GenMagic plugin, open **Tools**, choose **GenMagic**, click **Authorize**, and paste the API key. The key is checked against your GenMagic balance; nothing is billed.
4. Add any GenMagic tool to a workflow or an agent.

## Usage notes

- **Credits.** Each generation is billed to your GenMagic credit balance at the model's listed price, the same balance you use in the GenMagic studio and API. Checking your key, loading model lists and checking a video's status are free. Each tool's JSON output includes `cost_usd` and `balance_usd` where GenMagic reports them.
- **Video.** A clip renders asynchronously. Generate video waits up to about three minutes. If the clip is not ready by then, the tool returns its job `id`; pass it to **Check video** later. A video is billed once, when it completes, and a failed render is not billed.
- **Files.** Images, audio and video come back as Dify files, so later nodes can use them, and as hosted URLs on GenMagic's storage.
- **Brand personalization.** If you turned on brand personalization in your GenMagic account, outputs follow your brand automatically.

## Requirements and connection

- A GenMagic account with a verified email address and an API key.
- Outbound HTTPS access from your Dify installation to `genmagic.co` (the API) and `tlwdqzfibvgektzgdfqa.supabase.co` (GenMagic's media storage, used to download generated files).
- Dify 1.5.1 or later (the model dropdowns use dynamic options).

## Privacy

Prompts, reference images and text you send go to GenMagic, which runs them on the model provider you choose. See [PRIVACY.md](PRIVACY.md) and [GenMagic's privacy policy](https://genmagic.co/legal/privacy).

## Support

Questions or problems: hello@genmagic.co, or open an issue at https://github.com/yumaheymans/genmagic-dify-plugin/issues.
