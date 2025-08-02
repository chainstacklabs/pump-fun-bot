"""
Pump.Fun implementation of CurveManager interface.

This module handles pump.fun-specific bonding curve operations
by implementing the CurveManager interface.
"""

from typing import Any

from solders.pubkey import Pubkey

from core.client import SolanaClient
from core.curve import BondingCurveManager
from core.pubkeys import LAMPORTS_PER_SOL, TOKEN_DECIMALS
from interfaces.core import CurveManager, Platform


class PumpFunCurveManager(CurveManager):
    """Pump.Fun implementation of CurveManager interface."""
    
    def __init__(self, client: SolanaClient):
        """Initialize pump.fun curve manager.
        
        Args:
            client: Solana RPC client
        """
        self.client = client
        self.bonding_curve_manager = BondingCurveManager(client)
    
    @property
    def platform(self) -> Platform:
        """Get the platform this manager serves."""
        return Platform.PUMP_FUN
    
    async def get_pool_state(self, pool_address: Pubkey) -> dict[str, Any]:
        """Get the current state of a pump.fun bonding curve.
        
        Args:
            pool_address: Address of the bonding curve
            
        Returns:
            Dictionary containing bonding curve state data
        """
        curve_state = await self.bonding_curve_manager.get_curve_state(pool_address)
        
        return {
            "virtual_token_reserves": curve_state.virtual_token_reserves,
            "virtual_sol_reserves": curve_state.virtual_sol_reserves,
            "real_token_reserves": curve_state.real_token_reserves,
            "real_sol_reserves": curve_state.real_sol_reserves,
            "token_total_supply": curve_state.token_total_supply,
            "complete": curve_state.complete,
            "creator": str(curve_state.creator),
            
            # Calculated fields for convenience
            "price_per_token": curve_state.calculate_price(),
            "token_reserves_decimal": curve_state.token_reserves,
            "sol_reserves_decimal": curve_state.sol_reserves,
        }
    
    async def calculate_price(self, pool_address: Pubkey) -> float:
        """Calculate current token price from bonding curve state.
        
        Args:
            pool_address: Address of the bonding curve
            
        Returns:
            Current token price in SOL
        """
        return await self.bonding_curve_manager.calculate_price(pool_address)
    
    async def calculate_buy_amount_out(
        self,
        pool_address: Pubkey,
        amount_in: int
    ) -> int:
        """Calculate expected tokens received for a buy operation.
        
        Uses the pump.fun bonding curve formula to calculate token output.
        
        Args:
            pool_address: Address of the bonding curve
            amount_in: Amount of SOL to spend (in lamports)
            
        Returns:
            Expected amount of tokens to receive (in raw token units)
        """
        curve_state = await self.bonding_curve_manager.get_curve_state(pool_address)
        
        # Use virtual reserves for bonding curve calculation
        # Formula: tokens_out = (amount_in * virtual_token_reserves) / (virtual_sol_reserves + amount_in)
        numerator = amount_in * curve_state.virtual_token_reserves
        denominator = curve_state.virtual_sol_reserves + amount_in
        
        if denominator == 0:
            return 0
            
        tokens_out = numerator // denominator
        return tokens_out
    
    async def calculate_sell_amount_out(
        self,
        pool_address: Pubkey,
        amount_in: int
    ) -> int:
        """Calculate expected SOL received for a sell operation.
        
        Uses the pump.fun bonding curve formula to calculate SOL output.
        
        Args:
            pool_address: Address of the bonding curve
            amount_in: Amount of tokens to sell (in raw token units)
            
        Returns:
            Expected amount of SOL to receive (in lamports)
        """
        curve_state = await self.bonding_curve_manager.get_curve_state(pool_address)
        
        # Use virtual reserves for bonding curve calculation
        # Formula: sol_out = (amount_in * virtual_sol_reserves) / (virtual_token_reserves + amount_in)
        numerator = amount_in * curve_state.virtual_sol_reserves
        denominator = curve_state.virtual_token_reserves + amount_in
        
        if denominator == 0:
            return 0
            
        sol_out = numerator // denominator
        return sol_out
    
    async def get_reserves(self, pool_address: Pubkey) -> tuple[int, int]:
        """Get current bonding curve reserves.
        
        Args:
            pool_address: Address of the bonding curve
            
        Returns:
            Tuple of (token_reserves, sol_reserves) in raw units
        """
        curve_state = await self.bonding_curve_manager.get_curve_state(pool_address)
        return (curve_state.virtual_token_reserves, curve_state.virtual_sol_reserves)
    
    async def calculate_expected_tokens(self, pool_address: Pubkey, sol_amount: float) -> float:
        """Calculate the expected token amount for a given SOL input.
        
        This is a convenience method that wraps calculate_buy_amount_out
        and converts between decimal and raw units.
        
        Args:
            pool_address: Address of the bonding curve
            sol_amount: Amount of SOL to spend (in decimal SOL)
            
        Returns:
            Expected token amount (in decimal tokens)
        """
        sol_lamports = int(sol_amount * LAMPORTS_PER_SOL)
        tokens_raw = await self.calculate_buy_amount_out(pool_address, sol_lamports)
        return tokens_raw / 10**TOKEN_DECIMALS
    
    async def calculate_expected_sol(self, pool_address: Pubkey, token_amount: float) -> float:
        """Calculate the expected SOL amount for a given token input.
        
        This is a convenience method that wraps calculate_sell_amount_out
        and converts between decimal and raw units.
        
        Args:
            pool_address: Address of the bonding curve
            token_amount: Amount of tokens to sell (in decimal tokens)
            
        Returns:
            Expected SOL amount (in decimal SOL)
        """
        tokens_raw = int(token_amount * 10**TOKEN_DECIMALS)
        sol_lamports = await self.calculate_sell_amount_out(pool_address, tokens_raw)
        return sol_lamports / LAMPORTS_PER_SOL
    
    async def is_curve_complete(self, pool_address: Pubkey) -> bool:
        """Check if the bonding curve is complete (migrated to Raydium).
        
        Args:
            pool_address: Address of the bonding curve
            
        Returns:
            True if curve is complete, False otherwise
        """
        curve_state = await self.bonding_curve_manager.get_curve_state(pool_address)
        return curve_state.complete
    
    async def get_curve_progress(self, pool_address: Pubkey) -> dict[str, Any]:
        """Get bonding curve completion progress information.
        
        Args:
            pool_address: Address of the bonding curve
            
        Returns:
            Dictionary with progress information
        """
        curve_state = await self.bonding_curve_manager.get_curve_state(pool_address)
        
        # Calculate progress based on SOL raised vs target
        # This is approximate since the exact target isn't stored in the curve state
        sol_raised = curve_state.real_sol_reserves / LAMPORTS_PER_SOL
        
        # Estimate progress based on typical pump.fun graduation requirements
        # (This could be made more accurate with additional on-chain data)
        estimated_target_sol = 85.0  # Typical pump.fun graduation target
        progress_percentage = min((sol_raised / estimated_target_sol) * 100, 100.0)
        
        return {
            "complete": curve_state.complete,
            "sol_raised": sol_raised,
            "estimated_target_sol": estimated_target_sol,
            "progress_percentage": progress_percentage,
            "tokens_available": curve_state.virtual_token_reserves / 10**TOKEN_DECIMALS,
            "market_cap_sol": sol_raised,  # Approximate market cap
        }