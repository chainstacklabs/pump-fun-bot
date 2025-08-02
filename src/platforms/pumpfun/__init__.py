"""
Pump.Fun platform registration and exports.

This module registers all pump.fun implementations with the platform factory
and provides convenient imports for the pump.fun platform.
"""

from interfaces.core import Platform
from platforms import register_platform_implementations

from .address_provider import PumpFunAddressProvider
from .curve_manager import PumpFunCurveManager
from .event_parser import PumpFunEventParser
from .instruction_builder import PumpFunInstructionBuilder

# Register pump.fun platform implementations
register_platform_implementations(
    Platform.PUMP_FUN,
    PumpFunAddressProvider,
    PumpFunInstructionBuilder,
    PumpFunCurveManager,
    PumpFunEventParser
)

# Export implementations for direct use if needed
__all__ = [
    'PumpFunAddressProvider',
    'PumpFunCurveManager',
    'PumpFunEventParser',
    'PumpFunInstructionBuilder'
]