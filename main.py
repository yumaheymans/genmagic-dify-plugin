from dify_plugin import DifyPluginEnv, Plugin

# 240 s: Generate video waits for the clip to finish rendering (see tools/generate_video.py),
# and a music track can take a minute or more. The default 120 s leaves no headroom.
plugin = Plugin(DifyPluginEnv(MAX_REQUEST_TIMEOUT=240))

if __name__ == "__main__":
    plugin.run()
