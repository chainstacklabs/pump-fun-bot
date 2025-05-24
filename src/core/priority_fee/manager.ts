import { PublicKey, Connection } from '@solana/web3.js';
import { SolanaClient } from '../client'; // Adjust path as necessary
import { DynamicPriorityFee } from './dynamicFee'; // Assuming DynamicPriorityFee is in dynamicFee.ts
import { FixedPriorityFee } from './fixedFee'; // Assuming FixedPriorityFee is in fixedFee.ts

// TODO: Replace with a proper logger if needed
const logger = {
  info: (...args: any[]) => console.log(...args),
  warn: (...args: any[]) => console.warn(...args),
  error: (...args: any[]) => console.error(...args),
};

/**
 * Defines the interface for a priority fee plugin.
 * Any class that calculates priority fees should implement this interface.
 */
export interface PriorityFeePlugin {
  getPriorityFee(accounts?: PublicKey[]): Promise<number | null>;
}

export class PriorityFeeManager {
  private client: SolanaClient; // Retain SolanaClient if it's used by plugins or for other ops
  private connection: Connection; // Direct connection for methods like getRecentPrioritizationFees
  private enableDynamicFee: boolean;
  private enableFixedFee: boolean;
  // private fixedFeeValue: number; // Renamed from fixed_fee to avoid confusion with FixedPriorityFee class
  private extraFeePercentage: number; // Renamed from extra_fee
  private hardCapMicroLamports: number; // Renamed from hard_cap

  private dynamicFeePlugin: DynamicPriorityFee;
  private fixedFeePlugin: FixedPriorityFee;

  /**
   * Initialize the priority fee manager.
   * @param client SolanaClient for dynamic fee calculation or other operations.
   * @param connection Direct Connection object from @solana/web3.js.
   * @param enableDynamicFee Whether to enable dynamic fee calculation.
   * @param enableFixedFee Whether to enable fixed fee.
   * @param fixedFee Fixed priority fee in microlamports (used for FixedPriorityFee plugin).
   * @param extraFee Percentage increase to apply to the base fee (e.g., 0.1 for 10%).
   * @param hardCap Maximum allowed priority fee in microlamports.
   */
  constructor(
    client: SolanaClient,
    connection: Connection,
    enableDynamicFee: boolean,
    enableFixedFee: boolean,
    fixedFee: number, // This is the value for the fixed fee, not the plugin instance itself
    extraFee: number,
    hardCap: number
  ) {
    this.client = client;
    this.connection = connection;
    this.enableDynamicFee = enableDynamicFee;
    this.enableFixedFee = enableFixedFee;
    // this.fixedFeeValue = fixedFee; // Storing the raw value if needed, though plugin holds it too
    this.extraFeePercentage = extraFee;
    this.hardCapMicroLamports = hardCap;

    // Initialize plugins
    this.dynamicFeePlugin = new DynamicPriorityFee(this.client, this.connection);
    this.fixedFeePlugin = new FixedPriorityFee(fixedFee); // Pass the numeric fee value
  }

  /**
   * Calculate the priority fee based on the configuration.
   * @param accounts List of accounts to consider for dynamic fee calculation.
   *                 If null or empty, the fee is calculated without specific account constraints.
   * @returns Calculated priority fee in microlamports, or null if no fee should be applied.
   */
  public async calculatePriorityFee(accounts?: PublicKey[]): Promise<number | null> {
    const baseFee = await this.getBaseFee(accounts);
    if (baseFee === null) {
      return null;
    }

    // Apply extra fee (percentage increase)
    // Ensure extraFeePercentage is used correctly (e.g., 0.1 for 10% NOT 10 for 10%)
    const finalFee = Math.floor(baseFee * (1 + this.extraFeePercentage));

    // Enforce hard cap
    if (finalFee > this.hardCapMicroLamports) {
      logger.warn(
        `Calculated priority fee ${finalFee} μL exceeds hard cap ${this.hardCapMicroLamports} μL. Applying hard cap.`
      );
      return this.hardCapMicroLamports;
    }
    
    if (finalFee <= 0) {
        logger.info(`Final calculated priority fee is ${finalFee} μL. No priority fee will be applied.`);
        return null;
    }

    return finalFee;
  }

  private async getBaseFee(accounts?: PublicKey[]): Promise<number | null> {
    // Prefer dynamic fee if both are enabled and dynamic returns a valid fee
    if (this.enableDynamicFee) {
      const dynamicFee = await this.dynamicFeePlugin.getPriorityFee(accounts);
      if (dynamicFee !== null && dynamicFee > 0) { // Check if dynamic fee is valid and positive
        logger.info(`Using dynamic fee: ${dynamicFee} μL`);
        return dynamicFee;
      }
      if (dynamicFee !== null && dynamicFee <=0) {
        logger.info(`Dynamic fee plugin returned ${dynamicFee} μL. This is considered as no fee.`);
      }
      // If dynamic fee is null (error or no data), we might fall back or return null based on strictness
      // For now, if dynamicFee is null, it means it couldn't determine a fee.
      // If only dynamic is enabled and it fails, we return null.
      // If both are enabled and dynamic fails, we try fixed.
      if (dynamicFee === null && !this.enableFixedFee) {
        logger.warn("Dynamic fee enabled but failed to retrieve a fee, and fixed fee is not enabled.");
        return null;
      }
       if (dynamicFee === null && this.enableFixedFee) {
        logger.warn("Dynamic fee enabled but failed to retrieve a fee. Falling back to fixed fee if enabled.");
      }
    }

    // Fall back to fixed fee if enabled (either dynamic is disabled, or dynamic failed and fixed is enabled)
    if (this.enableFixedFee) {
      const fixedFee = await this.fixedFeePlugin.getPriorityFee(); // Fixed fee doesn't use accounts
      if (fixedFee !== null && fixedFee > 0) {
        logger.info(`Using fixed fee: ${fixedFee} μL`);
        return fixedFee;
      }
      if (fixedFee !== null && fixedFee <=0) {
         logger.info(`Fixed fee plugin returned ${fixedFee} μL. This is considered as no fee.`);
      }
    }
    
    // If dynamic was enabled but returned null/zero, and fixed is also enabled but returns null/zero
    if (this.enableDynamicFee && this.enableFixedFee) {
        logger.info("Both dynamic and fixed fees are enabled, but neither provided a positive fee.");
    }


    // No priority fee if both are disabled or both failed to provide a positive fee
    logger.info("No priority fee to apply (either disabled or plugins returned no fee).");
    return null;
  }
}
