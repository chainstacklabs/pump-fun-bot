import { PublicKey, Connection } from '@solana/web3.js';
import { SolanaClient } from '../client'; // Adjust path as necessary
import { PriorityFeePlugin } from './manager'; // Adjust path as necessary

// TODO: Replace with a proper logger if needed
const logger = {
  info: (...args: any[]) => console.log(...args),
  warn: (...args: any[]) => console.warn(...args),
  error: (...args: any[]) => console.error(...args),
};

// Helper function to calculate quantiles, similar to Python's statistics.quantiles
function calculateQuantiles(data: number[], n: number): number[] {
  if (n <= 0) throw new Error("Number of quantiles (n) must be positive.");
  if (data.length === 0) return [];

  const sortedData = [...data].sort((a, b) => a - b);
  const result: number[] = [];
  for (let i = 1; i < n; i++) {
    const index = (sortedData.length -1) * (i / n);
    const lower = Math.floor(index);
    const upper = Math.ceil(index);
    if (lower === upper) {
      result.push(sortedData[lower]);
    } else {
      // Linear interpolation
      result.push(sortedData[lower] * (upper - index) + sortedData[upper] * (index - lower));
    }
  }
  return result;
}


export class DynamicPriorityFee implements PriorityFeePlugin {
  private client: SolanaClient; // Using SolanaClient which encapsulates Connection
  private connection: Connection; // Direct connection for methods not in SolanaClient

  /**
   * Initialize the dynamic fee plugin.
   * @param client SolanaClient for network requests.
   * @param connection Direct Connection object from @solana/web3.js
   */
  constructor(client: SolanaClient, connection: Connection) {
    this.client = client;
    this.connection = connection;
  }

  /**
   * Fetch the recent priority fee using getRecentPrioritizationFees.
   * @param accounts List of accounts to consider for the fee calculation.
   *                 If null or empty, the fee is calculated without specific account constraints.
   * @returns Median priority fee in microlamports, or null if the request fails.
   */
  public async getPriorityFee(accounts?: PublicKey[]): Promise<number | null> {
    try {
      // @solana/web3.js has getRecentPrioritizationFees directly on the Connection object.
      const prioritizationFees = await this.connection.getRecentPrioritizationFees({
        lockedWritableAccounts: accounts && accounts.length > 0 ? accounts : undefined,
      });

      if (!prioritizationFees || prioritizationFees.length === 0) {
        logger.warn("No prioritization fees found in the response");
        return null;
      }

      // Extract the prioritizationFee values
      const fees = prioritizationFees.map(fee => fee.prioritizationFee);
      if (fees.length === 0) {
        logger.warn("No valid fee values extracted from prioritization fees response");
        return null;
      }

      // Get the 70th percentile of fees for faster processing
      // Higher percentile = faster transactions but more expensive
      // Lower percentile = cheaper but slower transactions
      if (fees.length < 2 && fees.length > 0) { // Not enough data for quantiles, use the single value or average if multiple but less than needed for 10 quantiles
          return Math.floor(fees.reduce((a,b) => a+b,0) / fees.length);
      }
      if (fees.length < 2 ) { // if still no fees (e.g. length 0)
        logger.warn("Not enough fee data points to calculate 70th percentile.");
        return null; // Or a default fee, or average if applicable
      }

      const quantiles = calculateQuantiles(fees, 10); // Calculate deciles
      // 70th percentile is the 7th element if quantiles were 0-indexed for 10 quantiles (q[6])
      // For n=10, quantiles returns 9 values (q1 to q9). q[6] is the 7th decile (70th percentile).
      const seventiethPercentileIndex = 6; // For n=10, quantiles are q[0]...q[8] (9 values)
                                        // q[0] = 10th, q[1]=20th ... q[6]=70th
      if (quantiles.length <= seventiethPercentileIndex) {
          logger.warn(`Not enough quantiles generated (${quantiles.length}) to pick 70th percentile. Using highest available.`);
          return Math.floor(quantiles[quantiles.length-1]);
      }
      const priorityFee = Math.floor(quantiles[seventiethPercentileIndex]);


      return priorityFee;

    } catch (e: any) {
      logger.error(`Failed to fetch recent priority fee: ${e.message}`, e);
      return null;
    }
  }
}
