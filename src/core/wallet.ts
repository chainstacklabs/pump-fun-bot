import { Keypair, PublicKey } from '@solana/web3.js';
import { getAssociatedTokenAddress } from '@solana/spl-token';
import * as base58 from 'bs58';

export class Wallet {
  private _privateKey: string;
  private _keypair: Keypair;

  constructor(privateKey: string) {
    this._privateKey = privateKey;
    this._keypair = this.loadKeypair(privateKey);
  }

  public get pubkey(): PublicKey {
    return this._keypair.publicKey;
  }

  public get keypair(): Keypair {
    return this._keypair;
  }

  public async getAssociatedTokenAddress(mint: PublicKey): Promise<PublicKey> {
    return getAssociatedTokenAddress(mint, this.pubkey);
  }

  private loadKeypair(privateKey: string): Keypair {
    const privateKeyBytes = base58.decode(privateKey);
    return Keypair.fromSecretKey(privateKeyBytes);
  }
}
