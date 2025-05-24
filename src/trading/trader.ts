import { PublicKey } from '@solana/web3.js';
import { SolanaClient } from '../core/client';
import { Wallet } from '../core/wallet';
import { BondingCurveManager } from '../core/curve';
import { PriorityFeeManager } from '../core/priority_fee';
import { TokenInfo, tokenInfoToPlain } from './baseTrader'; // Assuming TokenInfo and helpers are here
import { TokenBuyer, BuyerConfig } from './buyer'; // Assuming BuyerConfig is exported
import { TokenSeller, SellerConfig } from './seller'; // Assuming SellerConfig is exported

// Listener imports - GeyserListener is a placeholder
import { BaseListener, EventCallback } from '../monitoring/baseListener';
import { BlockListener } from '../monitoring/blockListener';
import { LogsListener } from '../monitoring/logsListener';
import { pumpFunProgramId } from '../core/pubkeys';

import { Queue } from '../utils/queue'; // Simple async queue
import { sleep, monotonic } from '../utils/time'; // Sleep and monotonic time
import *s fs from 'fs/promises'; // For async file operations
import *s path from 'path';

// Placeholder for cleanup functions - these would need their own TypeScript conversions
const handleCleanupAfterFailure = async (...args: any[]): Promise<void> => console.warn("handleCleanupAfterFailure not implemented", args);
const handleCleanupAfterSell = async (...args: any[]): Promise<void> => console.warn("handleCleanupAfterSell not implemented", args);
const handleCleanupPostSession = async (...args: any[]): Promise<void> => console.warn("handleCleanupPostSession not implemented", args);

// Placeholder for GeyserListener
class GeyserListener extends BaseListener {
    constructor(endpoint: string, token: string, authType: string, programId: PublicKey) {
        // Dummy solanaClient, wallet, trader, callback for BaseListener constructor
        const dummySolanaClient = {} as SolanaClient; 
        const dummyWallet = {} as Wallet;
        const dummyTrader = {} as Trader; // `this` is not available yet
        const dummyCallback: EventCallback = async () => {};
        super(dummySolanaClient, dummyWallet, dummyTrader, dummyCallback);
        logger.warn("GeyserListener is a placeholder and not fully implemented.");
    }
    async start(matchString?: string, creatorAddress?: string): Promise<void> { logger.info("GeyserListener.start called (placeholder)"); }
    async stop(): Promise<void> { logger.info("GeyserListener.stop called (placeholder)"); }
}


const logger = {
  info: (...args: any[]) => console.log('[Trader]', ...args),
  warn: (...args: any[]) => console.warn('[Trader]', ...args),
  error: (...args: any[]) => console.error('[Trader]', ...args),
  debug: (...args: any[]) => console.debug('[Trader]', ...args),
};

export interface TraderConfig {
  rpcEndpoint: string;
  wssEndpoint: string;
  privateKey: string;
  buyAmountSol: number;
  buySlippageBps: number; // e.g. 100 for 1%
  sellSlippageBps: number; // e.g. 2500 for 25%
  
  listenerType?: 'logs' | 'blocks' | 'geyser';
  geyserEndpoint?: string;
  geyserApiToken?: string;
  geyserAuthType?: 'x-token' | 'basic';

  extremeFastMode?: boolean;
  extremeFastTokenAmount?: number;

  enableDynamicPriorityFee?: boolean;
  enableFixedPriorityFee?: boolean;
  fixedPriorityFeeMicroLamports?: number; // Renamed from fixed_priority_fee
  extraPriorityFeePercent?: number; // Renamed from extra_priority_fee (0.1 for 10%)
  hardCapPriorityFeeMicroLamports?: number; // Renamed from hard_cap_prior_fee

  maxRetries?: number;
  waitTimeAfterCreationSec?: number;
  waitTimeAfterBuySec?: number;
  waitTimeBeforeNewTokenSec?: number;
  maxTokenAgeSec?: number;
  tokenWaitTimeoutSec?: number;

  cleanupMode?: 'disabled' | 'auto' | 'manual';
  cleanupForceCloseWithBurn?: boolean;
  cleanupWithPriorityFee?: boolean;

  matchString?: string | null;
  creatorAddressFilter?: string | null; // Renamed from bro_address
  marryMode?: boolean; // If true, only buy, don't sell
  yoloMode?: boolean;  // If true, trade continuously; if false, process one token and exit
}

export class Trader {
  private solanaClient: SolanaClient;
  private wallet: Wallet;
  private curveManager: BondingCurveManager;
  private priorityFeeManager: PriorityFeeManager;
  public buyer: TokenBuyer; // Made public for potential external access/info
  public seller: TokenSeller; // Made public
  private tokenListener: BaseListener;

  private config: TraderConfig;

  private tradedMints: Set<string> = new Set(); // Store mint Pubkeys as strings
  private tokenQueue: Queue<TokenInfo> = new Queue();
  private processingToken: boolean = false; // To prevent concurrent _handleToken calls if needed by design
  private processedTokens: Set<string> = new Set(); // Tracks mints that have been through _queue_token
  private tokenDiscoveredTimestamps: Map<string, number> = new Map(); // Mint (string) -> monotonic timestamp

  constructor(config: TraderConfig) {
    this.config = { ...this.getDefaultConfig(), ...config }; // Merge with defaults

    this.solanaClient = new SolanaClient(this.config.rpcEndpoint);
    this.wallet = new Wallet(this.config.privateKey);
    this.curveManager = new BondingCurveManager(this.solanaClient);
    this.priorityFeeManager = new PriorityFeeManager(
      this.solanaClient,
      this.solanaClient.connection, // Pass the actual connection object
      this.config.enableDynamicPriorityFee!,
      this.config.enableFixedPriorityFee!,
      this.config.fixedPriorityFeeMicroLamports!,
      this.config.extraPriorityFeePercent!,
      this.config.hardCapPriorityFeeMicroLamports!
    );

    const buyerConfig: BuyerConfig = {
        amountSol: this.config.buyAmountSol,
        slippageBps: this.config.buySlippageBps,
        maxRetries: this.config.maxRetries,
        extremeFastMode: this.config.extremeFastMode,
        extremeFastTokenAmount: this.config.extremeFastTokenAmount,
        priorityFeeManager: this.priorityFeeManager,
        bondingCurveManager: this.curveManager,
    };
    this.buyer = new TokenBuyer(this.solanaClient, this.wallet, buyerConfig);

    const sellerConfig: SellerConfig = {
        slippageBps: this.config.sellSlippageBps,
        maxRetries: this.config.maxRetries,
        priorityFeeManager: this.priorityFeeManager,
        bondingCurveManager: this.curveManager,
    };
    this.seller = new TokenSeller(this.solanaClient, this.wallet, sellerConfig);
    
    // Initialize listener - Pass `this` as the trader instance for callbacks
    // Note: `this` is not fully initialized here if listeners need methods from Trader during their construction.
    // This is a common issue; listeners usually get a callback that *uses* the trader instance later.
    // The Python BaseTokenListener takes a callback, not the trader instance itself.
    // The BaseListener I defined takes a trader instance, which might be problematic if it uses it in its constructor.
    // For now, assuming BaseListener stores it but doesn't use it in constructor.
    // The Python `PumpTrader` passes a lambda `lambda token: self._queue_token(token)` to its listener.
    // So the listeners here should take `this.queueToken.bind(this)` as the callback.
    
    const tokenCallback: EventCallback = this.queueToken.bind(this);

    switch (this.config.listenerType) {
      case 'geyser':
        if (!this.config.geyserEndpoint || !this.config.geyserApiToken) {
          throw new Error("Geyser endpoint and API token are required for geyser listener");
        }
        this.tokenListener = new GeyserListener( // GeyserListener needs a proper definition/conversion
          this.config.geyserEndpoint,
          this.config.geyserApiToken,
          this.config.geyserAuthType!,
          pumpFunProgramId // Assuming pump.fun program ID for Geyser too
        );
        logger.info("Using Geyser listener (placeholder) for token monitoring");
        break;
      case 'logs':
        this.tokenListener = new LogsListener(
          this.solanaClient, // LogsListener now takes SolanaClient
          this.wallet, 
          this, // Pass the Trader instance (this)
          tokenCallback,
          pumpFunProgramId
        );
        logger.info("Using logsSubscribe listener for token monitoring");
        break;
      case 'blocks':
      default:
        this.tokenListener = new BlockListener(
          this.solanaClient, // BlockListener now takes SolanaClient
          this.wallet,
          this, // Pass the Trader instance (this)
          tokenCallback,
          this.config.wssEndpoint,
          pumpFunProgramId
        );
        logger.info("Using blockSubscribe listener for token monitoring");
        break;
    }
  }

  private getDefaultConfig(): Partial<TraderConfig> {
    return {
      listenerType: 'logs',
      extremeFastMode: false,
      extremeFastTokenAmount: 30,
      enableDynamicPriorityFee: false,
      enableFixedPriorityFee: true,
      fixedPriorityFeeMicroLamports: 200000,
      extraPriorityFeePercent: 0.0,
      hardCapPriorityFeeMicroLamports: 200000,
      maxRetries: 3,
      waitTimeAfterCreationSec: 15,
      waitTimeAfterBuySec: 15,
      waitTimeBeforeNewTokenSec: 15,
      maxTokenAgeSec: 0.001, // This is very low, almost immediate. Python was 0.001.
      tokenWaitTimeoutSec: 30,
      cleanupMode: 'disabled',
      cleanupForceCloseWithBurn: false,
      cleanupWithPriorityFee: false,
      marryMode: false,
      yoloMode: false,
    };
  }

  public async start(): Promise<void> {
    logger.info("Starting Pump.fun Trader");
    logger.info(`Match filter: ${this.config.matchString || 'None'}`);
    logger.info(`Creator filter: ${this.config.creatorAddressFilter || 'None'}`);
    logger.info(`Marry mode: ${this.config.marryMode}`);
    logger.info(`YOLO mode: ${this.config.yoloMode}`);
    logger.info(`Max token age: ${this.config.maxTokenAgeSec} seconds`);

    try {
      const healthResp = await this.solanaClient.getHealth();
      logger.info(`RPC warm-up successful (getHealth: ${healthResp})`);
    } catch (e: any) {
      logger.warn(`RPC warm-up failed: ${e.message}`);
    }

    try {
      if (!this.config.yoloMode) {
        logger.info("Running in single token mode - will process one token and exit");
        const tokenInfo = await this.waitForToken();
        if (tokenInfo) {
          await this.handleToken(tokenInfo);
          logger.info("Finished processing single token. Exiting...");
        } else {
          logger.info(`No suitable token found within timeout period (${this.config.tokenWaitTimeoutSec}s). Exiting...`);
        }
      } else {
        logger.info("Running in continuous (YOLO) mode - will process tokens until interrupted");
        const processorTask = this.processTokenQueue(); // No await here, it runs in background
        
        // Start listening for tokens. The listener will call queueToken.
        await this.tokenListener.start(this.config.matchString || undefined, this.config.creatorAddressFilter || undefined);
        
        // Keep main thread alive or await processorTask if it's designed to complete/fail
        await processorTask; // This will run until processTokenQueue is explicitly stopped or errors
      }
    } catch (e: any) {
      logger.error(`Trading stopped due to error: ${e.message}`, e.stack);
    } finally {
      await this.cleanupResources();
      logger.info("Pump Trader has shut down");
    }
  }
  
  // Corresponds to _wait_for_token in Python
  private async waitForToken(): Promise<TokenInfo | null> {
    let foundToken: TokenInfo | null = null;
    const tokenFoundPromise = new Promise<TokenInfo | null>((resolve) => {
        const originalCallback = this.tokenListener.callback; // Assuming BaseListener stores it
        this.tokenListener.callback = async (token: TokenInfo) => { // Override callback temporarily
            const tokenKey = token.mint.toBase58();
            if (!this.processedTokens.has(tokenKey)) {
                this.tokenDiscoveredTimestamps.set(tokenKey, monotonic());
                this.processedTokens.add(tokenKey); // Mark as processed for this wait context
                foundToken = token;
                resolve(token); // Resolve the promise
            }
            // If originalCallback needs to be called for other purposes, do it here.
            // await originalCallback(token); 
        };
    });

    await this.tokenListener.start(this.config.matchString || undefined, this.config.creatorAddressFilter || undefined);
    logger.info(`Waiting for a suitable token (timeout: ${this.config.tokenWaitTimeoutSec}s)...`);

    try {
        const result = await Promise.race([
            tokenFoundPromise,
            sleep(this.config.tokenWaitTimeoutSec! * 1000).then(() => null) // Timeout
        ]);
        
        if (result) {
            logger.info(`Found token: ${result.symbol} (${result.mint.toBase58()})`);
        } else {
            logger.info(`Timed out after waiting ${this.config.tokenWaitTimeoutSec}s for a token`);
        }
        return result;

    } finally {
        await this.tokenListener.stop(); // Stop listener after waiting
        // Restore original callback if necessary, though for single token mode, trader might exit.
    }
}


  private async cleanupResources(): Promise<void> {
    if (this.tradedMints.size > 0) {
      logger.info(`Cleaning up ${this.tradedMints.size} traded token(s)...`);
      await handleCleanupPostSession(
        this.solanaClient,
        this.wallet,
        Array.from(this.tradedMints).map(mintStr => new PublicKey(mintStr)),
        this.priorityFeeManager,
        this.config.cleanupMode,
        this.config.cleanupWithPriorityFee,
        this.config.cleanupForceCloseWithBurn
      );
    }
    // Clean up token timestamps for tokens that were never processed from queue
    // (though processedTokens set should cover this mostly)
    // Python: old_keys = {k for k in self.token_timestamps if k not in self.processed_tokens}
    // This logic might need refinement based on how processedTokens is used in continuous mode.

    await this.solanaClient.close();
  }

  // Corresponds to _queue_token
  private async queueToken(tokenInfo: TokenInfo): Promise<void> {
    const tokenKey = tokenInfo.mint.toBase58();

    if (this.processedTokens.has(tokenKey) && this.config.yoloMode) { // In YOLO, only add if truly new
      // logger.debug(`Token ${tokenInfo.symbol} already processed or queued. Skipping.`);
      return;
    }
    
    this.tokenDiscoveredTimestamps.set(tokenKey, monotonic());
    
    // In non-YOLO mode, waitForToken handles adding to processedTokens.
    // In YOLO mode, processTokenQueue will add it.
    // If not yolo, queue shouldn't even be running. This callback is for yolo mode.
    if (!this.config.yoloMode) {
        logger.warn("queueToken called in non-YOLO mode. This shouldn't happen if waitForToken is used.");
        // If single token mode is active via _wait_for_token, that method handles the single token.
        // This callback should ideally only be active for continuous mode.
        return;
    }

    await this.tokenQueue.enqueue(tokenInfo);
    logger.info(`Queued new token: ${tokenInfo.symbol} (${tokenInfo.mint.toBase58()})`);
  }

  // Corresponds to _process_token_queue
  private async processTokenQueue(): Promise<void> {
    logger.info("Token processing queue started.");
    while (this.config.yoloMode) { // Loop indefinitely in YOLO mode
      try {
        const tokenInfo = await this.tokenQueue.dequeue(); // Waits if queue is empty
        if (!this.config.yoloMode) break; // Check again in case mode changed (though not supported dynamically)

        const tokenKey = tokenInfo.mint.toBase58();
        
        const discoveredTime = this.tokenDiscoveredTimestamps.get(tokenKey);
        if (!discoveredTime) {
            logger.warn(`Token ${tokenInfo.symbol} found in queue but no discovery timestamp. Skipping.`);
            this.processedTokens.add(tokenKey); // Mark as processed to avoid re-queueing issues
            continue;
        }

        const currentTime = monotonic();
        const tokenAge = currentTime - discoveredTime;

        if (tokenAge > this.config.maxTokenAgeSec!) {
          logger.info(`Skipping token ${tokenInfo.symbol} from queue - too old (${tokenAge.toFixed(1)}s > ${this.config.maxTokenAgeSec}s)`);
          this.processedTokens.add(tokenKey); // Mark as processed
          continue;
        }

        this.processedTokens.add(tokenKey); // Mark as processed before handling
        logger.info(`Processing fresh token from queue: ${tokenInfo.symbol} (age: ${tokenAge.toFixed(1)}s)`);
        await this.handleToken(tokenInfo); // No 'await' if we want non-blocking processing of queue

      } catch (e: any) {
        if (e.message === 'Queue closed') { // Specific error for closed queue
            logger.info("Token queue closed, stopping processor.");
            break;
        }
        logger.error(`Error in token queue processor: ${e.message}`, e.stack);
        await sleep(1000); // Wait a bit before retrying dequeue on generic error
      }
    }
    logger.info("Token processing queue stopped.");
  }

  // Corresponds to _handle_token. This is the method specified as `handle_new_token_event` in subtask.
  // It's more of a full processing pipeline for a token.
  public async handleToken(tokenInfo: TokenInfo): Promise<void> {
    // If there's already a token being processed, and we don't want concurrent handling:
    if (this.processingToken) {
        logger.warn(`Already processing a token, skipping ${tokenInfo.symbol} for now or re-queue if necessary.`);
        // Optionally, re-queue if it's critical not to miss: await this.tokenQueue.enqueue(tokenInfo);
        return;
    }
    this.processingToken = true;

    try {
      if (!this.config.extremeFastMode) {
        // await this.saveTokenInfo(tokenInfo); // Save token info
        logger.info(`Waiting ${this.config.waitTimeAfterCreationSec} seconds for bonding curve to stabilize...`);
        await sleep(this.config.waitTimeAfterCreationSec! * 1000);
      }

      logger.info(`Attempting to buy ${this.config.buyAmountSol.toFixed(6)} SOL worth of ${tokenInfo.symbol}...`);
      const buyResult = await this.buyer.execute(tokenInfo);

      if (buyResult.success && buyResult.txSignature) {
        await this.handleSuccessfulBuy(tokenInfo, buyResult);
      } else {
        await this.handleFailedBuy(tokenInfo, buyResult);
      }

      if (this.config.yoloMode) {
        logger.info(`YOLO mode: Waiting ${this.config.waitTimeBeforeNewTokenSec} seconds before next token processing cycle (if queue was empty).`);
        await sleep(this.config.waitTimeBeforeNewTokenSec! * 1000);
      }

    } catch (e: any) {
      logger.error(`Error handling token ${tokenInfo.symbol}: ${e.message}`, e.stack);
    } finally {
        this.processingToken = false;
    }
  }

  // Corresponds to _handle_successful_buy
  private async handleSuccessfulBuy(tokenInfo: TokenInfo, buyResult: TradeResult): Promise<void> {
    logger.info(`Successfully bought ${buyResult.amount?.toFixed(6)} ${tokenInfo.symbol} for ~${(buyResult.price! * buyResult.amount!).toFixed(6)} SOL. Tx: ${buyResult.txSignature}`);
    this.logTrade("buy", tokenInfo, buyResult.price!, buyResult.amount!, buyResult.txSignature!);
    this.tradedMints.add(tokenInfo.mint.toBase58());

    if (!this.config.marryMode) {
      logger.info(`Waiting ${this.config.waitTimeAfterBuySec} seconds before selling ${tokenInfo.symbol}...`);
      await sleep(this.config.waitTimeAfterBuySec! * 1000);

      logger.info(`Attempting to sell ${tokenInfo.symbol}...`);
      const sellResult = await this.seller.execute(tokenInfo);

      if (sellResult.success && sellResult.txSignature) {
        logger.info(`Successfully sold ${sellResult.amount?.toFixed(6)} ${tokenInfo.symbol} for ~${(sellResult.price! * sellResult.amount!).toFixed(6)} SOL. Tx: ${sellResult.txSignature}`);
        this.logTrade("sell", tokenInfo, sellResult.price!, sellResult.amount!, sellResult.txSignature!);
        await handleCleanupAfterSell(
          this.solanaClient, this.wallet, tokenInfo.mint, this.priorityFeeManager,
          this.config.cleanupMode, this.config.cleanupWithPriorityFee, this.config.cleanupForceCloseWithBurn
        );
      } else {
        logger.error(`Failed to sell ${tokenInfo.symbol}: ${sellResult.errorMessage}`);
        // Potentially handle cleanup differently if sell fails but buy was successful
      }
    } else {
      logger.info("Marry mode enabled. Skipping sell operation.");
      // If marry mode, may need different cleanup for just the bought token ATA if not selling.
      // The current cleanup_after_sell might be too aggressive or not run.
    }
  }

  // Corresponds to _handle_failed_buy
  private async handleFailedBuy(tokenInfo: TokenInfo, buyResult: TradeResult): Promise<void> {
    logger.error(`Failed to buy ${tokenInfo.symbol}: ${buyResult.errorMessage}`);
    await handleCleanupAfterFailure(
      this.solanaClient, this.wallet, tokenInfo.mint, this.priorityFeeManager,
      this.config.cleanupMode, this.config.cleanupWithPriorityFee, this.config.cleanupForceCloseWithBurn
    );
  }

  // Corresponds to _save_token_info
  public async saveTokenInfo(tokenInfo: TokenInfo): Promise<void> {
    try {
      const tradesDir = path.join(process.cwd(), "trades"); // Assuming trades directory in current working directory
      await fs.mkdir(tradesDir, { recursive: true });
      const fileName = path.join(tradesDir, `${tokenInfo.mint.toBase58()}.json`); // Changed from .txt to .json
      
      const plainTokenInfo = tokenInfoToPlain(tokenInfo); // Convert PKs to strings for JSON
      await fs.writeFile(fileName, JSON.stringify(plainTokenInfo, null, 2));
      logger.info(`Token information saved to ${fileName}`);
    } catch (e: any) {
      logger.error(`Failed to save token information: ${e.message}`);
    }
  }

  // Corresponds to _log_trade
  private async logTrade(
    action: 'buy' | 'sell',
    tokenInfo: TokenInfo,
    price: number, // Price per token in SOL
    solAmount: number, // Total SOL value of the trade (for buy, SOL spent; for sell, SOL received)
    txSignature: string
  ): Promise<void> {
    try {
      const tradesDir = path.join(process.cwd(), "trades");
      await fs.mkdir(tradesDir, { recursive: true });

      const logEntry = {
        timestamp: new Date().toISOString(),
        action: action,
        tokenAddress: tokenInfo.mint.toBase58(),
        symbol: tokenInfo.symbol,
        name: tokenInfo.name, // Added name for more context
        pricePerTokenSol: price,
        totalSolAmount: solAmount, // Amount of SOL involved in this trade
        // For buy, tokenAmount = solAmount / price. For sell, tokenAmount = actual tokens sold.
        // The `buyResult.amount` and `sellResult.amount` from Buyer/Seller are token amounts.
        // Let's clarify: the Python code logs `amount` which seems to be SOL amount for buy, token amount for sell.
        // The TradeResult interface has `amount` which is token amount.
        // Let's assume `amount` here means token quantity.
        tokenQuantity: solAmount, // This needs to be token quantity, not SOL amount.
                                 // The python code used `buy_result.amount` which was token amount.
                                 // And `sell_result.amount` which was token amount.
                                 // So `amount` param here should be token quantity.
        txHash: txSignature,
      };
      // Adjusting the log based on the `amount` parameter meaning token quantity:
      logEntry.tokenQuantity = amount; // Assuming `amount` parameter is token quantity
      logEntry.totalSolAmount = price * amount;


      const logFilePath = path.join(tradesDir, "trades.log");
      await fs.appendFile(logFilePath, JSON.stringify(logEntry) + "\n");
    } catch (e: any) {
      logger.error(`Failed to log trade: ${e.message}`);
    }
  }
  
  /**
   * Stops the trader and its associated listener.
   */
  public async stop(): Promise<void> {
    logger.info("Stopping Pump.fun Trader...");
    if (this.tokenListener) {
        await this.tokenListener.stop();
    }
    if (this.config.yoloMode) {
        this.config.yoloMode = false; // Signal processTokenQueue to stop
        this.tokenQueue.close(); // Close queue to unblock dequeue
    }
    await this.cleanupResources(); // Perform final cleanup
    logger.info("Pump.fun Trader stopped.");
  }

}

// Utility to create a Trader instance with a simplified config for testing or basic use
export function createTrader(
    rpcEndpoint: string,
    wssEndpoint: string,
    privateKey: string,
    buyAmountSol: number,
    customConfig: Partial<TraderConfig> = {}
): Trader {
    const defaultConfig: Partial<TraderConfig> = {
        rpcEndpoint,
        wssEndpoint,
        privateKey,
        buyAmountSol,
        buySlippageBps: 100, // 1%
        sellSlippageBps: 2500, // 25%
        listenerType: 'logs', // Default listener
    };
    return new Trader({ ...defaultConfig, ...customConfig } as TraderConfig);
}
