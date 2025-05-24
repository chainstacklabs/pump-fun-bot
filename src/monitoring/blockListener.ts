import WebSocket from 'ws';
import { PublicKey } from '@solana/web3.js';
import { BaseListener, EventCallback } from './baseListener'; // Assuming EventCallback is exported
import { PumpEventProcessor, TokenInfo } from './blockEventProcessor'; // Assuming TokenInfo is exported
import { SolanaClient } from '../core/client';
import { Wallet } from '../core/wallet';
import { pumpFunProgramId } from '../core/pubkeys'; // Default program ID

// Placeholder for Trader
interface Trader {
  // Define methods and properties of Trader if known
}

const logger = {
  info: (...args: any[]) => console.log('[BlockListener]', ...args),
  warn: (...args: any[]) => console.warn('[BlockListener]', ...args),
  error: (...args: any[]) => console.error('[BlockListener]', ...args),
  debug: (...args: any[]) => console.debug('[BlockListener]', ...args), // For verbose logs
};

// Type for the blockSubscribe response structure (simplified)
interface BlockNotification {
  jsonrpc: string;
  method: string;
  params?: {
    result?: {
      value?: {
        block?: {
          transactions: Array<{
            transaction: [string, string]; // [txData, encoding]
            meta: any; // Transaction metadata
          }>;
        };
      };
    };
    subscription: number;
  };
}


export class BlockListener extends BaseListener {
  private wssEndpoint: string;
  private pumpProgramId: PublicKey;
  private eventProcessor: PumpEventProcessor;
  private pingIntervalMs: number = 20 * 1000; // 20 seconds
  private reconnectDelayMs: number = 5 * 1000; // 5 seconds
  private receiveTimeoutMs: number = 30 * 1000; // 30 seconds for message, can be combined with ping logic

  private ws: WebSocket | null = null;
  private pingTimeout: NodeJS.Timeout | null = null;
  private messageReceiveTimeout: NodeJS.Timeout | null = null;
  private shouldBeRunning: boolean = false;
  private currentSubscriptionId: number | null = null;
  
  // Match string and creator address filters
  private matchString: string | null = null;
  private creatorAddress: string | null = null;


  constructor(
    solanaClient: SolanaClient, // Used by BaseListener, may not be directly used by this impl if wss is separate
    wallet: Wallet,             // Used by BaseListener
    trader: Trader,             // Used by BaseListener
    callback: EventCallback,
    wssEndpoint: string, // Specific to this listener implementation
    programIdToWatch: PublicKey = pumpFunProgramId
  ) {
    super(solanaClient, wallet, trader, callback);
    this.wssEndpoint = wssEndpoint;
    this.pumpProgramId = programIdToWatch;
    this.eventProcessor = new PumpEventProcessor(this.pumpProgramId);
  }

  public async start(matchString?: string, creatorAddress?: string): Promise<void> {
    this.matchString = matchString || null;
    this.creatorAddress = creatorAddress || null;
    
    if (this.shouldBeRunning) {
      logger.warn("Listener is already running or trying to start.");
      return;
    }
    this.shouldBeRunning = true;
    logger.info("Starting BlockListener...");
    this.connect();
  }

  public async stop(): Promise<void> {
    logger.info("Stopping BlockListener...");
    this.shouldBeRunning = false;
    if (this.pingTimeout) clearTimeout(this.pingTimeout);
    if (this.messageReceiveTimeout) clearTimeout(this.messageReceiveTimeout);
    
    if (this.ws) {
      if (this.currentSubscriptionId !== null) {
        // Try to unsubscribe, though closing might be faster/sufficient
        try {
          await this.sendJsonRpc("blockUnsubscribe", [this.currentSubscriptionId]);
          logger.info(`Unsubscribed from block notifications (ID: ${this.currentSubscriptionId})`);
        } catch (e: any) {
          logger.warn(`Failed to unsubscribe: ${e.message}`);
        }
      }
      this.ws.close(1000, "Listener stopped by client"); // 1000 is normal closure
      this.ws = null; // Ensure it's cleared for checks
    }
    this.currentSubscriptionId = null;
  }

  private connect(): void {
    if (!this.shouldBeRunning) return;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      logger.info("WebSocket already open or connecting.");
      return;
    }

    logger.info(`Connecting to WebSocket: ${this.wssEndpoint}`);
    this.ws = new WebSocket(this.wssEndpoint);

    this.ws.onopen = () => {
      logger.info("WebSocket connected.");
      this.subscribeToProgram();
      this.schedulePing();
      this.resetMessageReceiveTimeout();
    };

    this.ws.onmessage = (event) => {
      this.resetMessageReceiveTimeout(); // Reset timeout on any message
      try {
        const messageString = event.data.toString();
        const data = JSON.parse(messageString) as BlockNotification;

        if (data.method === "blockNotification" && data.params?.result?.value?.block?.transactions) {
           if (this.currentSubscriptionId === null && data.params?.subscription) {
             // This is how we get the subscription ID from the first notification related to our sub
             // Note: The actual subscription ack comes with "result": <subscription_id>
           }
          this.processBlockTransactions(data.params.result.value.block.transactions);
        } else if (data.params?.subscription && typeof data.params.result === 'number') {
            // This is the subscription confirmation
            this.currentSubscriptionId = data.params.result;
            logger.info(`Successfully subscribed with ID: ${this.currentSubscriptionId}`);
        } else {
          // logger.debug("Received non-blockNotification message or keepalive:", messageString);
        }
      } catch (e: any) {
        logger.error(`Error processing WebSocket message: ${e.message}`);
      }
    };

    this.ws.onerror = (error) => {
      logger.error(`WebSocket error: ${error.message}`);
      // Connection will likely close next, triggering onClose
    };

    this.ws.onclose = (event) => {
      logger.warn(`WebSocket disconnected (code: ${event.code}, reason: ${event.reason}).`);
      if (this.pingTimeout) clearTimeout(this.pingTimeout);
      if (this.messageReceiveTimeout) clearTimeout(this.messageReceiveTimeout);
      this.ws = null; // Important for reconnection logic
      this.currentSubscriptionId = null;

      if (this.shouldBeRunning) {
        logger.info(`Attempting to reconnect in ${this.reconnectDelayMs / 1000} seconds...`);
        setTimeout(() => this.connect(), this.reconnectDelayMs);
      }
    };
  }
  
  private async sendJsonRpc(method: string, params: any[]): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error("WebSocket is not connected.");
    }
    const message = JSON.stringify({
      jsonrpc: "2.0",
      id: Math.floor(Math.random() * 1_000_000), // Unique ID for each request
      method: method,
      params: params,
    });
    this.ws.send(message);
  }


  private async subscribeToProgram(): Promise<void> {
    try {
      await this.sendJsonRpc("blockSubscribe", [
        { mentionsAccountOrProgram: this.pumpProgramId.toBase58() },
        {
          commitment: "confirmed",
          encoding: "base64",
          showRewards: false,
          transactionDetails: "full",
          maxSupportedTransactionVersion: 0,
        },
      ]);
      logger.info(`Subscription request sent for program: ${this.pumpProgramId.toBase58()}`);
    } catch (e: any) {
       logger.error(`Failed to send subscription message: ${e.message}`);
       // Reconnection logic will handle this if ws is closed due to error
    }
  }

  private schedulePing(): void {
    if (this.pingTimeout) clearTimeout(this.pingTimeout);
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN || !this.shouldBeRunning) return;

    this.pingTimeout = setTimeout(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN && this.shouldBeRunning) {
        this.ws.ping((err) => {
            if (err) {
                logger.error("Ping failed, connection might be dead.", err);
                this.ws?.terminate(); // Force close to trigger reconnect
            } else {
                // logger.debug("Ping sent, pong received implicitly by ws library's health check or just sent successfully");
                this.schedulePing(); // Schedule next ping
            }
        });
      }
    }, this.pingIntervalMs);
  }
  
  private resetMessageReceiveTimeout(): void {
    if (this.messageReceiveTimeout) clearTimeout(this.messageReceiveTimeout);
    if (!this.ws || !this.shouldBeRunning) return;

    this.messageReceiveTimeout = setTimeout(() => {
      if (this.ws && this.shouldBeRunning) {
        logger.warn(`No message received for ${this.receiveTimeoutMs / 1000} seconds. Terminating connection to force reconnect.`);
        this.ws.terminate(); // Force close to trigger reconnect
      }
    }, this.receiveTimeoutMs);
  }


  private processBlockTransactions(
    transactions: Array<{ transaction: [string, string]; meta: any }>
  ): void {
    for (const tx of transactions) {
      if (tx && tx.transaction && tx.transaction[0]) { // tx.transaction[0] is the tx data string
        const tokenInfo = this.eventProcessor.processTransaction(tx.transaction[0]);
        if (tokenInfo) {
          this.handleFoundToken(tokenInfo);
        }
      }
    }
  }
  
  private handleFoundToken(tokenInfo: TokenInfo): void {
    logger.info(`New token candidate: ${tokenInfo.name} (${tokenInfo.symbol}) by ${tokenInfo.creator.toBase58()}`);

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
    
    // If all filters pass (or no filters), invoke the callback
    this.callback(tokenInfo).catch(e => {
        logger.error(`Error in token callback for ${tokenInfo.name}: ${e.message}`);
    });
  }
}
