from cleanup.manager import AccountCleanupManager
from config import CLEANUP_MODE, CLEANUP_WITH_PRIORITY_FEE
from utils.logger import get_logger

logger = get_logger(__name__)


def should_cleanup_after_failure() -> bool:
    return CLEANUP_MODE == "on_fail"


def should_cleanup_after_sell() -> bool:
    return CLEANUP_MODE == "after_sell"


def should_cleanup_post_session() -> bool:
    return CLEANUP_MODE == "post_session"


async def handle_cleanup_after_failure(client, wallet, mint, priority_fee_manager):
    if should_cleanup_after_failure():
        logger.info("[Cleanup] Triggered by failed buy transaction.")
        manager = AccountCleanupManager(client, wallet, priority_fee_manager, CLEANUP_WITH_PRIORITY_FEE)
        await manager.cleanup_ata(mint)

async def handle_cleanup_after_sell(client, wallet, mint, priority_fee_manager):
    if should_cleanup_after_sell():
        logger.info("[Cleanup] Triggered after token sell.")
        manager = AccountCleanupManager(client, wallet, priority_fee_manager, CLEANUP_WITH_PRIORITY_FEE)
        await manager.cleanup_ata(mint)

async def handle_cleanup_post_session(client, wallet, mints, priority_fee_manager):
    if should_cleanup_post_session():
        logger.info("[Cleanup] Triggered post trading session.")
        manager = AccountCleanupManager(client, wallet, priority_fee_manager, CLEANUP_WITH_PRIORITY_FEE)
        for mint in mints:
            await manager.cleanup_ata(mint)
