from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from utils.genmagic_client import KEY_HINT, GenMagicClient, GenMagicError


class GenMagicProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        """Check the key against GET /api/v1/usage, which reads the balance and spends nothing."""
        api_key = str(credentials.get("genmagic_api_key") or "").strip()
        if not api_key:
            raise ToolProviderCredentialValidationError(f"A GenMagic API key is required. {KEY_HINT}.")
        try:
            GenMagicClient(api_key).usage()
        except GenMagicError as e:
            raise ToolProviderCredentialValidationError(e.user_message()) from e
