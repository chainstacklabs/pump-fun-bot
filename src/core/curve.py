"""
Pump.fun bonding curve manager for price calculations and curve state management.
"""

import struct
from dataclasses import dataclass

from solders.pubkey import Pubkey

from core.client import SolanaClient
from core.pubkeys import LAMPORTS_PER_SOL, TOKEN_DECIMALS
from utils.logger import get_logger

logger = get_logger(__name__)

# Bonding curve discriminator
CURVE_DISCRIMINATOR = bytes([23, 203, 71, 8, 209, 70, 227, 3])


@dataclass
class BondingCurveState:
    """Represents the state of a pump.fun bonding curve."""
    
    virtual_token_reserves: int
    virtual_sol_reserves: int
    real_token_reserves: int
    real_sol_reserves: int
    token_total_supply: int
    complete: bool
    creator: Pubkey
    
    @property
    def token_reserves(self) -> float:
        """Token reserves in decimal form."""
        return self.virtual_token_reserves / 10**TOKEN_DECIMALS
    
    @property
    def sol_reserves(self) -> float:
        """SOL reserves in decimal form."""
        return self.virtual_sol_reserves / LAMPORTS_PER_SOL
    
    def calculate_price(self) -> float:
        """Calculate current token price in SOL."""
        if self.virtual_token_reserves <= 0:
            return 0.0
        
        # Price = sol_reserves / token_reserves
        price_lamports = self.virtual_sol_reserves / self.virtual_token_reserves
        return price_lamports * (10**TOKEN_DECIMALS) / LAMPORTS_PER_SOL


class BondingCurveManager:
    """Manages pump.fun bonding curve operations."""
    
    def __init__(self, client: SolanaClient):
        """Initialize bonding curve manager.
        
        Args:
            client: Solana RPC client
        """
        self.client = client
    
    async def get_curve_state(self, curve_address: Pubkey) -> BondingCurveState:
        """Get the current state of a bonding curve.
        
        Args:
            curve_address: Address of the bonding curve
            
        Returns:
            BondingCurveState with current curve data
            
        Raises:
            ValueError: If curve data is invalid or inaccessible
        """
        try:
            account = await self.client.get_account_info(curve_address)
            if not account.data:
                raise ValueError(f"No data in bonding curve account {curve_address}")
            
            curve_state = self._decode_curve_state(account.data)
            return curve_state
            
        except Exception as e:
            logger.error(f"Failed to get curve state: {e!s}")
            raise ValueError(f"Invalid bonding curve state: {e!s}")
    
    async def calculate_price(self, curve_address: Pubkey) -> float:
        """Calculate current token price from bonding curve.
        
        Args:
            curve_address: Address of the bonding curve
            
        Returns:
            Current token price in SOL
        """
        curve_state = await self.get_curve_state(curve_address)
        return curve_state.calculate_price()
    
    def _decode_curve_state(self, data: bytes) -> BondingCurveState:
        """Decode bonding curve state from raw account data.
        
        Args:
            data: Raw account data
            
        Returns:
            Decoded BondingCurveState
            
        Raises:
            ValueError: If data format is invalid
        """
        if len(data) < 8:
            raise ValueError("Curve data too short")
        
        # Check discriminator
        if not data.startswith(CURVE_DISCRIMINATOR):
            raise ValueError("Invalid curve discriminator")
        
        offset = 8
        
        try:
            # Decode based on pump.fun BondingCurve structure:
            # - virtual_token_reserves: u64 (8 bytes)
            # - virtual_sol_reserves: u64 (8 bytes) 
            # - real_token_reserves: u64 (8 bytes)
            # - real_sol_reserves: u64 (8 bytes)
            # - token_total_supply: u64 (8 bytes)
            # - complete: bool (1 byte)
            # - padding: 7 bytes
            # - creator: Pubkey (32 bytes)
            
            virtual_token_reserves = struct.unpack_from("<Q", data, offset)[0]
            offset += 8
            
            virtual_sol_reserves = struct.unpack_from("<Q", data, offset)[0]
            offset += 8
            
            real_token_reserves = struct.unpack_from("<Q", data, offset)[0]
            offset += 8
            
            real_sol_reserves = struct.unpack_from("<Q", data, offset)[0]
            offset += 8
            
            token_total_supply = struct.unpack_from("<Q", data, offset)[0]
            offset += 8
            
            complete = bool(struct.unpack_from("<B", data, offset)[0])
            offset += 1
            
            # Skip padding
            offset += 7
            
            creator = Pubkey.from_bytes(data[offset:offset + 32])
            
            return BondingCurveState(
                virtual_token_reserves=virtual_token_reserves,
                virtual_sol_reserves=virtual_sol_reserves,
                real_token_reserves=real_token_reserves,
                real_sol_reserves=real_sol_reserves,
                token_total_supply=token_total_supply,
                complete=complete,
                creator=creator,
            )
            
        except Exception as e:
            raise ValueError(f"Failed to decode curve state: {e}")