### File: app/config.py

# HORIZON_URL = "https://api.mainnet.minepi.com"
# NETWORK_PASSPHRASE = "Pi Network"
# COIN_DERIVATION_PATH = "m/44'/314159'/0'"
# MINIMUM_BALANCE = 0.3 
# FEE_PERCENT = 0.02


# app/config.py

HORIZON_URL = "https://api.mainnet.minepi.com"
NETWORK_PASSPHRASE = "Pi Network"
COIN_DERIVATION_PATH = "m/44'/314159'/0'"
MINIMUM_BALANCE = 0.3      # Keep at least this balance in wallets
FEE_PERCENT = 0.02         # take 2% fee (optional)
BATCH_SIZE = 20            # default batch size for parallel processing
TRANSACTION_DELAY_SECONDS = 0.1  # small pause between batches (seconds)

