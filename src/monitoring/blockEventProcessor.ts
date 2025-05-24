import { PublicKey, VersionedTransaction, TransactionInstruction, ParsedInstruction, MessageAccountKeys } from '@solana/web3.js';
import * as base58 from 'bs58';
import { Buffer } from 'buffer';
import * as fs from 'fs'; // For loading IDL, consider alternative for browser environments
import * as path from 'path'; // For constructing path to IDL
import { pumpFunProgramId } from '../core/pubkeys'; // Assuming pumpFunProgramId is the main program ID

// Placeholder for TokenInfo until it's defined - based on Python code
export interface TokenInfo {
  name: string;
  symbol: string;
  uri: string;
  mint: PublicKey;
  bondingCurve: PublicKey;
  associatedBondingCurve: PublicKey; // This might be the same as bondingCurve if it's the ATA
  user: PublicKey; // The account that initiated the create, likely the fee payer
  creator: PublicKey;
  creatorVault: PublicKey; // PDA for the creator's vault
}

// Simplified IDL structure based on the Python code's fallback
interface InstructionArgDef {
  name: string;
  type: 'string' | 'pubkey' | string; // Allow other types but handle only known
}
interface InstructionDef {
  name: string;
  args: InstructionArgDef[];
}
interface MinimalIdl {
  instructions: InstructionDef[];
}

const logger = {
  info: (...args: any[]) => console.log('[BlockEventProcessor]', ...args),
  warn: (...args: any[]) => console.warn('[BlockEventProcessor]', ...args),
  error: (...args: any[]) => console.error('[BlockEventProcessor]', ...args),
};

export class PumpEventProcessor {
  private pumpProgramId: PublicKey;
  private idl: MinimalIdl;
  private static readonly CREATE_DISCRIMINATOR_STR = "5c721ade8f0ed498"; // 8576854823835016728 as little-endian hex string
  private static readonly CREATE_DISCRIMINATOR = Buffer.from(PumpEventProcessor.CREATE_DISCRIMINATOR_STR, "hex");


  constructor(pumpProgramIdToUse: PublicKey = pumpFunProgramId) {
    this.pumpProgramId = pumpProgramIdToUse;
    this.idl = this.loadIdl();
  }

  private loadIdl(): MinimalIdl {
    try {
      // Assuming IDL is in <project_root>/idl/pump_fun_idl.json
      // Adjust path as necessary based on your project structure
      const idlPath = path.join(__dirname, '..', '..', 'idl', 'pump_fun_idl.json');
      const idlJson = fs.readFileSync(idlPath, 'utf-8');
      return JSON.parse(idlJson) as MinimalIdl;
    } catch (e: any) {
      logger.error(`Failed to load IDL: ${e.message}. Using minimal fallback.`);
      return {
        instructions: [
          {
            name: "create",
            args: [
              { name: "name", type: "string" },
              { name: "symbol", type: "string" },
              { name: "uri", type: "string" },
            ],
          },
        ],
      };
    }
  }

  public processTransaction(txData: string): TokenInfo | null {
    try {
      const txDataDecoded = Buffer.from(txData, 'base64');
      const transaction = VersionedTransaction.deserialize(txDataDecoded);
      const message = transaction.message;

      for (const ix of message.compiledInstructions) {
        const programIdIndex = ix.programIdIndex;
        if (programIdIndex >= message.staticAccountKeys.length) {
          logger.warn(`Program ID index ${programIdIndex} out of bounds for static account keys.`);
          continue;
        }
        const programId = message.staticAccountKeys[programIdIndex];

        if (!programId.equals(this.pumpProgramId)) {
          continue;
        }

        const ixDataBuffer = Buffer.from(ix.data);

        if (ixDataBuffer.length < 8) {
          continue;
        }
        
        const discriminator = ixDataBuffer.subarray(0, 8);
        if (!discriminator.equals(PumpEventProcessor.CREATE_DISCRIMINATOR)) {
          continue;
        }

        logger.info("Found create instruction for pump.fun program.");

        const createIxDef = this.idl.instructions.find(instr => instr.name === "create");
        if (!createIxDef) {
          logger.warn("Create instruction definition not found in IDL.");
          continue;
        }

        // Reconstruct account list for this instruction based on ix.accounts (indices)
        const instructionAccounts = ix.accountKeyIndexes.map(index => message.staticAccountKeys[index]);

        const decodedArgs = this.decodeCreateInstruction(ixDataBuffer, createIxDef, instructionAccounts);
        if (!decodedArgs) {
            logger.warn("Failed to decode create instruction arguments.");
            continue;
        }
        
        const creator = new PublicKey(decodedArgs.user); // In this context, user is likely the creator paying fees
        const creatorVault = this.findCreatorVault(creator);

        return {
          name: decodedArgs.name as string,
          symbol: decodedArgs.symbol as string,
          uri: decodedArgs.uri as string,
          mint: new PublicKey(decodedArgs.mint),
          bondingCurve: new PublicKey(decodedArgs.bondingCurve),
          associatedBondingCurve: new PublicKey(decodedArgs.associatedBondingCurve), // Often same as bondingCurve
          user: new PublicKey(decodedArgs.user), // The account that executed the ix, typically the fee payer / creator
          creator: creator, // Explicitly set creator
          creatorVault: creatorVault,
        };
      }
    } catch (e: any) {
      logger.error(`Error processing transaction: ${e.message}`, e.stack);
    }
    return null;
  }

  // TODO: Implement proper borsh deserialization if a schema is available.
  // This manual decoding is brittle and based on the Python code's assumptions.
  private decodeCreateInstruction(
    ixData: Buffer,
    ixDef: InstructionDef,
    accounts: PublicKey[]
  ): { [key: string]: string | PublicKey } | null {
    const args: { [key: string]: string | PublicKey } = {};
    let offset = 8; // Skip 8-byte discriminator

    for (const argDef of ixDef.args) {
      try {
        if (argDef.type === "string") {
          if (offset + 4 > ixData.length) {
            logger.error(`Not enough data for string length: offset ${offset}, data length ${ixData.length}`);
            return null;
          }
          const length = ixData.readUInt32LE(offset);
          offset += 4;
          if (offset + length > ixData.length) {
             logger.error(`Not enough data for string content: offset ${offset}, length ${length}, data length ${ixData.length}`);
            return null;
          }
          args[argDef.name] = ixData.subarray(offset, offset + length).toString('utf-8');
          offset += length;
        } else if (argDef.type === "pubkey") {
          // Pubkeys are not typically part of ix data like this unless serialized directly
          // The Python code implies they might be, or it's a misunderstanding of typical Solana ix structure
          // For now, assuming this case is not hit often or is handled by accounts mapping
          logger.warn(`Pubkey type in instruction args is unusual for direct data decoding: ${argDef.name}. This field might be from accounts array.`);
           if (offset + 32 > ixData.length) {
            logger.error(`Not enough data for pubkey: offset ${offset}, data length ${ixData.length}`);
            return null;
          }
          args[argDef.name] = new PublicKey(ixData.subarray(offset, offset + 32));
          offset += 32;
        } else {
          logger.warn(`Unsupported argument type in IDL for direct decoding: ${argDef.type} for arg ${argDef.name}`);
          // Cannot proceed if unknown type as offset would be wrong
          return null;
        }
      } catch (e:any) {
        logger.error(`Error decoding argument ${argDef.name} of type ${argDef.type}: ${e.message}`);
        return null;
      }
    }

    // Map accounts based on typical pump.fun create instruction structure
    // These indices are standard for pump.fun 'create'
    // (derived from observing transactions and common IDLs)
    if (accounts.length < 8) {
        logger.error(`Not enough accounts provided for create instruction. Expected at least 8, got ${accounts.length}`);
        return null;
    }
    args["mint"] = accounts[0];                     // Mint account being created
    // args["mintAuthority"] = accounts[1];          // Usually PDA or signer
    args["bondingCurve"] = accounts[2];            // Bonding curve account
    args["associatedBondingCurve"] = accounts[3]; // Associated token account for the bonding curve (often same as curve address itself if it holds tokens)
    // args["tokenProgram"] = accounts[4];          // Token program
    // args["systemProgram"] = accounts[5];         // System program
    // args["rent"] = accounts[6];                  // Rent sysvar
    args["user"] = accounts[7];                    // User/creator/feePayer

    // Ensure all required args from IDL (name, symbol, uri) are present
    if (!args.name || !args.symbol || !args.uri) {
        logger.error("Missing one or more required string arguments (name, symbol, uri) after decoding.");
        return null;
    }

    return args;
  }

  public findCreatorVault(creator: PublicKey): PublicKey {
    const [derivedAddress] = PublicKey.findProgramAddressSync(
      [Buffer.from("creator-vault"), creator.toBuffer()],
      this.pumpProgramId // Use the stored pump program ID
    );
    return derivedAddress;
  }
}
