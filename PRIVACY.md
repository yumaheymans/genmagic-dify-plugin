# Privacy

The GenMagic plugin sends your requests to GenMagic (https://genmagic.co) so that it can generate text, images, speech, music and video. The plugin itself stores nothing.

## What is sent, and where

- **To GenMagic:** your GenMagic API key (to authenticate), and the inputs of the tool you run: prompts, text to speak, system instructions, the chosen options and model, and any reference image you attach. Each request also names this plugin and its version (the `X-GenMagic-Client` header) so GenMagic can count usage that comes through Dify.
- **To the model provider:** GenMagic passes your inputs to the AI model providers it works with to run the model you chose (for example OpenAI, Google, Anthropic or Black Forest Labs) and produce the result.
- **Back to Dify:** the generated files and text, their hosted URLs, and the cost and remaining balance of the request.

## What GenMagic keeps

GenMagic records each generation in your account history (the prompt, the model, the result's hosted URL, the cost and the time) so that it can bill your credit balance and show you your history, and keeps generated files on its storage so the hosted URLs work. For calls made through this plugin it also records that the call came from the plugin. How long this is kept, who it is shared with, and your rights are in GenMagic's privacy policy: https://genmagic.co/legal/privacy.

## What the plugin does not do

- It does not store your inputs, outputs or API key itself. Dify keeps the API key in its encrypted credential storage and handles the returned files like any other tool output.
- It does not collect analytics, and it does not contact any service other than GenMagic's API and GenMagic's media storage.

## Contact

hello@genmagic.co
