import { PublicKey } from '@solana/web3.js';
import { SolanaClient } from '../core/client'; // Adjust path as necessary
import { Wallet } from '../core/wallet';     // Adjust path as necessary
import { pumpFunProgramId, pumpFunFeeRecipient } from '../core/pubkeys'; // Assuming PUMP_FUN_PROGRAM and PUMP_FUN_FEE_RECIPIENT

// From Python's TokenInfo dataclass
export interface TokenInfo {
  name: string;
  symbol: string;
  uri: string;
  mint: PublicKey;
  bondingCurve: PublicKey;
  associatedBondingCurve: PublicKey; // This might be the same as bondingCurve if it's the ATA for the curve
  user: PublicKey; // The account that initiated the create, likely the fee payer or trader
  creator: PublicKey;
  creatorVault: PublicKey; // PDA for the creator's vault
}

// Helper function to create TokenInfo from a plain object, similar to from_dict
export function tokenInfoFromPlain(data: { [key: string]: any }): TokenInfo {
  if (!data.name || !data.symbol || !data.uri || !data.mint || !data.bondingCurve || !data.associatedBondingCurve || !data.user || !data.creator || !data.creatorVault) {
    throw new Error("Missing required fields for TokenInfo construction from plain object.");
  }
  return {
    name: data.name,
    symbol: data.symbol,
    uri: data.uri,
    mint: new PublicKey(data.mint),
    bondingCurve: new PublicKey(data.bondingCurve),
    associatedBondingCurve: new PublicKey(data.associatedBondingCurve),
    user: new PublicKey(data.user),
    creator: new PublicKey(data.creator),
    creatorVault: new PublicKey(data.creatorVault),
  };
}

// Helper function to convert TokenInfo to a plain object, similar to to_dict
export function tokenInfoToPlain(tokenInfo: TokenInfo): { [key: string]: string } {
  return {
    name: tokenInfo.name,
    symbol: tokenInfo.symbol,
    uri: tokenInfo.uri,
    mint: tokenInfo.mint.toBase58(),
    bondingCurve: tokenInfo.bondingCurve.toBase58(),
    associatedBondingCurve: tokenInfo.associatedBondingCurve.toBase58(),
    user: tokenInfo.user.toBase58(),
    creator: tokenInfo.creator.toBase58(),
    creatorVault: tokenInfo.creatorVault.toBase58(),
  };
}


// From Python's TradeResult dataclass
export interface TradeResult {
  success: boolean;
  txSignature?: string | null;
  errorMessage?: string | null;
  amount?: number | null; // Amount of tokens bought/sold or SOL spent/received
  price?: number | null;  // Effective price of the trade
}

// Placeholder for Config type
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type TradingConfig = any;


// Based on Python's Trader abstract class and subtask instructions for TradingBase
export class TradingBase {
  protected solanaClient: SolanaClient;
  protected wallet: Wallet;
  protected config: TradingConfig; // Using 'any' for now as specified

  // Basic console logger
  protected logger = {
    info: (...args: unknown[]) => console.log('[TradingBase]', ...args),
    warn: (...args: unknown[]) => console.warn('[TradingBase]', ...args),
    error: (...args: unknown[]) => console.error('[TradingBase]', ...args),
  };

  constructor(solanaClient: SolanaClient, wallet: Wallet, config: TradingConfig) {
    this.solanaClient = solanaClient;
    this.wallet = wallet;
    this.config = config;
  }

  /**
   * Placeholder for an execute method.
   * Concrete trading actions (buy/sell) would extend this or be separate methods.
   * The original Python 'Trader' class had this as an abstract method.
   */
  public async execute(...args: unknown[]): Promise<TradeResult> {
    this.logger.info('TradingBase.execute called with args:', args);
    // This is a placeholder. Concrete implementations (like a Buyer or Seller class)
    // would override this or provide specific buy/sell methods.
    return {
      success: false,
      errorMessage: "Execute method not implemented in TradingBase.",
    };
  }

  /**
   * Get the list of accounts relevant for calculating the priority fee.
   * Converted from _get_relevant_accounts in Python's Trader class.
   * @param tokenInfo Token information for the buy/sell operation.
   * @returns List of relevant PublicKeys.
   */
  protected getRelevantAccounts(tokenInfo: TokenInfo): PublicKey[] {
    return [
      tokenInfo.mint,             // Token mint address
      tokenInfo.bondingCurve,     // Bonding curve address
      pumpFunProgramId,        // Pump.fun program address from pubkeys.ts
      pumpFunFeeRecipient,     // Pump.fun fee account from pubkeys.ts
    ];
  }
}
