import { PublicKey } from '@solana/web3.js';

export const lamportsPerSol: number = 1_000_000_000;
export const tokenDecimals: number = 6;

export const systemProgramId: PublicKey = new PublicKey("11111111111111111111111111111111");
export const tokenProgramId: PublicKey = new PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA");
export const associatedTokenProgramId: PublicKey = new PublicKey("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL");
export const rentSysvarId: PublicKey = new PublicKey("SysvarRent111111111111111111111111111111111");
export const solMintId: PublicKey = new PublicKey("So11111111111111111111111111111111111111112");

export const pumpFunProgramId: PublicKey = new PublicKey("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P");
export const pumpFunGlobal: PublicKey = new PublicKey("4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf");
export const pumpFunEventAuthority: PublicKey = new PublicKey("Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1");
export const pumpFunFeeRecipient: PublicKey = new PublicKey("CebN5WGQ4jvEPvsVU4EoHEpgzq1VV7AbicfhtW4xC9iM");
// LIQUIDITY_MIGRATOR is not a valid PublicKey, so it's kept as a string.
export const pumpFunLiquidityMigrator: string = "39azUYFWPz3VHgKCf3VChUwbpURdCHRxjWVowf5jUJjg";
