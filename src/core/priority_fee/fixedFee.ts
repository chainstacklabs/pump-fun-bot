import { PriorityFeePlugin } from './manager'; // Assuming PriorityFeePlugin is in manager.ts or a base file

export class FixedPriorityFee implements PriorityFeePlugin {
  private fixedFee: number;

  /**
   * Initialize the fixed fee plugin.
   * @param fixedFee Fixed priority fee in microlamports.
   */
  constructor(fixedFee: number) {
    this.fixedFee = fixedFee;
  }

  /**
   * Return the fixed priority fee.
   * @returns Fixed priority fee in microlamports, or null if fixedFee is 0.
   */
  public async getPriorityFee(): Promise<number | null> {
    if (this.fixedFee === 0) {
      return null;
    }
    return this.fixedFee;
  }
}
