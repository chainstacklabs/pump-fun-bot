"""
Buy operations for pump.fun tokens.
"""

import struct
from typing import Final

from solders.instruction import AccountMeta, Instruction
from solders.pubkey import Pubkey
from spl.token.instructions import create_idempotent_associated_token_account

from core.client import SolanaClient
from core.curve import BondingCurveManager
from core.priority_fee.manager import PriorityFeeManager
from core.pubkeys import (
    LAMPORTS_PER_SOL,
    TOKEN_DECIMALS,
    PumpAddresses,
    SystemAddresses,
)
from core.wallet import Wallet
from trading.base import TokenInfo, Trader, TradeResult
from utils.logger import get_logger

logger = get_logger(__name__)

# Discriminator for the buy instruction
EXPECTED_DISCRIMINATOR: Final[bytes] = struct.pack("<Q", 16927863322537952870)


class TokenBuyer(Trader):
    """Handles buying tokens on pump.fun."""

    def __init__(
        self,
        client: SolanaClient,
        wallet: Wallet,
        curve_manager: BondingCurveManager,
        priority_fee_manager: PriorityFeeManager,
        amount: float,
        slippage: float = 0.01,
        max_retries: int = 5,
        extreme_fast_token_amount: int = 0,
        extreme_fast_mode: bool = False,
    ):
        """Initialize token buyer.

        Args:
            client: Solana client for RPC calls
            wallet: Wallet for signing transactions
            curve_manager: Bonding curve manager
            amount: Amount of SOL to spend
            slippage: Slippage tolerance (0.01 = 1%)
            max_retries: Maximum number of retry attempts
            extreme_fast_token_amount: Amount of token to buy if extreme fast mode is enabled
            extreme_fast_mode: If enabled, avoid fetching associated bonding curve state
        """
        self.client = client
        self.wallet = wallet
        self.curve_manager = curve_manager
        self.priority_fee_manager = priority_fee_manager
        self.amount = amount
        self.slippage = slippage
        self.max_retries = max_retries
        self.extreme_fast_mode = extreme_fast_mode
        self.extreme_fast_token_amount = extreme_fast_token_amount

    async def execute(self, token_info: TokenInfo, *args, **kwargs) -> TradeResult:
        """Execute buy operation.

        Args:
            token_info: Token information

        Returns:
            TradeResult with buy outcome
        """
        try:
            # Convert amount to lamports
            amount_lamports = int(self.amount * LAMPORTS_PER_SOL)

            if self.extreme_fast_mode:
                # Skip the wait and directly calculate the amount
                token_amount = self.extreme_fast_token_amount
                token_price_sol = self.amount / token_amount
                #logger.info(f"EXTREME FAST Mode: Buying {token_amount} tokens.")
            else:
                # Regular behavior with RPC call
                curve_state = await self.curve_manager.get_curve_state(token_info.bonding_curve)
                token_price_sol = curve_state.calculate_price()
                token_amount = self.amount / token_price_sol

            # Calculate maximum SOL to spend with slippage
            max_amount_lamports = int(amount_lamports * (1 + self.slippage))

            associated_token_account = self.wallet.get_associated_token_address(
                token_info.mint
            )

            tx_signature = await self._send_buy_transaction(
                token_info,
                associated_token_account,
                token_amount,
                max_amount_lamports,
            )

            logger.info(
                f"Buying {token_amount:.6f} tokens at {token_price_sol:.8f} SOL per token"
            )
            logger.info(
                f"Total cost: {self.amount:.6f} SOL (max: {max_amount_lamports / LAMPORTS_PER_SOL:.6f} SOL)"
            )

            success = await self.client.confirm_transaction(tx_signature)

            if success:
                # Get actual execution data from bonding curve balance changes
                actual_price, actual_tokens = await self._get_actual_execution_price(tx_signature, token_info)
                
                logger.info(f"Buy transaction confirmed: {tx_signature}")
                logger.info(f"Actual price paid to bonding curve: {actual_price:.8f} SOL per token")
                
                return TradeResult(
                    success=True,
                    tx_signature=tx_signature,
                    amount=actual_tokens,      # Actual tokens received
                    price=actual_price,        # Actual price based on bonding curve SOL flow
                )
            else:
                return TradeResult(
                    success=False,
                    error_message=f"Transaction failed to confirm: {tx_signature}",
                )

        except Exception as e:
            logger.error(f"Buy operation failed: {e!s}")
            return TradeResult(success=False, error_message=str(e))

    async def _send_buy_transaction(
        self,
        token_info: TokenInfo,
        associated_token_account: Pubkey,
        token_amount: float,
        max_amount_lamports: int,
    ) -> str:
        """Send buy transaction.

        Args:
            token_info: Token information
            associated_token_account: User's token account
            token_amount: Amount of tokens to buy
            max_amount_lamports: Maximum SOL to spend in lamports

        Returns:
            Transaction signature

        Raises:
            Exception: If transaction fails after all retries
        """
        accounts = [
            AccountMeta(
                pubkey=PumpAddresses.GLOBAL, is_signer=False, is_writable=False
            ),
            AccountMeta(pubkey=PumpAddresses.FEE, is_signer=False, is_writable=True),
            AccountMeta(pubkey=token_info.mint, is_signer=False, is_writable=False),
            AccountMeta(
                pubkey=token_info.bonding_curve, is_signer=False, is_writable=True
            ),
            AccountMeta(
                pubkey=token_info.associated_bonding_curve,
                is_signer=False,
                is_writable=True,
            ),
            AccountMeta(
                pubkey=associated_token_account, is_signer=False, is_writable=True
            ),
            AccountMeta(pubkey=self.wallet.pubkey, is_signer=True, is_writable=True),
            AccountMeta(
                pubkey=SystemAddresses.PROGRAM, is_signer=False, is_writable=False
            ),
            AccountMeta(
                pubkey=SystemAddresses.TOKEN_PROGRAM, is_signer=False, is_writable=False
            ),
            AccountMeta(
                pubkey=token_info.creator_vault, is_signer=False, is_writable=True
            ),
            AccountMeta(
                pubkey=PumpAddresses.EVENT_AUTHORITY, is_signer=False, is_writable=False
            ),
            AccountMeta(
                pubkey=PumpAddresses.PROGRAM, is_signer=False, is_writable=False
            ),
        ]

        # Prepare idempotent create ATA instruction: it will not fail if ATA already exists
        idempotent_ata_ix = create_idempotent_associated_token_account(
            self.wallet.pubkey,
            self.wallet.pubkey,
            token_info.mint,
            SystemAddresses.TOKEN_PROGRAM
        )

        # Prepare buy instruction data
        token_amount_raw = int(token_amount * 10**TOKEN_DECIMALS)
        data = (
            EXPECTED_DISCRIMINATOR
            + struct.pack("<Q", token_amount_raw)
            + struct.pack("<Q", max_amount_lamports)
        )
        buy_ix = Instruction(PumpAddresses.PROGRAM, data, accounts)

        try:
            return await self.client.build_and_send_transaction(
                [idempotent_ata_ix, buy_ix],
                self.wallet.keypair,
                skip_preflight=True,
                max_retries=self.max_retries,
                priority_fee=await self.priority_fee_manager.calculate_priority_fee(
                    self._get_relevant_accounts(token_info)
                ),
            )
        except Exception as e:
            logger.error(f"Buy transaction failed: {e!s}")
            raise


    async def _get_actual_execution_price(self, tx_signature: str, token_info: TokenInfo) -> tuple[float, float]:
        """Get actual execution price from bonding curve SOL balance changes."""
        try:
            client = await self.client.get_client()

            tx_response = await client.get_transaction(
                tx_signature, 
                encoding="jsonParsed",
                commitment="confirmed",
                max_supported_transaction_version=0
            )
            
            if not tx_response.value or not tx_response.value.transaction:
                raise ValueError("Transaction not found")
                
            meta = tx_response.value.transaction.meta
            if not meta or not meta.pre_balances or not meta.post_balances:
                raise ValueError("Transaction balance data not found")
                
            # Get accounts - they're ParsedAccountTxStatus objects, need to extract pubkey
            accounts = tx_response.value.transaction.transaction.message.account_keys
            
            # Find bonding curve account index in the transaction
            bonding_curve_index = None
            for i, account in enumerate(accounts):
                # Extract pubkey from ParsedAccountTxStatus object
                account_pubkey = str(account.pubkey) if hasattr(account, 'pubkey') else str(account)
                
                if account_pubkey == str(token_info.bonding_curve):
                    bonding_curve_index = i
                    break
                    
            if bonding_curve_index is None:
                raise ValueError("Bonding curve not found in transaction accounts")
                
            pre_balance_lamports = meta.pre_balances[bonding_curve_index]
            post_balance_lamports = meta.post_balances[bonding_curve_index]

            sol_sent_to_curve = (post_balance_lamports - pre_balance_lamports) / LAMPORTS_PER_SOL
            
            if sol_sent_to_curve <= 0:
                raise ValueError(f"No SOL sent to bonding curve: {sol_sent_to_curve}")
            
            tokens_received = await self._get_tokens_received_from_tx(tx_response, token_info)
            
            if tokens_received == 0:
                raise ValueError("Cannot compute execution price: zero tokens received")
            actual_price = sol_sent_to_curve / tokens_received
            
            logger.info(f"Bonding curve received: {sol_sent_to_curve:.6f} SOL")
            logger.info(f"We received: {tokens_received:.6f} tokens")
            logger.info(f"Actual execution price: {actual_price:.8f} SOL per token")
            
            return actual_price, tokens_received
            
        except Exception as e:
            logger.warning(f"Failed to get actual execution price from bonding curve: {e}")
            # Fallback to EXTREME_FAST estimate
            tokens_received = self.extreme_fast_token_amount if self.extreme_fast_mode else self.amount / await self.curve_manager.calculate_price(token_info.bonding_curve)
            if tokens_received == 0:
               logger.error("Fallback failed – unable to determine tokens received")
               return 0.0, 0.0
            return self.amount / tokens_received, tokens_received


    async def _get_tokens_received_from_tx(self, tx_response, token_info: TokenInfo) -> float:
        """Extract tokens received from transaction token balance changes."""
        meta = tx_response.value.transaction.meta
        
        pre_token_balance = 0
        post_token_balance = 0
        
        wallet_str = str(self.wallet.pubkey)
        mint_str = str(token_info.mint)
        
        if meta.pre_token_balances:
            for balance in meta.pre_token_balances:
                # Convert to string for comparison
                balance_owner = str(balance.owner) if hasattr(balance, 'owner') else str(getattr(balance, 'owner', ''))
                balance_mint = str(balance.mint) if hasattr(balance, 'mint') else str(getattr(balance, 'mint', ''))
                
                if balance_owner == wallet_str and balance_mint == mint_str:
                    try:
                        # Try multiple ways to get the amount
                        if hasattr(balance, 'ui_token_amount'):
                            amount_obj = balance.ui_token_amount
                            if hasattr(amount_obj, 'amount') and amount_obj.amount is not None:
                                pre_token_balance = int(amount_obj.amount)
                            elif hasattr(amount_obj, 'ui_amount') and amount_obj.ui_amount is not None:
                                pre_token_balance = int(float(amount_obj.ui_amount) * (10**TOKEN_DECIMALS))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error parsing pre-token balance: {e}")
                    break
                    
        # Check post-token balances  
        if meta.post_token_balances:
            for balance in meta.post_token_balances:
                # Convert to string for comparison
                balance_owner = str(balance.owner) if hasattr(balance, 'owner') else str(getattr(balance, 'owner', ''))
                balance_mint = str(balance.mint) if hasattr(balance, 'mint') else str(getattr(balance, 'mint', ''))
                
                if balance_owner == wallet_str and balance_mint == mint_str:
                    try:
                        # Try multiple ways to get the amount
                        if hasattr(balance, 'ui_token_amount'):
                            amount_obj = balance.ui_token_amount
                            if hasattr(amount_obj, 'amount') and amount_obj.amount is not None:
                                post_token_balance = int(amount_obj.amount)
                            elif hasattr(amount_obj, 'ui_amount') and amount_obj.ui_amount is not None:
                                post_token_balance = int(float(amount_obj.ui_amount) * (10**TOKEN_DECIMALS))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error parsing post-token balance: {e}")
                    break
        
        # Calculate tokens received
        if pre_token_balance == 0 and post_token_balance > 0:
            tokens_received_raw = post_token_balance
        else:
            tokens_received_raw = post_token_balance - pre_token_balance
        
        if tokens_received_raw <= 0:
            logger.warning("Token balance search failed. Using fallback from EXTREME_FAST estimate.")
            # Fallback: use the amount we know we bought
            if self.extreme_fast_mode and self.extreme_fast_token_amount > 0:
                return self.extreme_fast_token_amount
            else:
                logger.error("Cannot determine tokens received from transaction")
                return 0.0

        return tokens_received_raw / 10**TOKEN_DECIMALS