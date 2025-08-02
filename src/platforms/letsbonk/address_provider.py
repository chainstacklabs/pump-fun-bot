"""
LetsBonk implementation of AddressProvider interface.

This module provides all LetsBonk (Raydium LaunchLab) specific addresses and PDA derivations
by implementing the AddressProvider interface.
"""

from dataclasses import dataclass
from typing import Final

from solders.pubkey import Pubkey
from spl.token.instructions import get_associated_token_address

from core.pubkeys import SystemAddresses
from interfaces.core import AddressProvider, Platform, TokenInfo


@dataclass
class LetsBonkAddresses:
    """LetsBonk (Raydium LaunchLab) program addresses."""
    
    # Raydium LaunchLab program addresses
    PROGRAM: Final[Pubkey] = Pubkey.from_string("LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj")
    GLOBAL_CONFIG: Final[Pubkey] = Pubkey.from_string("6s1xP3hpbAfFoNtUNF8mfHsjr2Bd97JxFJRWLbL6aHuX")
    PLATFORM_CONFIG: Final[Pubkey] = Pubkey.from_string("FfYek5vEz23cMkWsdJwG2oa6EphsvXSHrGpdALN4g6W1")


class LetsBonkAddressProvider(AddressProvider):
    """LetsBonk (Raydium LaunchLab) implementation of AddressProvider interface."""
    
    @property
    def platform(self) -> Platform:
        """Get the platform this provider serves."""
        return Platform.LETS_BONK
    
    @property
    def program_id(self) -> Pubkey:
        """Get the main program ID for this platform."""
        return LetsBonkAddresses.PROGRAM
    
    def get_system_addresses(self) -> dict[str, Pubkey]:
        """Get all system addresses required for LetsBonk.
        
        Returns:
            Dictionary mapping address names to Pubkey objects
        """
        # Get system addresses from the single source of truth
        system_addresses = SystemAddresses.get_all_system_addresses()
        
        # Add LetsBonk specific addresses
        letsbonk_addresses = {
            # Raydium LaunchLab specific addresses
            "program": LetsBonkAddresses.PROGRAM,
            "global_config": LetsBonkAddresses.GLOBAL_CONFIG,
            "platform_config": LetsBonkAddresses.PLATFORM_CONFIG,
        }
        
        # Combine system and platform-specific addresses
        return {**system_addresses, **letsbonk_addresses}
    
    def derive_pool_address(self, base_mint: Pubkey, quote_mint: Pubkey | None = None) -> Pubkey:
        """Derive the pool state address for a token pair.
        
        For LetsBonk, this derives the pool state PDA using base_mint and WSOL.
        
        Args:
            base_mint: Base token mint address
            quote_mint: Quote token mint (defaults to WSOL)
            
        Returns:
            Pool state address
        """
        if quote_mint is None:
            quote_mint = SystemAddresses.SOL_MINT
            
        pool_state, _ = Pubkey.find_program_address(
            [b"pool", bytes(base_mint), bytes(quote_mint)],
            LetsBonkAddresses.PROGRAM
        )
        return pool_state
    
    def derive_user_token_account(self, user: Pubkey, mint: Pubkey) -> Pubkey:
        """Derive user's associated token account address.
        
        Args:
            user: User's wallet address
            mint: Token mint address
            
        Returns:
            User's associated token account address
        """
        return get_associated_token_address(user, mint)
    
    def get_additional_accounts(self, token_info: TokenInfo) -> dict[str, Pubkey]:
        """Get LetsBonk-specific additional accounts needed for trading.
        
        Args:
            token_info: Token information
            
        Returns:
            Dictionary of additional account addresses
        """
        accounts = {}
        
        # Add pool state - must be present in token_info
        if token_info.pool_state:
            accounts["pool_state"] = token_info.pool_state
        
        # Add vault addresses - must be present in token_info
        if token_info.base_vault:
            accounts["base_vault"] = token_info.base_vault
        if token_info.quote_vault:
            accounts["quote_vault"] = token_info.quote_vault
            
        # Derive authority PDA
        accounts["authority"] = self.derive_authority_pda()
        
        # Derive event authority PDA
        accounts["event_authority"] = self.derive_event_authority_pda()
            
        return accounts
    
    def derive_authority_pda(self) -> Pubkey:
        """Derive the authority PDA for Raydium LaunchLab.
        
        This PDA acts as the authority for pool vault operations.
        
        Returns:
            Authority PDA address
        """
        AUTH_SEED = b"vault_auth_seed"
        authority_pda, _ = Pubkey.find_program_address(
            [AUTH_SEED],
            LetsBonkAddresses.PROGRAM
        )
        return authority_pda
    
    def derive_event_authority_pda(self) -> Pubkey:
        """Derive the event authority PDA for Raydium LaunchLab.
        
        This PDA is used for emitting program events during swaps.
        
        Returns:
            Event authority PDA address
        """
        EVENT_AUTHORITY_SEED = b"__event_authority"
        event_authority_pda, _ = Pubkey.find_program_address(
            [EVENT_AUTHORITY_SEED],
            LetsBonkAddresses.PROGRAM
        )
        return event_authority_pda
    
    def create_wsol_account_with_seed(self, payer: Pubkey, seed: str) -> Pubkey:
        """Create a WSOL account address using createAccountWithSeed pattern.
        
        Args:
            payer: The account that will pay for and own the new account
            seed: String seed for deterministic account generation
            
        Returns:
            New WSOL account address
        """
        return Pubkey.create_with_seed(payer, seed, SystemAddresses.TOKEN_PROGRAM)
    
    def get_buy_instruction_accounts(self, token_info: TokenInfo, user: Pubkey) -> dict[str, Pubkey]:
        """Get all accounts needed for a buy instruction.
        
        Args:
            token_info: Token information
            user: User's wallet address
            
        Returns:
            Dictionary of account addresses for buy instruction
        """
        additional_accounts = self.get_additional_accounts(token_info)
        
        # Vault addresses must be present in token_info
        if not token_info.base_vault or not token_info.quote_vault:
            raise ValueError(f"Missing required vault addresses for token {token_info.mint}. "
                           f"base_vault: {token_info.base_vault}, quote_vault: {token_info.quote_vault}")
        
        return {
            "payer": user,
            "authority": additional_accounts["authority"],
            "global_config": LetsBonkAddresses.GLOBAL_CONFIG,
            "platform_config": LetsBonkAddresses.PLATFORM_CONFIG,
            "pool_state": token_info.pool_state,
            "user_base_token": self.derive_user_token_account(user, token_info.mint),
            "base_vault": token_info.base_vault,
            "quote_vault": token_info.quote_vault,
            "base_token_mint": token_info.mint,
            "quote_token_mint": SystemAddresses.SOL_MINT,
            "base_token_program": SystemAddresses.TOKEN_PROGRAM,
            "quote_token_program": SystemAddresses.TOKEN_PROGRAM,
            "event_authority": additional_accounts["event_authority"],
            "program": LetsBonkAddresses.PROGRAM,
        }
    
    def get_sell_instruction_accounts(self, token_info: TokenInfo, user: Pubkey) -> dict[str, Pubkey]:
        """Get all accounts needed for a sell instruction.
        
        Args:
            token_info: Token information
            user: User's wallet address
            
        Returns:
            Dictionary of account addresses for sell instruction
        """
        additional_accounts = self.get_additional_accounts(token_info)
        
        # Vault addresses must be present in token_info
        if not token_info.base_vault or not token_info.quote_vault:
            raise ValueError(f"Missing required vault addresses for token {token_info.mint}. "
                           f"base_vault: {token_info.base_vault}, quote_vault: {token_info.quote_vault}")
        
        return {
            "payer": user,
            "authority": additional_accounts["authority"],
            "global_config": LetsBonkAddresses.GLOBAL_CONFIG,
            "platform_config": LetsBonkAddresses.PLATFORM_CONFIG,
            "pool_state": token_info.pool_state,
            "user_base_token": self.derive_user_token_account(user, token_info.mint),
            "base_vault": token_info.base_vault,
            "quote_vault": token_info.quote_vault,
            "base_token_mint": token_info.mint,
            "quote_token_mint": SystemAddresses.SOL_MINT,
            "base_token_program": SystemAddresses.TOKEN_PROGRAM,
            "quote_token_program": SystemAddresses.TOKEN_PROGRAM,
            "event_authority": additional_accounts["event_authority"],
            "program": LetsBonkAddresses.PROGRAM,
        }
    
    def get_wsol_account_creation_accounts(self, user: Pubkey, wsol_account: Pubkey) -> dict[str, Pubkey]:
        """Get accounts needed for WSOL account creation and initialization.
        
        Args:
            user: User's wallet address
            wsol_account: WSOL account to be created
            
        Returns:
            Dictionary of account addresses for WSOL operations
        """
        return {
            "payer": user,
            "wsol_account": wsol_account,
            "wsol_mint": SystemAddresses.SOL_MINT,
            "owner": user,
            "system_program": SystemAddresses.SYSTEM_PROGRAM,
            "token_program": SystemAddresses.TOKEN_PROGRAM,
            "rent": SystemAddresses.RENT,
        }