import {
  PublicKey,
  TransactionInstruction,
  AccountMeta,
  SystemProgram,
} from '@solana/web3.js';
import {
  createAssociatedTokenAccountInstruction,
  getAssociatedTokenAddress, // To get the ATA address if needed before creating instruction
  TOKEN_PROGRAM_ID,
} from '@solana/spl-token';
import { Buffer } from 'buffer';
import * as borsh from '@project-serum/borsh'; // For struct packing if simple, or manual Buffer manipulation

import { TradingBase, TokenInfo, TradeResult, TradingConfig } from './baseTrader';
import { SolanaClient } from '../core/client';
import { Wallet } from '../core/wallet';
import { BondingCurveManager } from '../core/curve'; // Python used BondingCurveManager
import { PriorityFeeManager } from '../core/priority_fee';
import {
  lamportsPerSol,
  tokenDecimals,
  pumpFunProgramId,
  pumpFunGlobal,
  pumpFunFeeRecipient,
  pumpFunEventAuthority,
  // systemProgramId is SystemProgram.programId
  // tokenProgramId is TOKEN_PROGRAM_ID from @solana/spl-token
} from '../core/pubkeys';

// Discriminator for the buy instruction from Python: 16927863322537952870
// Hex: ee628be18ff39a66 (little-endian)
const BUY_DISCRIMINATOR_STR = "669af38fe18b62ee"; // 16927863322537952870 as little-endian hex string
const BUY_DISCRIMINATOR = Buffer.from(BUY_DISCRIMINATOR_STR, "hex");


// Define a more specific config type if possible, extending TradingConfig
export interface BuyerConfig extends TradingConfig {
  amountSol: number; // Amount of SOL to spend
  slippageBps?: number; // Slippage tolerance in basis points (e.g., 100 for 1%)
  maxRetries?: number;
  extremeFastTokenAmount?: number; // Amount of token to buy if extreme fast mode is enabled
  extremeFastMode?: boolean;     // If enabled, avoid fetching associated bonding curve state
  priorityFeeManager: PriorityFeeManager; // Make it mandatory for buyer
  bondingCurveManager: BondingCurveManager; // Make it mandatory for buyer
}

export class TokenBuyer extends TradingBase {
  private bondingCurveManager: BondingCurveManager;
  private priorityFeeManager: PriorityFeeManager;
  private amountSol: number;
  private slippageBps: number; // Basis points, e.g., 100 = 1%
  private maxRetries: number;
  private extremeFastMode: boolean;
  private extremeFastTokenAmount: number;

  constructor(
    solanaClient: SolanaClient,
    wallet: Wallet,
    config: BuyerConfig, // Use the more specific BuyerConfig
  ) {
    super(solanaClient, wallet, config); // Pass general config up
    
    // Specific config for TokenBuyer
    this.bondingCurveManager = config.bondingCurveManager;
    this.priorityFeeManager = config.priorityFeeManager;
    this.amountSol = config.amountSol;
    this.slippageBps = config.slippageBps ?? 100; // Default 1% slippage (100 bps)
    this.maxRetries = config.maxRetries ?? 5;
    this.extremeFastMode = config.extremeFastMode ?? false;
    this.extremeFastTokenAmount = config.extremeFastTokenAmount ?? 0;

    if (this.extremeFastMode && this.extremeFastTokenAmount <= 0) {
      this.logger.warn("TokenBuyer: extremeFastMode is enabled but extremeFastTokenAmount is not set or invalid. It might lead to errors.");
    }
  }

  /**
   * Executes the buy operation for a given token.
   * @param tokenInfo Information about the token to buy.
   * @returns A TradeResult object indicating the outcome of the buy operation.
   */
  public async execute(tokenInfo: TokenInfo): Promise<TradeResult> {
    this.logger.info(`Attempting to buy token: ${tokenInfo.name} (${tokenInfo.symbol})`);
    try {
      const amountLamports = Math.floor(this.amountSol * lamportsPerSol);
      let tokenAmountToBuy: number; // Amount of tokens expected to receive
      let tokenPriceSol: number;   // Calculated price in SOL per token

      if (this.extremeFastMode && this.extremeFastTokenAmount > 0) {
        tokenAmountToBuy = this.extremeFastTokenAmount;
        tokenPriceSol = this.amountSol / tokenAmountToBuy;
        this.logger.info(`EXTREME FAST Mode: Targeting to buy ${tokenAmountToBuy} tokens.`);
      } else {
        const curveState = await this.bondingCurveManager.getCurveState(tokenInfo.bondingCurve);
        tokenPriceSol = curveState.calculatePrice();
        if (tokenPriceSol <= 0) {
          throw new Error("Calculated token price is zero or negative, cannot proceed with buy.");
        }
        tokenAmountToBuy = this.amountSol / tokenPriceSol;
      }

      // Calculate maximum SOL to spend with slippage
      // slippageBps (e.g., 100 for 1%) means max_amount_lamports = amount_lamports * (1 + 100/10000)
      const maxAmountLamports = Math.floor(amountLamports * (1 + this.slippageBps / 10000));
      
      const userAssociatedTokenAccount = await getAssociatedTokenAddress(
        tokenInfo.mint,
        this.wallet.pubkey // Owner of the ATA
      );

      this.logger.info(`Targeting to buy ~${tokenAmountToBuy.toFixed(6)} tokens of ${tokenInfo.symbol}.`);
      this.logger.info(`User ATA for ${tokenInfo.mint.toBase58()}: ${userAssociatedTokenAccount.toBase58()}`);
      this.logger.info(`Max SOL to spend (incl. slippage ${this.slippageBps/100}%): ${(maxAmountLamports / lamportsPerSol).toFixed(6)} SOL`);

      const txSignature = await this.sendBuyTransaction(
        tokenInfo,
        userAssociatedTokenAccount,
        tokenAmountToBuy,
        maxAmountLamports
      );

      this.logger.info(`Buy transaction sent: ${txSignature}. Confirming...`);
      
      const { blockhash, lastValidBlockHeight } = await this.solanaClient.getLatestBlockhashInfo();
      const confirmation = await this.solanaClient.confirmTransaction(txSignature, 'confirmed', blockhash, lastValidBlockHeight);

      if (confirmation && !confirmation.value.err) {
        this.logger.info(`Buy transaction confirmed: ${txSignature}`);
        return {
          success: true,
          txSignature: txSignature,
          amount: tokenAmountToBuy, // Amount of tokens bought
          price: tokenPriceSol,    // Effective price per token in SOL
        };
      } else {
        this.logger.error(`Buy transaction failed to confirm or confirmed with error: ${txSignature}`, confirmation?.value.err);
        return {
          success: false,
          txSignature: txSignature,
          errorMessage: `Transaction failed to confirm or confirmed with error: ${JSON.stringify(confirmation?.value.err)}`,
        };
      }
    } catch (e: any) {
      this.logger.error(`Buy operation for ${tokenInfo.name} failed: ${e.message}`, e.stack);
      return { success: false, errorMessage: e.message };
    }
  }

  private async sendBuyTransaction(
    tokenInfo: TokenInfo,
    userAssociatedTokenAccount: PublicKey,
    tokenAmount: number, // Expected amount of tokens to receive
    maxAmountLamports: number // Max SOL lamports to spend
  ): Promise<string> {
    const accounts: AccountMeta[] = [
      { pubkey: pumpFunGlobal, isSigner: false, isWritable: false },
      { pubkey: pumpFunFeeRecipient, isSigner: false, isWritable: true }, // fee_recipient
      { pubkey: tokenInfo.mint, isSigner: false, isWritable: false },
      { pubkey: tokenInfo.bondingCurve, isSigner: false, isWritable: true },
      { pubkey: tokenInfo.associatedBondingCurve, isSigner: false, isWritable: true }, // bonding_curve_token_ata
      { pubkey: userAssociatedTokenAccount, isSigner: false, isWritable: true }, // user_token_ata
      { pubkey: this.wallet.pubkey, isSigner: true, isWritable: true }, // user (signer)
      { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
      { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
      // The Python code had creator_vault (index 9), event_authority (index 10), pump_program (index 11)
      // These are often specific to the program's requirements for a 'buy' instruction.
      { pubkey: tokenInfo.creatorVault, isSigner: false, isWritable: true }, // creator_vault
      { pubkey: pumpFunEventAuthority, isSigner: false, isWritable: false }, // event_authority
      { pubkey: pumpFunProgramId, isSigner: false, isWritable: false }, // pump_program (itself, if needed in accounts list)
    ];
    
    // Create ATA instruction - this is often included to ensure the user's token account exists.
    // The instruction should ideally be idempotent or checked for existence beforehand if strictness is needed.
    // For pump.fun, often the buy instruction itself handles ATA creation if it's the first interaction.
    // However, the Python code explicitly adds an idempotent ATA creation.
    // createAssociatedTokenAccountInstruction is not idempotent by default if account exists.
    // A common pattern is to just send it. If it fails because account exists, tx fails.
    // For true idempotency like Python's create_idempotent_associated_token_account,
    // you might need to check if account exists first using getAccountInfo, or use a specific instruction if available.
    // For now, we'll include it as per the Python code's intention.
    // Note: The payer for create ATA is typically the user/wallet.
    const ataInstruction = createAssociatedTokenAccountInstruction(
      this.wallet.pubkey,            // payer
      userAssociatedTokenAccount,   // ata
      this.wallet.pubkey,            // owner
      tokenInfo.mint                // mint
    );

    // Prepare buy instruction data
    // struct.pack("<Q", token_amount_raw) + struct.pack("<Q", max_amount_lamports)
    const tokenAmountRaw = BigInt(Math.floor(tokenAmount * Math.pow(10, tokenDecimals)));
    const maxAmountLamportsBigInt = BigInt(maxAmountLamports);

    const dataBuffer = Buffer.alloc(16); // 8 bytes for token_amount_raw, 8 bytes for max_amount_lamports
    dataBuffer.writeBigUInt64LE(tokenAmountRaw, 0);
    dataBuffer.writeBigUInt64LE(maxAmountLamportsBigInt, 8);
    
    const buyInstructionData = Buffer.concat([BUY_DISCRIMINATOR, dataBuffer]);

    const buyInstruction = new TransactionInstruction({
      keys: accounts,
      programId: pumpFunProgramId,
      data: buyInstructionData,
    });

    const instructions = [ataInstruction, buyInstruction];
    
    const relevantAccountsForFee = this.getRelevantAccounts(tokenInfo); // From TradingBase
    const priorityFee = await this.priorityFeeManager.calculatePriorityFee(relevantAccountsForFee);

    try {
      return await this.solanaClient.buildAndSendTransaction(
        instructions,
        this.wallet.keypair,
        true, // skipPreflight
        this.maxRetries,
        priorityFee // Optional priority fee in microLamports
      );
    } catch (e: any) {
      this.logger.error(`_sendBuyTransaction failed: ${e.message}`, e.stack);
      throw e; // Re-throw to be caught by execute method
    }
  }
}
