---
inclusion: always
---

# Project Architecture Rules

## Directory Structure

### Package Organization
Maintain clear separation of concerns:

```
src/
├── __init__.py
├── bot_runner.py              # Main entry point
├── config_loader.py           # Configuration management
├── core/                      # Core blockchain functionality
│   ├── client.py             # Solana RPC client abstraction
│   ├── wallet.py             # Wallet operations
│   └── priority_fee/         # Fee management
├── platforms/                # Platform-specific implementations
│   ├── pumpfun/             # pump.fun specific code
│   └── letsbonk/            # letsbonk.fun specific code
├── trading/                  # Trading logic
│   ├── base.py              # Base trading classes
│   ├── universal_trader.py   # Platform-agnostic trader
│   └── position.py          # Position management
├── monitoring/               # Event listening and monitoring
│   ├── base_listener.py     # Base listener interface
│   └── universal_*_listener.py  # Specific listeners
├── interfaces/               # Abstract base classes
└── utils/                    # Utilities and helpers
    ├── logger.py            # Logging utilities
    └── idl_manager.py       # IDL management
```

### File Naming Conventions
- Use snake_case for all Python files and directories
- Prefix abstract base classes with "Base" or put in `interfaces/`
- Use "Universal" prefix for platform-agnostic implementations
- Group related functionality in subdirectories

## Design Patterns

### Platform Abstraction
Implement platform-specific functionality using the factory pattern:

```python
# interfaces/core.py - Define abstract interfaces
from abc import ABC, abstractmethod

class AddressProvider(ABC):
    @abstractmethod
    def get_program_address(self) -> str:
        pass

# platforms/pumpfun/address_provider.py - Concrete implementation
class PumpFunAddressProvider(AddressProvider):
    def get_program_address(self) -> str:
        return "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
```

### Universal Components
Create platform-agnostic wrappers that delegate to platform-specific implementations:

```python
class UniversalTrader:
    def __init__(self, platform: Platform, **kwargs):
        self.platform = platform
        self.platform_trader = self._create_platform_trader()
    
    def _create_platform_trader(self):
        # Factory method to create platform-specific trader
        pass
```

### Configuration Management
- Use YAML files for bot configurations in `bots/` directory
- Support environment variable interpolation with `${VARIABLE}` syntax
- Validate configurations before starting bots
- Separate environment-specific settings in `.env` files

## Module Dependencies

### Import Rules
- Core modules should not import from trading or monitoring
- Platform-specific modules should only import from their own package and core/interfaces
- Avoid circular imports between packages
- Use dependency injection for cross-package dependencies

### Dependency Layers (from low to high level)
1. **utils/** - Utilities and helpers (no business logic dependencies)
2. **interfaces/** - Abstract base classes and protocols
3. **core/** - Blockchain and infrastructure (depends on utils, interfaces)
4. **platforms/** - Platform implementations (depends on core, interfaces)
5. **trading/** - Trading logic (depends on core, platforms, interfaces)
6. **monitoring/** - Event listening (depends on core, platforms, interfaces)
7. **bot_runner.py** - Main orchestrator (depends on all layers)

## Async Architecture

### Event Loop Management
- Use uvloop for better performance
- Set event loop policy at application startup
- Use asyncio.create_task() for concurrent operations
- Implement proper cleanup on shutdown

### Connection Management
- Use connection pooling for HTTP clients
- Implement reconnection logic for WebSocket connections
- Cache expensive resources (blockhash, account info)
- Use async context managers for resource cleanup

## Testing Strategy

### Test Organization
- Use `learning-examples/` for integration testing and validation
- Test platform-specific components independently
- Mock external dependencies (RPC calls, WebSocket connections)
- Validate configurations with actual bot startup

### Test Data
- Use test networks for development
- Never test with real funds or production keys
- Create fixtures for common test scenarios
- Document test account requirements

## Performance Considerations

### Caching Strategy
- Cache recent blockhash in background task
- Cache account information where appropriate
- Use local caching for IDL data
- Implement TTL for cached data

### Resource Management
- Limit concurrent operations based on RPC provider limits
- Implement backoff strategies for failed requests
- Use separate processes for production bot instances
- Monitor memory usage in long-running processes