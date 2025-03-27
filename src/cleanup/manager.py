from solders.pubkey import Pubkey
from spl.token.instructions import BurnParams, CloseAccountParams, burn, close_account

from config import CLEANUP_WITHOUT_PRIORITY_FEE
from core.client import SolanaClient
from core.pubkeys import SystemAddresses
from core.wallet import Wallet
from utils.logger import get_logger

logger = get_logger(__name__)


class AccountCleanupManager:
    """Handles safe cleanup of token accounts (ATA) after trading sessions."""

    def __init__(
        self,
        client: SolanaClient,
        wallet: Wallet,
    ):
        """
        Args:
            client: Solana RPC client
            wallet: Wallet for signing transactions
        """
        self.client = client
        self.wallet = wallet
        self.use_priority_fee = not CLEANUP_WITHOUT_PRIORITY_FEE

    async def cleanup_ata(self, mint: Pubkey) -> None:
        """
        Attempt to burn any remaining tokens and close the ATA.
        Skips if account doesn't exist or is already empty/closed.
        """
        ata = self.wallet.get_associated_token_address(mint)
        solana_client = await self.client.get_client()

        try:
            info = await solana_client.get_account_info(ata)
            if not info.value:
                logger.info(f"ATA {ata} does not exist or already closed.")
                return

            balance = await self.client.get_token_account_balance(ata)
            if balance > 0:
                logger.info(f"⚠️ Burning {balance} tokens from ATA {ata} (mint: {mint})...")
                burn_ix = burn(
                    BurnParams(
                        account=ata,
                        mint=mint,
                        owner=self.wallet.pubkey,
                        amount=balance,
                        program_id=SystemAddresses.TOKEN_PROGRAM,
                    )
                )
                await self.client.build_and_send_transaction(
                    [burn_ix],
                    self.wallet.keypair,
                    skip_preflight=True,
                    priority_fee=None if not self.use_priority_fee else 0,
                )
                logger.info(f"✅ Burned successfully from ATA {ata}")

            logger.info(f"Closing ATA: {ata}")
            close_ix = close_account(
                CloseAccountParams(
                    account=ata,
                    dest=self.wallet.pubkey,
                    owner=self.wallet.pubkey,
                    program_id=SystemAddresses.TOKEN_PROGRAM,
                )
            )
            tx_sig = await self.client.build_and_send_transaction(
                [close_ix],
                self.wallet.keypair,
                skip_preflight=True,
                priority_fee=None if not self.use_priority_fee else 0,
            )
            await self.client.confirm_transaction(tx_sig)
            logger.info(f"✅ Closed successfully: {ata}")

        except Exception as e:
            logger.warning(f"⚠️ Cleanup failed for ATA {ata}: {e!s}")
