"""
Wallet management for Solana transactions.
"""

import base58
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from spl.token.instructions import get_associated_token_address


class Wallet:
    """Manages a Solana wallet for trading operations."""

    def __init__(self, private_key: str):
        """Initialize wallet from private key.

        Args:
            private_key: Base58 encoded private key
        """
        self._private_key = private_key
        self._keypair = self._load_keypair(private_key)

    @property
    def pubkey(self) -> Pubkey:
        """Get the public key of the wallet."""
        return self._keypair.pubkey()

    @property
    def keypair(self) -> Keypair:
        """Get the keypair for signing transactions."""
        return self._keypair

    def get_associated_token_address(self, mint: Pubkey) -> Pubkey:
        """Get the associated token account address for a mint.

        Args:
            mint: Token mint address

        Returns:
            Associated token account address
        """
        return get_associated_token_address(self.pubkey, mint)

    @staticmethod
    def _load_keypair(private_key: str) -> Keypair:
        """Load keypair from private key.

        Args:
            private_key: Base58 encoded private key

        Returns:
            Solana keypair
        """
        private_key_bytes = base58.b58decode(private_key)
        return Keypair.from_bytes(private_key_bytes)
