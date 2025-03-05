"""
Base interfaces for trading operations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from solders.pubkey import Pubkey
from solders.signature import Signature


@dataclass
class TokenInfo:
    """Token information."""

    name: str
    symbol: str
    uri: str
    mint: Pubkey
    bonding_curve: Pubkey
    associated_bonding_curve: Pubkey
    user: Pubkey

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenInfo":
        """Create TokenInfo from dictionary.

        Args:
            data: Dictionary with token data

        Returns:
            TokenInfo instance
        """
        return cls(
            name=data["name"],
            symbol=data["symbol"],
            uri=data["uri"],
            mint=Pubkey.from_string(data["mint"]),
            bonding_curve=Pubkey.from_string(data["bondingCurve"]),
            associated_bonding_curve=Pubkey.from_string(data["associatedBondingCurve"]),
            user=Pubkey.from_string(data["user"]),
        )

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "name": self.name,
            "symbol": self.symbol,
            "uri": self.uri,
            "mint": str(self.mint),
            "bondingCurve": str(self.bonding_curve),
            "associatedBondingCurve": str(self.associated_bonding_curve),
            "user": str(self.user),
        }


@dataclass
class TradeResult:
    """Result of a trading operation."""

    success: bool
    tx_signature: str | None = None
    error_message: str | None = None
    amount: float | None = None
    price: float | None = None


class Trader(ABC):
    """Base interface for trading operations."""

    @abstractmethod
    async def execute(self, *args, **kwargs) -> TradeResult:
        """Execute trading operation.

        Returns:
            TradeResult with operation outcome
        """
        pass
