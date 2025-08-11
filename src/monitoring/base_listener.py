"""
Base class for WebSocket token listeners - now platform-agnostic.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from interfaces.core import Platform, TokenInfo


class BaseTokenListener(ABC):
    """Base abstract class for token listeners - now platform-agnostic."""

    def __init__(self, platform: Platform | None = None):
        """Initialize the listener with optional platform specification.

        Args:
            platform: Platform to monitor (if None, monitor all platforms)
        """
        self.platform = platform

    @abstractmethod
    async def listen_for_tokens(
        self,
        token_callback: Callable[[TokenInfo], Awaitable[None]],
        match_string: str | None = None,
        creator_address: str | None = None,
    ) -> None:
        """
        Listen for new token creations.

        Args:
            token_callback: Callback function for new tokens
            match_string: Optional string to match in token name/symbol
            creator_address: Optional creator address to filter by
        """
        pass

    def should_process_token(self, token_info: TokenInfo) -> bool:
        """Check if a token should be processed based on platform filter.

        Args:
            token_info: Token information

        Returns:
            True if token should be processed
        """
        if self.platform is None:
            return True  # Process all platforms
        return token_info.platform == self.platform
