import {
  Connection,
  PublicKey,
  Keypair,
  Transaction,
  sendAndConfirmTransaction,
  Blockhash,
  FeeCalculator,
  Commitment,
  RpcResponseAndContext,
  SignatureResult,
  AccountInfo,
  TransactionInstruction,
  ComputeBudgetProgram,
  Message,
  VersionedTransaction,
} from '@solana/web3.js';
import fetch from 'cross-fetch'; // For making HTTP requests, similar to aiohttp

// Assuming pubkeys might be needed, though not directly in the Python version for client itself
// import * as pubkeys from './pubkeys';

// TODO: Replace with a proper logger if needed, for now console will do.
const logger = {
  info: (...args: any[]) => console.log(...args),
  warn: (...args: any[]) => console.warn(...args),
  error: (...args: any[]) => console.error(...args),
};

export interface TokenAccountBalance {
  amount: string;
  decimals: number;
  uiAmount: number | null;
  uiAmountString: string | null;
}

export class SolanaClient {
  private rpcEndpoint: string;
  private connection: Connection;
  private cachedBlockhash: Blockhash | null = null;
  private blockhashLock: Promise<void> = Promise.resolve(); // Simple lock mechanism
  private blockhashUpdaterIntervalId: NodeJS.Timeout | null = null;

  constructor(rpcEndpoint: string) {
    this.rpcEndpoint = rpcEndpoint;
    this.connection = new Connection(rpcEndpoint, 'processed');
    this.startBlockhashUpdater().catch(error => logger.error("Failed to start blockhash updater:", error));
  }

  private async startBlockhashUpdater(intervalSeconds: number = 5.0): Promise<void> {
    const update = async () => {
      try {
        const blockhashResult = await this.connection.getLatestBlockhash('processed');
        await this.blockhashLock; // Wait for previous lock to release
        this.blockhashLock = (async () => { // Acquire lock
          this.cachedBlockhash = blockhashResult.blockhash;
        })();
        await this.blockhashLock; // Wait for current update to complete
      } catch (e: any) {
        logger.warn(`Blockhash fetch failed: ${e.message}`);
      }
    };

    await update(); // Initial update
    this.blockhashUpdaterIntervalId = setInterval(update, intervalSeconds * 1000);
  }

  public async getCachedBlockhash(): Promise<Blockhash> {
    await this.blockhashLock; // Ensure no race condition / read during update
    if (!this.cachedBlockhash) {
      // Fallback if cache is somehow null, though updater should prevent this
      logger.warn("Cached blockhash was null, fetching new one directly.");
      const blockhashResult = await this.connection.getLatestBlockhash('processed');
      this.cachedBlockhash = blockhashResult.blockhash;
    }
    if (!this.cachedBlockhash) {
        throw new Error("No cached blockhash available yet and fallback failed.");
    }
    return this.cachedBlockhash;
  }

  public async close(): Promise<void> {
    if (this.blockhashUpdaterIntervalId) {
      clearInterval(this.blockhashUpdaterIntervalId);
      this.blockhashUpdaterIntervalId = null;
    }
    // Connection in @solana/web3.js doesn't have an explicit close method for HTTP connections.
    // If using WebSockets, it would be `this.connection.removeBlockhashSubscriber()` or similar.
    logger.info("SolanaClient closed (blockhash updater stopped).");
  }

  public async getHealth(): Promise<string | null> {
    // web3.js Connection does not have a direct getHealth method like solders.
    // We can try a basic RPC call.
    try {
      const health = await this.connection.getHealth();
      return health;
    } catch (error: any) {
      logger.error(`getHealth failed: ${error.message}`);
      return null;
    }
  }

  public async getAccountInfo(pubkey: PublicKey): Promise<AccountInfo<Buffer> | null> {
    try {
      const accountInfo = await this.connection.getAccountInfo(pubkey, 'processed');
      if (!accountInfo) {
        // Differentiate between not found and other errors if necessary
        // logger.warn(`Account ${pubkey.toBase58()} not found.`);
        return null; // Explicitly return null if account not found, as per web3.js behavior
      }
      return accountInfo;
    } catch (error: any) {
      logger.error(`Failed to get account info for ${pubkey.toBase58()}: ${error.message}`);
      throw new Error(`Failed to get account info: ${error.message}`);
    }
  }

  public async getTokenAccountBalance(tokenAccount: PublicKey): Promise<TokenAccountBalance | null> {
    try {
      const response = await this.connection.getTokenAccountBalance(tokenAccount, 'processed');
      if (response.value) {
        return response.value;
      }
      return null;
    } catch (error: any) {
      logger.error(`Failed to get token account balance for ${tokenAccount.toBase58()}: ${error.message}`);
      return null; // Or throw, depending on desired error handling
    }
  }

  public async getLatestBlockhashInfo(): Promise<{ blockhash: Blockhash; lastValidBlockHeight: number; feeCalculator?: FeeCalculator }> {
      return this.connection.getLatestBlockhash('processed');
  }


  public async buildAndSendTransaction(
    instructions: TransactionInstruction[],
    signerKeypair: Keypair,
    skipPreflight: boolean = true,
    maxRetries: number = 3, // web3.js sendAndConfirmTransaction has its own retry logic
    priorityFeeMicroLamports: number | null = null
  ): Promise<string> {
    logger.info(`Priority fee in microlamports: ${priorityFeeMicroLamports ?? 0}`);

    const allInstructions = [];
    if (priorityFeeMicroLamports !== null && priorityFeeMicroLamports > 0) {
      allInstructions.push(
        ComputeBudgetProgram.setComputeUnitLimit({ units: 72_000 }) // Default from Python
      );
      allInstructions.push(
        ComputeBudgetProgram.setComputeUnitPrice({ microLamports: priorityFeeMicroLamports })
      );
    }
    allInstructions.push(...instructions);

    let attempt = 0;
    while (attempt < maxRetries) {
      try {
        const { blockhash, lastValidBlockHeight } = await this.getLatestBlockhashInfo();

        const messageV0 = new Message({
            payerKey: signerKeypair.publicKey,
            recentBlockhash: blockhash,
            instructions: allInstructions,
        }).compileToV0Message();

        const transaction = new VersionedTransaction(messageV0);
        transaction.sign([signerKeypair]);

        // `sendAndConfirmTransaction` handles retries and confirmation internally
        // but we are doing manual retries to mimic the python code's exponential backoff
        const signature = await this.connection.sendTransaction(transaction, {
          skipPreflight: skipPreflight,
          maxRetries: 0, // Disable internal retries of sendTransaction to use custom loop
          preflightCommitment: 'processed',
        });

        // Manual confirmation polling with timeout
        const confirmation = await this.connection.confirmTransaction({
            signature,
            blockhash,
            lastValidBlockHeight
        }, 'confirmed');

        if (confirmation.value.err) {
            throw new Error(`Transaction confirmation failed: ${JSON.stringify(confirmation.value.err)}`);
        }

        return signature;

      } catch (e: any) {
        attempt++;
        if (attempt >= maxRetries) {
          logger.error(`Failed to send transaction after ${maxRetries} attempts: ${e.message}`);
          throw e;
        }
        const waitTime = Math.pow(2, attempt -1); // Exponential backoff, starting with 1s for first retry
        logger.warn(
          `Transaction attempt ${attempt} failed: ${e.message}, retrying in ${waitTime}s`
        );
        await new Promise(resolve => setTimeout(resolve, waitTime * 1000));
      }
    }
    // Should not be reached if maxRetries is > 0
    throw new Error("Transaction failed after all retries.");
  }

  public async confirmTransaction(
    signature: string,
    commitment: Commitment = 'confirmed',
    blockhash?: Blockhash,
    lastValidBlockHeight?: number
  ): Promise<RpcResponseAndContext<SignatureResult>> {
    // Note: confirmTransaction in web3.js requires blockhash and lastValidBlockHeight
    // if not using 'finalized' commitment. We should try to pass these if available.
    if (!blockhash || !lastValidBlockHeight) {
        logger.warn("Attempting to confirm transaction without blockhash and lastValidBlockHeight. This might lead to issues if not using 'finalized'.");
        // Fetch them if not provided, though this might use a newer blockhash
        const latestBlockhashInfo = await this.getLatestBlockhashInfo();
        blockhash = latestBlockhashInfo.blockhash;
        lastValidBlockHeight = latestBlockhashInfo.lastValidBlockHeight;
    }

    try {
      const result = await this.connection.confirmTransaction(
        {signature, blockhash, lastValidBlockHeight},
        commitment
      );
      return result;
    } catch (e: any) {
      logger.error(`Failed to confirm transaction ${signature}: ${e.message}`);
      throw e; // Re-throw to allow caller to handle
    }
  }

  public async postRpc(body: { [key: string]: any }): Promise<any | null> {
    // This method is less common with web3.js as it provides higher-level abstractions.
    // However, if needed for specific RPC calls not covered:
    try {
      const response = await fetch(this.rpcEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
        timeout: 10000, // 10-second timeout
      });

      if (!response.ok) {
        throw new Error(`RPC request failed with status ${response.status}: ${await response.text()}`);
      }
      return await response.json();
    } catch (e: any) {
      logger.error(`RPC request failed: ${e.message}`, e);
      return null;
    }
  }
}
