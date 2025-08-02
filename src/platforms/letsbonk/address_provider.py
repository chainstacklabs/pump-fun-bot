"""
LetsBonk implementation of AddressProvider interface.

This module provides all LetsBonk (Raydium LaunchLab) specific addresses and PDA derivations
by implementing the AddressProvider interface.
"""


from solders.pubkey import Pubkey
from spl.token.instructions import get_associated_token_address

from interfaces.core import AddressProvider, Platform, TokenInfo


class LetsBonkAddressProvider(AddressProvider):
    """LetsBonk (Raydium LaunchLab) implementation of AddressProvider interface."""
    
    # Raydium LaunchLab program addresses
    RAYDIUM_LAUNCHLAB_PROGRAM_ID = Pubkey.from_string("LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj")
    GLOBAL_CONFIG = Pubkey.from_string("6s1xP3hpbAfFoNtUNF8mfHsjr2Bd97JxFJRWLbL6aHuX")
    LETSBONK_PLATFORM_CONFIG = Pubkey.from_string("FfYek5vEz23cMkWsdJwG2oa6EphsvXSHrGpdALN4g6W1")
    
    # System program addresses
    TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
    SYSTEM_PROGRAM_ID = Pubkey.from_string("11111111111111111111111111111111")
    WSOL_MINT = Pubkey.from_string("So11111111111111111111111111111111111111112")
    ASSOCIATED_TOKEN_PROGRAM_ID = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")
    SYSTEM_RENT_PROGRAM_ID = Pubkey.from_string("SysvarRent111111111111111111111111111111111")
    
    @property
    def platform(self) -> Platform:
        """Get the platform this provider serves."""
        return Platform.LETS_BONK
    
    @property
    def program_id(self) -> Pubkey:
        """Get the main program ID for this platform."""
        return self.RAYDIUM_LAUNCHLAB_PROGRAM_ID
    
    def get_system_addresses(self) -> dict[str, Pubkey]:
        """Get all system addresses required for LetsBonk.
        
        Returns:
            Dictionary mapping address names to Pubkey objects
        """
        return {
            # Raydium LaunchLab specific addresses
            "program": self.RAYDIUM_LAUNCHLAB_PROGRAM_ID,
            "global_config": self.GLOBAL_CONFIG,
            "platform_config": self.LETSBONK_PLATFORM_CONFIG,
            
            # System addresses
            "system_program": self.SYSTEM_PROGRAM_ID,
            "token_program": self.TOKEN_PROGRAM_ID,
            "associated_token_program": self.ASSOCIATED_TOKEN_PROGRAM_ID,
            "rent": self.SYSTEM_RENT_PROGRAM_ID,
            "wsol_mint": self.WSOL_MINT,
        }
    
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
            quote_mint = self.WSOL_MINT
            
        pool_state, _ = Pubkey.find_program_address(
            [b"pool", bytes(base_mint), bytes(quote_mint)],
            self.RAYDIUM_LAUNCHLAB_PROGRAM_ID
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
        
        # Add pool state if available
        if token_info.pool_state:
            accounts["pool_state"] = token_info.pool_state
        
        # Add vault addresses if available
        if token_info.base_vault:
            accounts["base_vault"] = token_info.base_vault
        if token_info.quote_vault:
            accounts["quote_vault"] = token_info.quote_vault
            
        # Derive pool state if not provided
        if not token_info.pool_state:
            accounts["pool_state"] = self.derive_pool_address(token_info.mint)
        
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
            self.RAYDIUM_LAUNCHLAB_PROGRAM_ID
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
            self.RAYDIUM_LAUNCHLAB_PROGRAM_ID
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
        return Pubkey.create_with_seed(payer, seed, self.TOKEN_PROGRAM_ID)
    
    def get_buy_instruction_accounts(self, token_info: TokenInfo, user: Pubkey) -> dict[str, Pubkey]:
        """Get all accounts needed for a buy instruction.
        
        Args:
            token_info: Token information
            user: User's wallet address
            
        Returns:
            Dictionary of account addresses for buy instruction
        """
        additional_accounts = self.get_additional_accounts(token_info)
        
        return {
            "payer": user,
            "authority": additional_accounts["authority"],
            "global_config": self.GLOBAL_CONFIG,
            "platform_config": self.LETSBONK_PLATFORM_CONFIG,
            "pool_state": additional_accounts["pool_state"],
            "user_base_token": self.derive_user_token_account(user, token_info.mint),
            "base_vault": additional_accounts.get("base_vault", token_info.base_vault),
            "quote_vault": additional_accounts.get("quote_vault", token_info.quote_vault),
            "base_token_mint": token_info.mint,
            "quote_token_mint": self.WSOL_MINT,
            "base_token_program": self.TOKEN_PROGRAM_ID,
            "quote_token_program": self.TOKEN_PROGRAM_ID,
            "event_authority": additional_accounts["event_authority"],
            "program": self.RAYDIUM_LAUNCHLAB_PROGRAM_ID,
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
        
        return {
            "payer": user,
            "authority": additional_accounts["authority"],
            "global_config": self.GLOBAL_CONFIG,
            "platform_config": self.LETSBONK_PLATFORM_CONFIG,
            "pool_state": additional_accounts["pool_state"],
            "user_base_token": self.derive_user_token_account(user, token_info.mint),
            "base_vault": additional_accounts.get("base_vault", token_info.base_vault),
            "quote_vault": additional_accounts.get("quote_vault", token_info.quote_vault),
            "base_token_mint": token_info.mint,
            "quote_token_mint": self.WSOL_MINT,
            "base_token_program": self.TOKEN_PROGRAM_ID,
            "quote_token_program": self.TOKEN_PROGRAM_ID,
            "event_authority": additional_accounts["event_authority"],
            "program": self.RAYDIUM_LAUNCHLAB_PROGRAM_ID,
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
            "wsol_mint": self.WSOL_MINT,
            "owner": user,
            "system_program": self.SYSTEM_PROGRAM_ID,
            "token_program": self.TOKEN_PROGRAM_ID,
            "rent": self.SYSTEM_RENT_PROGRAM_ID,
        }