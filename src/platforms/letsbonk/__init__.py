"""
LetsBonk platform registration and exports.

This module registers all LetsBonk implementations with the platform factory
and provides convenient imports for the LetsBonk platform.
"""

from interfaces.core import Platform
from platforms import register_platform_implementations

from .address_provider import LetsBonkAddressProvider
from .curve_manager import LetsBonkCurveManager
from .event_parser import LetsBonkEventParser
from .instruction_builder import LetsBonkInstructionBuilder

# Register LetsBonk platform implementations
register_platform_implementations(
    Platform.LETS_BONK,
    LetsBonkAddressProvider,
    LetsBonkInstructionBuilder,
    LetsBonkCurveManager,
    LetsBonkEventParser
)

# Export implementations for direct use if needed
__all__ = [
    'LetsBonkAddressProvider',
    'LetsBonkCurveManager', 
    'LetsBonkEventParser',
    'LetsBonkInstructionBuilder'
]