"""
Pump.Fun implementation of AddressProvider interface.

This module provides all pump.fun-specific addresses and PDA derivations
by implementing the AddressProvider interface.
"""


from solders.pubkey import Pubkey
from spl.token.instructions import get_associated_token_address

from core.pubkeys import PumpAddresses, SystemAddresses
from interfaces.core import AddressProvider, Platform, TokenInfo


class PumpFunAddressProvider(AddressProvider):
    """Pump.Fun implementation of AddressProvider interface."""
    
    @property
    def platform(self) -> Platform:
        """Get the platform this provider serves."""
        return Platform.PUMP_FUN
    
    @property
    def program_id(self) -> Pubkey:
        """Get the main program ID for this platform."""
        return PumpAddresses.PROGRAM
    
    def get_system_addresses(self) -> dict[str, Pubkey]:
        """Get all system addresses required for pump.fun.
        
        Returns:
            Dictionary mapping address names to Pubkey objects
        """
        return {
            # Pump.fun specific addresses
            "program": PumpAddresses.PROGRAM,
            "global": PumpAddresses.GLOBAL,
            "event_authority": PumpAddresses.EVENT_AUTHORITY,
            "fee": PumpAddresses.FEE,
            "liquidity_migrator": PumpAddresses.LIQUIDITY_MIGRATOR,
            
            # System addresses
            "system_program": SystemAddresses.PROGRAM,
            "token_program": SystemAddresses.TOKEN_PROGRAM,
            "associated_token_program": SystemAddresses.ASSOCIATED_TOKEN_PROGRAM,
            "rent": SystemAddresses.RENT,
            "sol_mint": SystemAddresses.SOL,
        }
    
    def derive_pool_address(self, base_mint: Pubkey, quote_mint: Pubkey | None = None) -> Pubkey:
        """Derive the bonding curve address for a token.
        
        For pump.fun, this is the bonding curve PDA derived from the mint.
        
        Args:
            base_mint: Token mint address
            quote_mint: Not used for pump.fun (SOL is always the quote)
            
        Returns:
            Bonding curve address
        """
        bonding_curve, _ = Pubkey.find_program_address(
            [b"bonding-curve", bytes(base_mint)],
            PumpAddresses.PROGRAM
        )
        return bonding_curve
    
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
        """Get pump.fun-specific additional accounts needed for trading.
        
        Args:
            token_info: Token information
            
        Returns:
            Dictionary of additional account addresses
        """
        accounts = {}
        
        # Add bonding curve if available
        if token_info.bonding_curve:
            accounts["bonding_curve"] = token_info.bonding_curve
        
        # Add associated bonding curve if available
        if token_info.associated_bonding_curve:
            accounts["associated_bonding_curve"] = token_info.associated_bonding_curve
            
        # Add creator vault if available
        if token_info.creator_vault:
            accounts["creator_vault"] = token_info.creator_vault
        
        # Derive associated bonding curve if not provided
        if not token_info.associated_bonding_curve and token_info.bonding_curve:
            accounts["associated_bonding_curve"] = self.derive_associated_bonding_curve(
                token_info.mint, token_info.bonding_curve
            )
        
        # Derive creator vault if not provided but creator is available
        if not token_info.creator_vault and token_info.creator:
            accounts["creator_vault"] = self.derive_creator_vault(token_info.creator)
            
        return accounts
    
    def derive_associated_bonding_curve(self, mint: Pubkey, bonding_curve: Pubkey) -> Pubkey:
        """Derive the associated bonding curve (ATA of bonding curve for the token).
        
        Args:
            mint: Token mint address
            bonding_curve: Bonding curve address
            
        Returns:
            Associated bonding curve address
        """
        return get_associated_token_address(bonding_curve, mint)
    
    def derive_creator_vault(self, creator: Pubkey) -> Pubkey:
        """Derive the creator vault address.
        
        Args:
            creator: Creator address
            
        Returns:
            Creator vault address
        """
        creator_vault, _ = Pubkey.find_program_address(
            [b"creator-vault", bytes(creator)],
            PumpAddresses.PROGRAM
        )
        return creator_vault
    
    def derive_global_volume_accumulator(self) -> Pubkey:
        """Derive the global volume accumulator PDA.
        
        Returns:
            Global volume accumulator address
        """
        return PumpAddresses.find_global_volume_accumulator()
    
    def derive_user_volume_accumulator(self, user: Pubkey) -> Pubkey:
        """Derive the user volume accumulator PDA.
        
        Args:
            user: User address
            
        Returns:
            User volume accumulator address
        """
        return PumpAddresses.find_user_volume_accumulator(user)
    
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
            "global": PumpAddresses.GLOBAL,
            "fee": PumpAddresses.FEE,
            "mint": token_info.mint,
            "bonding_curve": additional_accounts.get("bonding_curve", token_info.bonding_curve),
            "associated_bonding_curve": additional_accounts.get("associated_bonding_curve", token_info.associated_bonding_curve),
            "user_token_account": self.derive_user_token_account(user, token_info.mint),
            "user": user,
            "system_program": SystemAddresses.PROGRAM,
            "token_program": SystemAddresses.TOKEN_PROGRAM,
            "creator_vault": additional_accounts.get("creator_vault", token_info.creator_vault),
            "event_authority": PumpAddresses.EVENT_AUTHORITY,
            "program": PumpAddresses.PROGRAM,
            "global_volume_accumulator": self.derive_global_volume_accumulator(),
            "user_volume_accumulator": self.derive_user_volume_accumulator(user),
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
            "global": PumpAddresses.GLOBAL,
            "fee": PumpAddresses.FEE,
            "mint": token_info.mint,
            "bonding_curve": additional_accounts.get("bonding_curve", token_info.bonding_curve),
            "associated_bonding_curve": additional_accounts.get("associated_bonding_curve", token_info.associated_bonding_curve),
            "user_token_account": self.derive_user_token_account(user, token_info.mint),
            "user": user,
            "system_program": SystemAddresses.PROGRAM,
            "creator_vault": additional_accounts.get("creator_vault", token_info.creator_vault),
            "token_program": SystemAddresses.TOKEN_PROGRAM,
            "event_authority": PumpAddresses.EVENT_AUTHORITY,
            "program": PumpAddresses.PROGRAM,
        }