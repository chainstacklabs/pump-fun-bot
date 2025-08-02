"""
Platform factory and registry for managing multiple trading platforms.

This module provides a centralized way to instantiate and access
platform-specific implementations of the trading interfaces.
"""

from dataclasses import dataclass
from typing import Any

from core.client import SolanaClient
from interfaces.core import (
    AddressProvider,
    CurveManager,
    EventParser,
    InstructionBuilder,
    Platform,
)


@dataclass
class PlatformImplementations:
    """Container for all platform-specific implementations."""
    address_provider: AddressProvider
    instruction_builder: InstructionBuilder
    curve_manager: CurveManager
    event_parser: EventParser


class PlatformRegistry:
    """Registry for platform implementations."""
    
    def __init__(self):
        self._implementations: dict[Platform, dict[str, type]] = {}
        self._instances: dict[Platform, PlatformImplementations] = {}
    
    def register_platform(
        self,
        platform: Platform,
        address_provider_class: type[AddressProvider],
        instruction_builder_class: type[InstructionBuilder],
        curve_manager_class: type[CurveManager],
        event_parser_class: type[EventParser]
    ) -> None:
        """Register platform implementations.
        
        Args:
            platform: Platform enum value
            address_provider_class: AddressProvider implementation class
            instruction_builder_class: InstructionBuilder implementation class
            curve_manager_class: CurveManager implementation class
            event_parser_class: EventParser implementation class
        """
        self._implementations[platform] = {
            'address_provider': address_provider_class,
            'instruction_builder': instruction_builder_class,
            'curve_manager': curve_manager_class,
            'event_parser': event_parser_class
        }
    
    def create_platform_implementations(
        self,
        platform: Platform,
        client: SolanaClient,
        **kwargs: Any
    ) -> PlatformImplementations:
        """Create platform implementation instances.
        
        Args:
            platform: Platform to create implementations for
            client: Solana RPC client
            **kwargs: Additional arguments for implementation constructors
            
        Returns:
            PlatformImplementations containing all interface implementations
            
        Raises:
            ValueError: If platform is not registered
        """
        if platform not in self._implementations:
            raise ValueError(f"Platform {platform} is not registered")
        
        # Check if we already have instances for this platform
        if platform in self._instances:
            return self._instances[platform]
        
        impl_classes = self._implementations[platform]
        
        # Create instances
        address_provider = impl_classes['address_provider']()
        instruction_builder = impl_classes['instruction_builder']()
        curve_manager = impl_classes['curve_manager'](client)
        event_parser = impl_classes['event_parser']()
        
        implementations = PlatformImplementations(
            address_provider=address_provider,
            instruction_builder=instruction_builder,
            curve_manager=curve_manager,
            event_parser=event_parser
        )
        
        # Cache the instances
        self._instances[platform] = implementations
        
        return implementations
    
    def get_platform_implementations(self, platform: Platform) -> PlatformImplementations | None:
        """Get cached platform implementations.
        
        Args:
            platform: Platform to get implementations for
            
        Returns:
            PlatformImplementations if available, None otherwise
        """
        return self._instances.get(platform)
    
    def get_supported_platforms(self) -> list[Platform]:
        """Get list of supported platforms.
        
        Returns:
            List of registered platforms
        """
        return list(self._implementations.keys())
    
    def is_platform_supported(self, platform: Platform) -> bool:
        """Check if a platform is supported.
        
        Args:
            platform: Platform to check
            
        Returns:
            True if platform is registered, False otherwise
        """
        return platform in self._implementations


class PlatformFactory:
    """Factory for creating platform-specific implementations."""
    
    def __init__(self):
        self.registry = PlatformRegistry()
        self._setup_default_platforms()
    
    def _setup_default_platforms(self) -> None:
        """Setup default platform registrations."""
        # Import platform implementations dynamically to avoid circular imports
        try:
            from platforms.pumpfun import (
                PumpFunAddressProvider,
                PumpFunCurveManager,
                PumpFunEventParser,
                PumpFunInstructionBuilder,
            )
            
            self.registry.register_platform(
                Platform.PUMP_FUN,
                PumpFunAddressProvider,
                PumpFunInstructionBuilder,
                PumpFunCurveManager,
                PumpFunEventParser
            )
            
        except ImportError as e:
            print(f"Warning: Could not register pump.fun platform: {e}")
        
        try:
            from platforms.letsbonk import (
                LetsBonkAddressProvider,
                LetsBonkCurveManager,
                LetsBonkEventParser,
                LetsBonkInstructionBuilder,
            )
            
            self.registry.register_platform(
                Platform.LETS_BONK,
                LetsBonkAddressProvider,
                LetsBonkInstructionBuilder,
                LetsBonkCurveManager,
                LetsBonkEventParser
            )
            
        except ImportError as e:
            print(f"Warning: Could not register LetsBonk platform: {e}")
    
    def create_for_platform(
        self,
        platform: Platform,
        client: SolanaClient,
        **config: Any
    ) -> PlatformImplementations:
        """Create all implementations for a specific platform.
        
        Args:
            platform: Platform to create implementations for
            client: Solana RPC client
            **config: Platform-specific configuration
            
        Returns:
            PlatformImplementations containing all interface implementations
        """
        return self.registry.create_platform_implementations(platform, client, **config)
    
    def get_address_provider(self, platform: Platform, client: SolanaClient) -> AddressProvider:
        """Get address provider for platform.
        
        Args:
            platform: Platform to get provider for
            client: Solana RPC client
            
        Returns:
            AddressProvider implementation
        """
        implementations = self.registry.create_platform_implementations(platform, client)
        return implementations.address_provider
    
    def get_instruction_builder(self, platform: Platform, client: SolanaClient) -> InstructionBuilder:
        """Get instruction builder for platform.
        
        Args:
            platform: Platform to get builder for
            client: Solana RPC client
            
        Returns:
            InstructionBuilder implementation
        """
        implementations = self.registry.create_platform_implementations(platform, client)
        return implementations.instruction_builder
    
    def get_curve_manager(self, platform: Platform, client: SolanaClient) -> CurveManager:
        """Get curve manager for platform.
        
        Args:
            platform: Platform to get manager for
            client: Solana RPC client
            
        Returns:
            CurveManager implementation
        """
        implementations = self.registry.create_platform_implementations(platform, client)
        return implementations.curve_manager
    
    def get_event_parser(self, platform: Platform, client: SolanaClient) -> EventParser:
        """Get event parser for platform.
        
        Args:
            platform: Platform to get parser for
            client: Solana RPC client
            
        Returns:
            EventParser implementation
        """
        implementations = self.registry.create_platform_implementations(platform, client)
        return implementations.event_parser
    
    def get_supported_platforms(self) -> list[Platform]:
        """Get list of supported platforms.
        
        Returns:
            List of supported platforms
        """
        return self.registry.get_supported_platforms()


# Global factory instance
platform_factory = PlatformFactory()


def get_platform_implementations(platform: Platform, client: SolanaClient) -> PlatformImplementations:
    """Convenience function to get platform implementations.
    
    Args:
        platform: Platform to get implementations for
        client: Solana RPC client
        
    Returns:
        PlatformImplementations containing all interface implementations
    """
    return platform_factory.create_for_platform(platform, client)


def register_platform_implementations(
    platform: Platform,
    address_provider_class: type[AddressProvider],
    instruction_builder_class: type[InstructionBuilder],
    curve_manager_class: type[CurveManager],
    event_parser_class: type[EventParser]
) -> None:
    """Register platform implementations with the global factory.
    
    Args:
        platform: Platform enum value
        address_provider_class: AddressProvider implementation class
        instruction_builder_class: InstructionBuilder implementation class
        curve_manager_class: CurveManager implementation class
        event_parser_class: EventParser implementation class
    """
    platform_factory.registry.register_platform(
        platform,
        address_provider_class,
        instruction_builder_class,
        curve_manager_class,
        event_parser_class
    )