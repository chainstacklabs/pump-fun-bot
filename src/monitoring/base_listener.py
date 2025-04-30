"""
Base class for WebSocket token listeners.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from trading.base import TokenInfo


class BaseTokenListener(ABC):
    """Base abstract class for token listeners."""

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
