import {
  PublicKey,
  TransactionInstruction,
  AccountMeta,
  SystemProgram,
} from '@solana/web3.js';
import { TOKEN_PROGRAM_ID, getAssociatedTokenAddress } from '@solana/spl-token';
import { Buffer } from 'buffer';
import * as borsh from '@project-serum/borsh'; // For struct packing or manual Buffer manipulation

import { TradingBase, TokenInfo, TradeResult, TradingConfig } from './baseTrader';
import { SolanaClient } from '../core/client';
import { Wallet } from '../core/wallet';
import { BondingCurveManager } from '../core/curve';
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

// Discriminator for the sell instruction from Python: 12502976635542562355
// Hex: 33a93264836ff2ad (little-endian)
const SELL_DISCRIMINATOR_STR = "ad2ff63846232a93"; // 12502976635542562355 as little-endian hex string
const SELL_DISCRIMINATOR = Buffer.from(SELL_DISCRIMINATOR_STR, "hex");


// Define a more specific config type if possible, extending TradingConfig
export interface SellerConfig extends TradingConfig {
  slippageBps?: number; // Slippage tolerance in basis points (e.g., 2500 for 25%)
  maxRetries?: number;
  priorityFeeManager: PriorityFeeManager; // Make it mandatory for seller
  bondingCurveManager: BondingCurveManager; // Make it mandatory for seller
}

export class TokenSeller extends TradingBase {
  private bondingCurveManager: BondingCurveManager;
  private priorityFeeManager: PriorityFeeManager;
  private slippageBps: number; // Basis points, e.g., 2500 = 25%
  private maxRetries: number;

  constructor(
    solanaClient: SolanaClient,
    wallet: Wallet,
    config: SellerConfig, // Use the more specific SellerConfig
  ) {
    super(solanaClient, wallet, config); // Pass general config up
    
    this.bondingCurveManager = config.bondingCurveManager;
    this.priorityFeeManager = config.priorityFeeManager;
    this.slippageBps = config.slippageBps ?? 2500; // Default 25% slippage (2500 bps) as per Python
    this.maxRetries = config.maxRetries ?? 5;
  }

  /**
   * Executes the sell operation for a given token.
   * @param tokenInfo Information about the token to sell.
   * @returns A TradeResult object indicating the outcome of the sell operation.
   */
  public async execute(tokenInfo: TokenInfo): Promise<TradeResult> {
    this.logger.info(`Attempting to sell token: ${tokenInfo.name} (${tokenInfo.symbol})`);
    try {
      const userAssociatedTokenAccount = await getAssociatedTokenAddress(
        tokenInfo.mint,
        this.wallet.pubkey // Owner of the ATA
      );

      const balanceResponse = await this.solanaClient.getTokenAccountBalance(userAssociatedTokenAccount);
      const tokenBalanceRaw = BigInt(balanceResponse?.amount || '0');

      if (tokenBalanceRaw === 0n) {
        this.logger.info("No tokens to sell.");
        return { success: false, errorMessage: "No tokens to sell" };
      }
      const tokenBalanceDecimal = Number(tokenBalanceRaw) / Math.pow(10, tokenDecimals);
      this.logger.info(`Token balance for ${tokenInfo.symbol}: ${tokenBalanceDecimal}`);

      const curveState = await this.bondingCurveManager.getCurveState(tokenInfo.bondingCurve);
      const tokenPriceSol = curveState.calculatePrice();
      this.logger.info(`Current price per token: ${tokenPriceSol.toFixed(8)} SOL`);

      const expectedSolOutput = tokenBalanceDecimal * tokenPriceSol;
      // slippageBps (e.g., 2500 for 25%) means min_sol_output = expected_sol_output * (1 - 2500/10000)
      const minSolOutputLamports = Math.floor(
        expectedSolOutput * (1 - this.slippageBps / 10000) * lamportsPerSol
      );

      this.logger.info(`Selling ${tokenBalanceDecimal} tokens of ${tokenInfo.symbol}.`);
      this.logger.info(`Expected SOL output: ${expectedSolOutput.toFixed(8)} SOL.`);
      this.logger.info(`Minimum SOL output (with ${this.slippageBps/100}% slippage): ${(minSolOutputLamports / lamportsPerSol).toFixed(8)} SOL`);

      const txSignature = await this.sendSellTransaction(
        tokenInfo,
        userAssociatedTokenAccount,
        tokenBalanceRaw, // Send raw amount
        minSolOutputLamports
      );

      this.logger.info(`Sell transaction sent: ${txSignature}. Confirming...`);
      
      const { blockhash, lastValidBlockHeight } = await this.solanaClient.getLatestBlockhashInfo();
      const confirmation = await this.solanaClient.confirmTransaction(txSignature, 'confirmed', blockhash, lastValidBlockHeight);

      if (confirmation && !confirmation.value.err) {
        this.logger.info(`Sell transaction confirmed: ${txSignature}`);
        return {
          success: true,
          txSignature: txSignature,
          amount: tokenBalanceDecimal, // Amount of tokens sold
          price: tokenPriceSol,       // Effective price per token in SOL at time of calculation
        };
      } else {
        this.logger.error(`Sell transaction failed to confirm or confirmed with error: ${txSignature}`, confirmation?.value.err);
        return {
          success: false,
          txSignature: txSignature,
          errorMessage: `Transaction failed to confirm or confirmed with error: ${JSON.stringify(confirmation?.value.err)}`,
        };
      }
    } catch (e: any) {
      this.logger.error(`Sell operation for ${tokenInfo.name} failed: ${e.message}`, e.stack);
      return { success: false, errorMessage: e.message };
    }
  }

  private async sendSellTransaction(
    tokenInfo: TokenInfo,
    userAssociatedTokenAccount: PublicKey,
    tokenAmountRaw: bigint, // Amount of tokens to sell in raw units (BigInt)
    minSolOutputLamports: number // Minimum SOL lamports to receive
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
      { pubkey: tokenInfo.creatorVault, isSigner: false, isWritable: true }, // creator_vault (differs from buy account order)
      { pubkey: TOKEN_PROGRAM_ID, isSigner: false, isWritable: false }, // Moved from index 9 to 8 in python, now 9
      { pubkey: pumpFunEventAuthority, isSigner: false, isWritable: false }, // event_authority
      { pubkey: pumpFunProgramId, isSigner: false, isWritable: false }, // pump_program (itself)
    ];

    // Prepare sell instruction data
    // struct.pack("<Q", token_amount) + struct.pack("<Q", min_sol_output)
    const minSolOutputLamportsBigInt = BigInt(minSolOutputLamports);

    const dataBuffer = Buffer.alloc(16); // 8 bytes for token_amount, 8 bytes for min_sol_output
    dataBuffer.writeBigUInt64LE(tokenAmountRaw, 0);
    dataBuffer.writeBigUInt64LE(minSolOutputLamportsBigInt, 8);
    
    const sellInstructionData = Buffer.concat([SELL_DISCRIMINATOR, dataBuffer]);

    const sellInstruction = new TransactionInstruction({
      keys: accounts,
      programId: pumpFunProgramId,
      data: sellInstructionData,
    });
    
    const relevantAccountsForFee = this.getRelevantAccounts(tokenInfo); // From TradingBase
    const priorityFee = await this.priorityFeeManager.calculatePriorityFee(relevantAccountsForFee);

    try {
      // Sell transaction usually does not need ATA creation instruction
      return await this.solanaClient.buildAndSendTransaction(
        [sellInstruction], // Only the sell instruction
        this.wallet.keypair,
        true, // skipPreflight
        this.maxRetries,
        priorityFee // Optional priority fee in microLamports
      );
    } catch (e: any) {
      this.logger.error(`_sendSellTransaction failed: ${e.message}`, e.stack);
      throw e; // Re-throw to be caught by execute method
    }
  }
}
