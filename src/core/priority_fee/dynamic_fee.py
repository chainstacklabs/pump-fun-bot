from src.core.client import SolanaClient
from src.utils.logger import get_logger

from . import PriorityFeePlugin

logger = get_logger(__name__)


class DynamicPriorityFee(PriorityFeePlugin):
    """Default dynamic priority fee plugin using getRecentPriorityFee."""

    def __init__(self, client: SolanaClient):
        """
        Initialize the dynamic fee plugin.

        Args:
            client: Solana RPC client for network requests.
        """
        self.client = client

    async def get_priority_fee(self) -> int | None:
        """
        Fetch the recent priority fee from the Solana network.

        Returns:
            Optional[int]: Recent priority fee in lamports, or None if the request fails.
        """
        try:
            client = await self.client.get_client()
            response = await client.get_recent_prioritization_fees()
            if response and response.value:
                return response.value[
                    0
                ].prioritization_fee  # Use the first fee from the list
            return None
        except Exception as e:
            logger.error(f"Failed to fetch recent priority fee: {str(e)}")
            return None
