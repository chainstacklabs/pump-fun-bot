import { Connection, PublicKey, Logs, SubscriptionId } from '@solana/web3.js';
import { BaseListener, EventCallback } from './baseListener'; // Assuming EventCallback is exported
import { LogsEventProcessor, TokenInfo } from './logsEventProcessor'; // Assuming TokenInfo is exported
import { SolanaClient } from '../core/client';
import { Wallet } from '../core/wallet';
import { pumpFunProgramId as PUMP_FUN_PROGRAM } from '../core/pubkeys'; // Aliasing for clarity

// Placeholder for Trader
interface Trader {
  // Define methods and properties of Trader if known
}

const logger = {
  info: (...args: any[]) => console.log('[LogsListener]', ...args),
  warn: (...args: any[]) => console.warn('[LogsListener]', ...args),
  error: (...args: any[]) => console.error('[LogsListener]', ...args),
};

export class LogsListener extends BaseListener {
  private logsEventProcessor: LogsEventProcessor;
  private programIdToWatch: PublicKey;
  private subscriptionId: SubscriptionId | null = null;
  
  // Match string and creator address filters
  private matchString: string | null = null;
  private creatorAddress: string | null = null;

  // Access to the underlying Connection object from SolanaClient is needed for onLogs
  private connection: Connection;

  constructor(
    solanaClient: SolanaClient,
    wallet: Wallet,
    trader: Trader, // Using placeholder Trader interface
    callback: EventCallback,
    programIdToWatch: PublicKey = PUMP_FUN_PROGRAM
  ) {
    super(solanaClient, wallet, trader, callback);
    // Expose connection from solanaClient or pass it directly
    // For this conversion, assuming solanaClient has a public 'connection' property
    // If not, the constructor should be: constructor(connection: Connection, wallet: Wallet, ...)
    if (!this.solanaClient.connection) { // 'connection' is not a direct prop of the converted SolanaClient
                                        // Let's assume solanaClient IS the connection for onLogs,
                                        // or that LogsListener needs a direct Connection object.
                                        // For now, let's adjust to require a Connection object directly for clarity.
        throw new Error("LogsListener requires a direct Connection object from @solana/web3.js, not wrapped in SolanaClient for onLogs.");
    }
    this.connection = this.solanaClient.connection; // This was the issue in thought process, SolanaClient has a connection.
    
    this.programIdToWatch = programIdToWatch;
    this.logsEventProcessor = new LogsEventProcessor(this.programIdToWatch);
  }

  public async start(matchString?: string, creatorAddress?: string): Promise<void> {
    this.matchString = matchString || null;
    this.creatorAddress = creatorAddress || null;

    if (this.subscriptionId !== null) {
      logger.warn("Logs listener is already running.");
      return;
    }

    logger.info(`Starting logs listener for program: ${this.programIdToWatch.toBase58()}`);
    
    try {
      this.subscriptionId = this.connection.onLogs(
        this.programIdToWatch,
        (logsResult: Logs, context) => {
          // logger.info(`Received logs for slot ${context.slot}, signature: ${logsResult.signature}`);
          const tokenInfo = this.logsEventProcessor.processLogs(logsResult.logs, logsResult.signature);
          if (tokenInfo) {
            this.handleFoundToken(tokenInfo);
          }
        },
        'processed' // Commitment level, can be 'confirmed' or 'finalized' as well
      );
      logger.info(`Subscribed to logs with subscription ID: ${this.subscriptionId}`);
    } catch (error: any) {
        logger.error(`Error subscribing to logs: ${error.message}`, error);
        this.subscriptionId = null; // Ensure it's reset on failure
    }
  }

  private handleFoundToken(tokenInfo: TokenInfo): void {
    logger.info(`New token candidate via logs: ${tokenInfo.name} (${tokenInfo.symbol}) by ${tokenInfo.creator.toBase58()}, sig: ${tokenInfo.signature}`);

    if (this.matchString) {
      const nameMatch = tokenInfo.name.toLowerCase().includes(this.matchString.toLowerCase());
      const symbolMatch = tokenInfo.symbol.toLowerCase().includes(this.matchString.toLowerCase());
      if (!nameMatch && !symbolMatch) {
        logger.info(`Token does not match filter string '${this.matchString}'. Skipping.`);
        return;
      }
    }

    if (this.creatorAddress && tokenInfo.creator.toBase58() !== this.creatorAddress) {
      logger.info(`Token not created by specified creator ${this.creatorAddress}. Skipping.`);
      return;
    }
    
    this.callback(tokenInfo).catch(e => {
        logger.error(`Error in token callback for ${tokenInfo.name} (sig: ${tokenInfo.signature}): ${e.message}`);
    });
  }

  public async stop(): Promise<void> {
    if (this.subscriptionId !== null) {
      try {
        await this.connection.removeOnLogsListener(this.subscriptionId);
        logger.info(`Unsubscribed from logs with subscription ID: ${this.subscriptionId}`);
        this.subscriptionId = null;
      } catch (error: any) {
        logger.error(`Error unsubscribing from logs (ID: ${this.subscriptionId}): ${error.message}`, error);
      }
    } else {
      logger.warn("Logs listener was not running or already stopped.");
    }
  }
}
