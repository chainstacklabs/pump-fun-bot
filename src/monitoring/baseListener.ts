import { SolanaClient } from '../core/client'; // Adjust path if client.ts is elsewhere or named differently
import { Wallet } from '../core/wallet';     // Adjust path if wallet.ts is elsewhere or named differently

// Placeholder for Trader until it's defined
interface Trader {
  // Define methods and properties of Trader if known, otherwise leave empty
  // Example: handleNewToken(tokenInfo: any): Promise<void>;
}

// Define a more specific type for the callback if possible
export type EventCallback = (data: any) => Promise<void>;

export abstract class BaseListener {
  protected solanaClient: SolanaClient;
  protected wallet: Wallet;
  protected trader: Trader; // Using placeholder Trader interface
  protected callback: EventCallback;

  constructor(
    solanaClient: SolanaClient,
    wallet: Wallet,
    trader: Trader, // Using placeholder Trader interface
    callback: EventCallback
  ) {
    this.solanaClient = solanaClient;
    this.wallet = wallet;
    this.trader = trader;
    this.callback = callback;
  }

  /**
   * Starts the listener.
   * Concrete implementations should define how listening is initiated.
   */
  abstract start(): Promise<void>;

  /**
   * Stops the listener.
   * Concrete implementations should define how listening is terminated and resources are cleaned up.
   */
  abstract stop(): Promise<void>;
}
