from solders.pubkey import Pubkey
from spl.token.instructions import BurnParams, CloseAccountParams, burn, close_account

from config import CLEANUP_FORCE_CLOSE_WITH_BURN
from core.client import SolanaClient
from core.priority_fee.manager import PriorityFeeManager
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
        priority_fee_manager: PriorityFeeManager,
        use_priority_fee: bool = False,
    ):
        """
        Args:
            client: Solana RPC client
            wallet: Wallet for signing transactions
        """
        self.client = client
        self.wallet = wallet
        self.priority_fee_manager = priority_fee_manager
        self.use_priority_fee = use_priority_fee

    async def cleanup_ata(self, mint: Pubkey) -> None:
        """
        Attempt to burn any remaining tokens and close the ATA.
        Skips if account doesn't exist or is already empty/closed.
        """
        ata = self.wallet.get_associated_token_address(mint)
        solana_client = await self.client.get_client()

        priority_fee = (
            await self.priority_fee_manager.calculate_priority_fee([ata])
            if self.use_priority_fee
            else None
        )

        try:
            info = await solana_client.get_account_info(ata, encoding="base64")
            if not info.value:
                logger.info(f"ATA {ata} does not exist or already closed.")
                return

            balance = await self.client.get_token_account_balance(ata)
            instructions = []

            if balance > 0 and CLEANUP_FORCE_CLOSE_WITH_BURN:
                logger.info(f"Burning {balance} tokens from ATA {ata} (mint: {mint})...")
                burn_ix = burn(
                    BurnParams(
                        account=ata,
                        mint=mint,
                        owner=self.wallet.pubkey,
                        amount=balance,
                        program_id=SystemAddresses.TOKEN_PROGRAM,
                    )
                )
                instructions.append(burn_ix)

            elif balance > 0:
                logger.info(
                    f"Skipping ATA {ata} with non-zero balance ({balance} tokens) "
                    f"because CLEANUP_FORCE_CLOSE_WITH_BURN is disabled."
                )
                return

            # Include close account instruction
            logger.info(f"Closing ATA: {ata}")
            close_ix = close_account(
                CloseAccountParams(
                    account=ata,
                    dest=self.wallet.pubkey,
                    owner=self.wallet.pubkey,
                    program_id=SystemAddresses.TOKEN_PROGRAM,
                )
            )
            instructions.append(close_ix)

            # Send both burn and close instructions in the same transaction
            if instructions:
                tx_sig = await self.client.build_and_send_transaction(
                    instructions,
                    self.wallet.keypair,
                    skip_preflight=True,
                    priority_fee=priority_fee,
                )
                await self.client.confirm_transaction(tx_sig)
                logger.info(f"Closed successfully: {ata}")

        except Exception as e:
            logger.warning(f"Cleanup failed for ATA {ata}: {e!s}")
