For the full walkthrough, see [Solana: Creating a trading and sniping pump.fun bot](https://docs.chainstack.com/docs/solana-creating-a-pumpfun-bot).

For near-instantaneous transaction propagation, you can use the [Chainstack Solana Trader nodes](https://docs.chainstack.com/docs/trader-nodes).

[Sign up with Chainstack](https://console.chainstack.com).

Make sure you have the required packages installed `pip install -r requirements.txt`.

Make sure you have your endpoints set up in `config.py`.

Quick note on a couple of new scripts in `/learning-examples`:

## Bonding curve state check

`check_boding_curve_status.py` — checks the state of the bonding curve associated with a token. When the bonding curve state is completed, the token is migrated to Raydium.

To run:

`python check_boding_curve_status.py TOKEN_ADDRESS`

## Listening to the Raydium migration

When the bonding curve state completes, the liquidity and the token graduate to Raydium.

`listen_to_raydium_migration.py` — listens to the migration events of the tokens from pump_fun to Raydium and prints the signature of the migration, the token address, and the liquidity pool address on Raydium.

Note that it's using the [blockSubscribe]([url](https://docs.chainstack.com/reference/blocksubscribe-solana)) method that not all providers support, but Chainstack does and I (although obviously biased) found it pretty reliable.

To run:

`python listen_to_raydium_migration.py`
