"""
LetsBonk implementation of InstructionBuilder interface.

This module builds LetsBonk (Raydium LaunchLab) specific buy and sell instructions
by implementing the InstructionBuilder interface.
"""

import hashlib
import struct
import time
from typing import Final

from solders.instruction import AccountMeta, Instruction
from solders.pubkey import Pubkey
from solders.system_program import CreateAccountWithSeedParams, create_account_with_seed
from spl.token.instructions import create_idempotent_associated_token_account

from core.pubkeys import TOKEN_DECIMALS, SystemAddresses
from interfaces.core import AddressProvider, InstructionBuilder, Platform, TokenInfo

# Instruction discriminators for LetsBonk (from IDL)
BUY_EXACT_IN_DISCRIMINATOR: Final[bytes] = bytes([250, 234, 13, 123, 213, 156, 19, 236])
BUY_EXACT_OUT_DISCRIMINATOR: Final[bytes] = bytes([24, 211, 116, 40, 105, 3, 153, 56])
SELL_EXACT_IN_DISCRIMINATOR: Final[bytes] = bytes([149, 39, 222, 155, 211, 124, 152, 26])
SELL_EXACT_OUT_DISCRIMINATOR: Final[bytes] = bytes([95, 200, 71, 34, 8, 9, 11, 166])


class LetsBonkInstructionBuilder(InstructionBuilder):
    """LetsBonk (Raydium LaunchLab) implementation of InstructionBuilder interface."""
    
    @property
    def platform(self) -> Platform:
        """Get the platform this builder serves."""
        return Platform.LETS_BONK
    
    async def build_buy_instruction(
        self,
        token_info: TokenInfo,
        user: Pubkey,
        amount_in: int,
        minimum_amount_out: int,
        address_provider: AddressProvider
    ) -> list[Instruction]:
        """Build buy instruction(s) for LetsBonk using buy_exact_in.
        
        Args:
            token_info: Token information
            user: User's wallet address
            amount_in: Amount of SOL to spend (in lamports)
            minimum_amount_out: Minimum tokens expected (raw token units)
            address_provider: Platform address provider
            
        Returns:
            List of instructions needed for the buy operation
        """
        instructions = []
        
        # Get all required accounts
        accounts_info = address_provider.get_buy_instruction_accounts(token_info, user)
        
        # 1. Create idempotent ATA for base token
        ata_instruction = create_idempotent_associated_token_account(
            user,  # payer
            user,  # owner  
            token_info.mint,  # mint
            SystemAddresses.TOKEN_PROGRAM,  # token program
        )
        instructions.append(ata_instruction)
        
        # 2. Create WSOL account with seed (temporary account for the transaction)
        wsol_seed = self._generate_wsol_seed(user)
        wsol_account = address_provider.create_wsol_account_with_seed(user, wsol_seed)
        
        # Account creation cost + amount to spend
        account_creation_lamports = 2_039_280  # Standard account creation cost
        total_lamports = amount_in + account_creation_lamports
        
        create_wsol_ix = create_account_with_seed(
            CreateAccountWithSeedParams(
                from_pubkey=user,
                to_pubkey=wsol_account,
                base=user,
                seed=wsol_seed,
                lamports=total_lamports,
                space=165,  # Size of a token account
                owner=SystemAddresses.TOKEN_PROGRAM
            )
        )
        instructions.append(create_wsol_ix)
        
        # 3. Initialize WSOL account
        initialize_wsol_ix = self._create_initialize_account_instruction(
            wsol_account, 
            SystemAddresses.SOL_MINT, 
            user,
            address_provider
        )
        instructions.append(initialize_wsol_ix)
        
        # 4. Build buy_exact_in instruction
        buy_accounts = [
            AccountMeta(pubkey=accounts_info["payer"], is_signer=True, is_writable=True),
            AccountMeta(pubkey=accounts_info["authority"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["global_config"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["platform_config"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["pool_state"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts_info["user_base_token"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=wsol_account, is_signer=False, is_writable=True),  # user_quote_token
            AccountMeta(pubkey=accounts_info["base_vault"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts_info["quote_vault"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts_info["base_token_mint"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["quote_token_mint"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["base_token_program"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["quote_token_program"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["event_authority"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["program"], is_signer=False, is_writable=False),
        ]
        
        # Build instruction data: discriminator + amount_in + minimum_amount_out + share_fee_rate
        SHARE_FEE_RATE = 0  # No sharing fee
        instruction_data = (
            BUY_EXACT_IN_DISCRIMINATOR +
            struct.pack("<Q", amount_in) +           # amount_in (u64) - SOL to spend
            struct.pack("<Q", minimum_amount_out) +  # minimum_amount_out (u64) - min tokens
            struct.pack("<Q", SHARE_FEE_RATE)        # share_fee_rate (u64): 0
        )
        
        buy_instruction = Instruction(
            program_id=accounts_info["program"],
            data=instruction_data,
            accounts=buy_accounts
        )
        instructions.append(buy_instruction)
        
        # 5. Close WSOL account to reclaim SOL
        close_wsol_ix = self._create_close_account_instruction(
            wsol_account, 
            user, 
            user,
            address_provider
        )
        instructions.append(close_wsol_ix)
        
        return instructions
    
    async def build_sell_instruction(
        self,
        token_info: TokenInfo,
        user: Pubkey,
        amount_in: int,
        minimum_amount_out: int,
        address_provider: AddressProvider
    ) -> list[Instruction]:
        """Build sell instruction(s) for LetsBonk using sell_exact_in.
        
        Args:
            token_info: Token information
            user: User's wallet address
            amount_in: Amount of tokens to sell (raw token units)
            minimum_amount_out: Minimum SOL expected (in lamports)
            address_provider: Platform address provider
            
        Returns:
            List of instructions needed for the sell operation
        """
        instructions = []
        
        # Get all required accounts
        accounts_info = address_provider.get_sell_instruction_accounts(token_info, user)
        
        # 1. Create WSOL account with seed (to receive SOL)
        wsol_seed = self._generate_wsol_seed(user)
        wsol_account = address_provider.create_wsol_account_with_seed(user, wsol_seed)
        
        # Minimal account creation cost
        account_creation_lamports = 2_039_280
        
        create_wsol_ix = create_account_with_seed(
            CreateAccountWithSeedParams(
                from_pubkey=user,
                to_pubkey=wsol_account,
                base=user,
                seed=wsol_seed,
                lamports=account_creation_lamports,
                space=165,  # Size of a token account
                owner=SystemAddresses.TOKEN_PROGRAM
            )
        )
        instructions.append(create_wsol_ix)
        
        # 2. Initialize WSOL account
        initialize_wsol_ix = self._create_initialize_account_instruction(
            wsol_account, 
            SystemAddresses.SOL_MINT, 
            user,
            address_provider
        )
        instructions.append(initialize_wsol_ix)
        
        # 3. Build sell_exact_in instruction
        sell_accounts = [
            AccountMeta(pubkey=accounts_info["payer"], is_signer=True, is_writable=True),
            AccountMeta(pubkey=accounts_info["authority"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["global_config"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["platform_config"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["pool_state"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts_info["user_base_token"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=wsol_account, is_signer=False, is_writable=True),  # user_quote_token
            AccountMeta(pubkey=accounts_info["base_vault"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts_info["quote_vault"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts_info["base_token_mint"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["quote_token_mint"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["base_token_program"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["quote_token_program"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["event_authority"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts_info["program"], is_signer=False, is_writable=False),
        ]
        
        # Build instruction data: discriminator + amount_in + minimum_amount_out + share_fee_rate
        SHARE_FEE_RATE = 0  # No sharing fee
        instruction_data = (
            SELL_EXACT_IN_DISCRIMINATOR +
            struct.pack("<Q", amount_in) +           # amount_in (u64) - tokens to sell
            struct.pack("<Q", minimum_amount_out) +  # minimum_amount_out (u64) - min SOL
            struct.pack("<Q", SHARE_FEE_RATE)        # share_fee_rate (u64): 0
        )
        
        sell_instruction = Instruction(
            program_id=accounts_info["program"],
            data=instruction_data,
            accounts=sell_accounts
        )
        instructions.append(sell_instruction)
        
        # 4. Close WSOL account to reclaim SOL
        close_wsol_ix = self._create_close_account_instruction(
            wsol_account, 
            user, 
            user,
            address_provider
        )
        instructions.append(close_wsol_ix)
        
        return instructions
    
    def get_required_accounts_for_buy(
        self,
        token_info: TokenInfo,
        user: Pubkey,
        address_provider: AddressProvider
    ) -> list[Pubkey]:
        """Get list of accounts required for buy operation (for priority fee calculation).
        
        Args:
            token_info: Token information
            user: User's wallet address
            address_provider: Platform address provider
            
        Returns:
            List of account addresses that will be accessed
        """
        accounts_info = address_provider.get_buy_instruction_accounts(token_info, user)
        
        return [
            accounts_info["pool_state"],
            accounts_info["user_base_token"],
            accounts_info["base_vault"],
            accounts_info["quote_vault"],
            accounts_info["base_token_mint"],
            accounts_info["quote_token_mint"],
            accounts_info["program"],
        ]
    
    def get_required_accounts_for_sell(
        self,
        token_info: TokenInfo,
        user: Pubkey,
        address_provider: AddressProvider
    ) -> list[Pubkey]:
        """Get list of accounts required for sell operation (for priority fee calculation).
        
        Args:
            token_info: Token information
            user: User's wallet address
            address_provider: Platform address provider
            
        Returns:
            List of account addresses that will be accessed
        """
        accounts_info = address_provider.get_sell_instruction_accounts(token_info, user)
        
        return [
            accounts_info["pool_state"],
            accounts_info["user_base_token"],
            accounts_info["base_vault"],
            accounts_info["quote_vault"],
            accounts_info["base_token_mint"],
            accounts_info["quote_token_mint"],
            accounts_info["program"],
        ]
    
    def _generate_wsol_seed(self, user: Pubkey) -> str:
        """Generate a unique seed for WSOL account creation.
        
        Args:
            user: User's wallet address
            
        Returns:
            Unique seed string for WSOL account
        """
        # Generate a unique seed based on timestamp and user pubkey
        seed_data = f"{int(time.time())}{user!s}"
        return hashlib.sha256(seed_data.encode()).hexdigest()[:32]
    
    def _create_initialize_account_instruction(
        self, 
        account: Pubkey, 
        mint: Pubkey, 
        owner: Pubkey,
        address_provider: AddressProvider
    ) -> Instruction:
        """Create an InitializeAccount instruction for the Token Program.
        
        Args:
            account: The account to initialize
            mint: The token mint
            owner: The account owner
            address_provider: Platform address provider
            
        Returns:
            Instruction for initializing the account
        """
        accounts = [
            AccountMeta(pubkey=account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=mint, is_signer=False, is_writable=False),
            AccountMeta(pubkey=owner, is_signer=False, is_writable=False),
            AccountMeta(pubkey=SystemAddresses.RENT, is_signer=False, is_writable=False),
        ]
        
        # InitializeAccount instruction discriminator (instruction 1 in Token Program)
        data = bytes([1])
        
        return Instruction(
            program_id=SystemAddresses.TOKEN_PROGRAM,
            data=data,
            accounts=accounts
        )
    
    def _create_close_account_instruction(
        self, 
        account: Pubkey, 
        destination: Pubkey, 
        owner: Pubkey,
        address_provider: AddressProvider
    ) -> Instruction:
        """Create a CloseAccount instruction for the Token Program.
        
        Args:
            account: The account to close
            destination: Where to send the remaining lamports
            owner: The account owner (must sign)
            address_provider: Platform address provider
            
        Returns:
            Instruction for closing the account
        """
        accounts = [
            AccountMeta(pubkey=account, is_signer=False, is_writable=True),
            AccountMeta(pubkey=destination, is_signer=False, is_writable=True),
            AccountMeta(pubkey=owner, is_signer=True, is_writable=False),
        ]
        
        # CloseAccount instruction discriminator (instruction 9 in Token Program)
        data = bytes([9])
        
        return Instruction(
            program_id=SystemAddresses.TOKEN_PROGRAM,
            data=data,
            accounts=accounts
        )
    
    def calculate_token_amount_raw(self, token_amount_decimal: float) -> int:
        """Convert decimal token amount to raw token units.
        
        Args:
            token_amount_decimal: Token amount in decimal form
            
        Returns:
            Token amount in raw units (adjusted for decimals)
        """
        return int(token_amount_decimal * 10**TOKEN_DECIMALS)
    
    def calculate_token_amount_decimal(self, token_amount_raw: int) -> float:
        """Convert raw token amount to decimal form.
        
        Args:
            token_amount_raw: Token amount in raw units
            
        Returns:
            Token amount in decimal form
        """
        return token_amount_raw / 10**TOKEN_DECIMALS