import { PublicKey } from '@solana/web3.js';
import { SolanaClient } from './client'; // Assuming SolanaClient is in client.ts
import { lamportsPerSol, tokenDecimals } from './pubkeys'; // Assuming these are in pubkeys.ts
import { struct, u64, bool, publicKey as borshPublicKey } from "@project-serum/borsh";
import { Buffer } from 'buffer';

// Discriminator for the bonding curve account
const EXPECTED_DISCRIMINATOR = Buffer.from("97807dd31702d517", "hex"); // 6966180631402821399 in little-endian hex

interface BondingCurveStateData {
  virtualTokenReserves: bigint;
  virtualSolReserves: bigint;
  realTokenReserves: bigint;
  realSolReserves: bigint;
  tokenTotalSupply: bigint;
  complete: boolean;
  creator: PublicKey;
}

const bondingCurveStateLayout = struct([
  u64('virtualTokenReserves'),
  u64('virtualSolReserves'),
  u64('realTokenReserves'),
  u64('realSolReserves'),
  u64('tokenTotalSupply'),
  bool('complete'),
  borshPublicKey('creator'),
]);

export class BondingCurveState implements BondingCurveStateData {
  public virtualTokenReserves: bigint;
  public virtualSolReserves: bigint;
  public realTokenReserves: bigint;
  public realSolReserves: bigint;
  public tokenTotalSupply: bigint;
  public complete: boolean;
  public creator: PublicKey;

  constructor(data: Buffer) {
    if (data.subarray(0, 8).compare(EXPECTED_DISCRIMINATOR) !== 0) {
      throw new Error("Invalid curve state discriminator");
    }

    const parsed = bondingCurveStateLayout.decode(data.subarray(8));
    this.virtualTokenReserves = BigInt(parsed.virtualTokenReserves.toString());
    this.virtualSolReserves = BigInt(parsed.virtualSolReserves.toString());
    this.realTokenReserves = BigInt(parsed.realTokenReserves.toString());
    this.realSolReserves = BigInt(parsed.realSolReserves.toString());
    this.tokenTotalSupply = BigInt(parsed.tokenTotalSupply.toString());
    this.complete = parsed.complete;
    this.creator = parsed.creator;
  }

  public calculatePrice(): number {
    // TODO: Consider using a Decimal library for precision if needed
    if (this.virtualTokenReserves <= 0n || this.virtualSolReserves <= 0n) {
      throw new Error("Invalid reserve state");
    }
    const virtualSolReservesNum = Number(this.virtualSolReserves) / lamportsPerSol;
    const virtualTokenReservesNum = Number(this.virtualTokenReserves) / Math.pow(10, tokenDecimals);
    return virtualSolReservesNum / virtualTokenReservesNum;
  }

  public get tokenReserves(): number {
    // TODO: Consider using a Decimal library for precision if needed
    return Number(this.virtualTokenReserves) / Math.pow(10, tokenDecimals);
  }

  public get solReserves(): number {
    // TODO: Consider using a Decimal library for precision if needed
    return Number(this.virtualSolReserves) / lamportsPerSol;
  }
}

export class BondingCurveManager {
  private client: SolanaClient;

  constructor(client: SolanaClient) {
    this.client = client;
  }

  public async getCurveState(curveAddress: PublicKey): Promise<BondingCurveState> {
    try {
      const accountInfo = await this.client.getAccountInfo(curveAddress);
      if (!accountInfo || !accountInfo.data) {
        throw new Error(`No data in bonding curve account ${curveAddress}`);
      }
      return new BondingCurveState(accountInfo.data);
    } catch (e: any) {
      console.error(`Failed to get curve state: ${e.message}`);
      throw new Error(`Invalid curve state: ${e.message}`);
    }
  }

  public async calculatePrice(curveAddress: PublicKey): Promise<number> {
    const curveState = await this.getCurveState(curveAddress);
    return curveState.calculatePrice();
  }

  public async calculateExpectedTokens(curveAddress: PublicKey, solAmount: number): Promise<number> {
    // TODO: Consider using a Decimal library for precision if needed
    const curveState = await this.getCurveState(curveAddress);
    const price = curveState.calculatePrice();
    if (price === 0) {
        throw new Error("Cannot calculate expected tokens with zero price");
    }
    return solAmount / price;
  }
}
