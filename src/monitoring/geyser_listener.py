"""
Geyser monitoring for pump.fun tokens.
"""

import asyncio
from collections.abc import Awaitable, Callable

import grpc
from solders.pubkey import Pubkey

from geyser.generated import geyser_pb2, geyser_pb2_grpc
from monitoring.base_listener import BaseTokenListener
from monitoring.geyser_event_processor import GeyserEventProcessor
from trading.base import TokenInfo
from utils.logger import get_logger

logger = get_logger(__name__)


class GeyserListener(BaseTokenListener):
    """Geyser listener for pump.fun token creation events."""

    def __init__(self, geyser_endpoint: str, geyser_api_token: str, geyser_auth_type: str, pump_program: Pubkey):
        """Initialize token listener.
        
        Args:
            geyser_endpoint: Geyser gRPC endpoint URL
            geyser_api_token: API token for authentication
            geyser_auth_type: authentication type ('x-token' or 'basic')
            pump_program: Pump.fun program address
        """
        self.geyser_endpoint = geyser_endpoint
        self.geyser_api_token = geyser_api_token
        valid_auth_types = {"x-token", "basic"}
        self.auth_type: str = (geyser_auth_type or "x-token").lower()
        if self.auth_type not in valid_auth_types:
            raise ValueError(
                f"Unsupported auth_type={self.auth_type!r}. "
                f"Expected one of {valid_auth_types}"
            )
        self.pump_program = pump_program
        self.event_processor = GeyserEventProcessor(pump_program)
        
    async def _create_geyser_connection(self):
        """Establish a secure connection to the Geyser endpoint."""
        if self.auth_type == "x-token":
            auth = grpc.metadata_call_credentials(
                lambda _, callback: callback((("x-token", self.geyser_api_token),), None)
            )
        else:  # Default to basic auth
            auth = grpc.metadata_call_credentials(
                lambda _, callback: callback((("authorization", f"Basic {self.geyser_api_token}"),), None)
            )
        creds = grpc.composite_channel_credentials(
            grpc.ssl_channel_credentials(), auth
        )
        channel = grpc.aio.secure_channel(self.geyser_endpoint, creds)
        return geyser_pb2_grpc.GeyserStub(channel), channel

    def _create_subscription_request(self):
        """Create a subscription request for Pump.fun transactions."""
        request = geyser_pb2.SubscribeRequest()
        request.transactions["pump_filter"].account_include.append(str(self.pump_program))
        request.transactions["pump_filter"].failed = False
        request.commitment = geyser_pb2.CommitmentLevel.PROCESSED
        return request

    async def listen_for_tokens(
        self,
        token_callback: Callable[[TokenInfo], Awaitable[None]],
        match_string: str | None = None,
        creator_address: str | None = None,
    ) -> None:
        """Listen for new token creations using Geyser subscription.
        
        Args:
            token_callback: Callback function for new tokens
            match_string: Optional string to match in token name/symbol
            creator_address: Optional creator address to filter by
        """
        while True:
            try:
                stub, channel = await self._create_geyser_connection()
                request = self._create_subscription_request()
                
                logger.info(f"Connected to Geyser endpoint: {self.geyser_endpoint}")
                logger.info(f"Monitoring for transactions involving program: {self.pump_program}")
                
                try:
                    async for update in stub.Subscribe(iter([request])):
                        token_info = await self._process_update(update)
                        if not token_info:
                            continue
                            
                        logger.info(
                            f"New token detected: {token_info.name} ({token_info.symbol})"
                        )
    
                        if match_string and not (
                            match_string.lower() in token_info.name.lower()
                            or match_string.lower() in token_info.symbol.lower()
                        ):
                            logger.info(
                                f"Token does not match filter '{match_string}'. Skipping..."
                            )
                            continue
    
                        if (
                            creator_address
                            and str(token_info.user) != creator_address
                        ):
                            logger.info(
                                f"Token not created by {creator_address}. Skipping..."
                            )
                            continue
    
                        await token_callback(token_info)
                        
                except grpc.aio.AioRpcError as e:
                    logger.error(f"gRPC error: {e.details()}")
                    await asyncio.sleep(5)
                    
                finally:
                    await channel.close()
                    
            except Exception as e:
                logger.error(f"Geyser connection error: {e}")
                logger.info("Reconnecting in 10 seconds...")
                await asyncio.sleep(10)
    
    async def _process_update(self, update) -> TokenInfo | None:
        """Process a Geyser update and extract token creation info.
        
        Args:
            update: Geyser update from the subscription
            
        Returns:
            TokenInfo if a token creation is found, None otherwise
        """
        try:
            if not update.HasField("transaction"):
                return None
                
            tx = update.transaction.transaction.transaction
            msg = getattr(tx, "message", None)
            if msg is None:
                return None

            for ix in msg.instructions:
                # Skip non-Pump.fun program instructions
                program_idx = ix.program_id_index
                if program_idx >= len(msg.account_keys):
                    continue
                    
                program_id = msg.account_keys[program_idx]
                if bytes(program_id) != bytes(self.pump_program):
                    continue
                
                # Process instruction data
                token_info = self.event_processor.process_transaction_data(
                    ix.data, ix.accounts, msg.account_keys
                )
                if token_info:
                    return token_info
                    
            return None
            
        except Exception as e:
            logger.error(f"Error processing Geyser update: {e}")
            return None
