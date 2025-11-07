# ### File: app/pi_worker.py



# app/pi_worker.py

import asyncio
import time
from typing import List, Dict, Any
from stellar_sdk import Server, TransactionBuilder, Asset
from app.utils import derive_keypair
from app.config import HORIZON_URL, NETWORK_PASSPHRASE

# Horizon server for Pi (from config)
server = Server(HORIZON_URL)


async def send_payment(seed: str, destination: str, amount: float) -> Dict[str, Any]:
    """
    Derive keypair from mnemonic seed and submit a payment transaction.
    Uses asyncio.to_thread for blocking SDK calls.
    Returns a dict describing success or error.
    """
    try:
        kp = derive_keypair(seed)

        # load account (blocking SDK call) in a thread
        source_account = await asyncio.to_thread(server.load_account, kp.public_key)

        # fetch base fee (blocking)
        base_fee = await asyncio.to_thread(server.fetch_base_fee)

        # Build transaction (use Asset.native() for native Pi)
        tx_builder = TransactionBuilder(
            source_account=source_account,
            network_passphrase=NETWORK_PASSPHRASE,
            base_fee=base_fee,
        ).append_payment_op(
            destination=destination,
            asset=Asset.native(),
            amount=str(amount),
        ).set_timeout(30)

        tx = tx_builder.build()
        tx.sign(kp)

        # submit transaction (blocking)
        response = await asyncio.to_thread(server.submit_transaction, tx)

        return {
            "seed": seed,
            "status": "success",
            "tx_hash": response.get("hash"),
        }
    except Exception as e:
        return {"seed": seed, "status": "error", "error": str(e)}


# -------------------------
# One-off batch (used by /api/transfer)
# -------------------------
async def process_all_seeds(seeds: List[str], destination: str, amount: float) -> List[Dict[str, Any]]:
    """
    Perform a single batch of transactions (one per seed).
    Returns a list of dicts (each success/error normalized).
    """
    tasks = [send_payment(seed, destination, amount) for seed in seeds]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Normalize: convert exceptions into dicts so return type is List[Dict]
    normalized: List[Dict[str, Any]] = []
    for idx, r in enumerate(raw_results):
        if isinstance(r, BaseException):
            normalized.append(
                {"seed": seeds[idx] if idx < len(seeds) else None, "status": "error", "error": str(r)}
            )
        else:
            normalized.append(r)
    return normalized


# -------------------------
# Continuous loops (used by /start and /start_turbo)
# -------------------------
async def loop_process_forever(seeds: List[str], destination: str, amount: float, stop_event: asyncio.Event):
    """
    Run transactions continuously (1 batch per second) until stop_event is set.
    Each batch sends one payment per seed.
    """
    round_no = 0
    while not stop_event.is_set():
        round_no += 1
        print(f"🔁 Normal round {round_no} — processing {len(seeds)} seeds")
        results = await process_all_seeds(seeds, destination, amount)
        # you can log results or persist them here
        errors = [r for r in results if r.get("status") == "error"]
        if errors:
            print(f"⚠️ Errors in batch: {errors}")
        await asyncio.sleep(0.5)  # 1-second interval between rounds
"""

Modified above

"""



async def loop_turbo_forever(seeds: List[str], destination: str, amount: float, stop_event: asyncio.Event):
    """
    Run turbo transfer rounds: up to 10 transactions per second total.
    If user supplies fewer than 10 seeds, it will send up to len(seeds) tx/sec.
    """
    round_no = 0
    while not stop_event.is_set():
        round_no += 1
        start = time.time()

        # choose up to 10 seeds for this turbo batch
        seeds_for_batch = seeds[:10] if len(seeds) >= 10 else seeds

        tasks = [send_payment(seed, destination, amount) for seed in seeds_for_batch]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        # normalize as in process_all_seeds
        normalized: List[Dict[str, Any]] = []
        for idx, r in enumerate(raw_results):
            if isinstance(r, BaseException):
                normalized.append(
                    {"seed": seeds_for_batch[idx] if idx < len(seeds_for_batch) else None, "status": "error", "error": str(r)}
                )
            else:
                normalized.append(r)

        duration = time.time() - start
        print(f"⚡ Turbo round {round_no}: {len(normalized)} tx in {duration:.3f}s")
        errors = [r for r in normalized if r.get("status") == "error"]
        if errors:
            print(f"⚠️ Turbo errors: {errors}")

        # maintain roughly 1 second per turbo round (=> up to ~10 tx/sec)
        if duration < 1:
            await asyncio.sleep(1 - duration)



async def process_all_seeds_turbo(seeds: List[str], destination: str, amount: float) -> List[Dict[str, Any]]:
    """
    Perform a single turbo batch (up to 10 transactions in one second).
    """
    seeds_for_batch = seeds[:10] if len(seeds) >= 10 else seeds
    tasks = [send_payment(seed, destination, amount) for seed in seeds_for_batch]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    normalized: List[Dict[str, Any]] = []
    for idx, r in enumerate(raw_results):
        if isinstance(r, BaseException):
            normalized.append(
                {"seed": seeds_for_batch[idx] if idx < len(seeds_for_batch) else None, "status": "error", "error": str(r)}
            )
        else:
            normalized.append(r)
    return normalized


# # app/pi_worker.py

# import asyncio
# import time
# from typing import List, Tuple
# from stellar_sdk import Server, TransactionBuilder, Asset
# from stellar_sdk.exceptions import NotFoundError
# import httpx

# from .config import HORIZON_URL, NETWORK_PASSPHRASE, MINIMUM_BALANCE, FEE_PERCENT, BATCH_SIZE, TRANSACTION_DELAY_SECONDS
# from .utils import derive_keypair

# server = Server(HORIZON_URL)


# async def _call_in_thread(func, *args, **kwargs):
#     """Helper to run blocking calls in threadpool."""
#     return await asyncio.to_thread(func, *args, **kwargs)


# async def _get_native_balance(public_key: str) -> float:
#     """Return native (PI) balance for an account, or 0.0 if not found."""
#     try:
#         resp = await _call_in_thread(server.accounts().account_id(public_key).call)
#         native = next((b["balance"] for b in resp["balances"] if b["asset_type"] == "native"), "0")
#         return float(native)
#     except NotFoundError:
#         return 0.0
#     except Exception:
#         return 0.0


# async def fetch_account_and_fee(kp):
#     """
#     Load account object and base_fee (both blocking SDK calls).
#     kp is stellar Keypair-like (has public_key)
#     """
#     account = await asyncio.to_thread(server.load_account, kp.public_key)
#     base_fee = await asyncio.to_thread(server.fetch_base_fee)
#     return account, base_fee


# async def create_signed_transaction(seed_or_mnemonic: str, destination: str, amount: float) -> Tuple[str, str, str]:
#     """
#     Build and sign a transaction. Returns (pubkey, xdr, error_str).
#     If error_str is None then xdr is valid.
#     """
#     try:
#         kp = derive_keypair(seed_or_mnemonic)
#     except Exception as e:
#         return (str(seed_or_mnemonic)[:12], None, f"Invalid mnemonic: {e}")

#     pubkey = kp.public_key

#     # Check balance
#     try:
#         native_balance = await _get_native_balance(pubkey)
#     except Exception as e:
#         return (pubkey, None, f"Error fetching balance: {e}")

#     # Minimal fee & reserve check
#     estimated_fee = 0.00001
#     if native_balance < amount + estimated_fee + MINIMUM_BALANCE:
#         return (pubkey, None, f"Insufficient balance ({native_balance})")

#     # compute send amount after fee percent
#     fee_amount = amount * FEE_PERCENT
#     send_amount = round(amount - fee_amount, 7)

#     # build transaction
#     try:
#         account, base_fee = await fetch_account_and_fee(kp)
#         tx = (
#             TransactionBuilder(account, network_passphrase=NETWORK_PASSPHRASE, base_fee=base_fee)
#             .add_text_memo("PI Transfer")
#             .append_payment_op(destination=destination, amount=str(send_amount), asset=Asset.native())
#             .set_timeout(30)
#             .build()
#         )
#         tx.sign(kp)
#         xdr = tx.to_xdr()
#         return (pubkey, xdr, None)
#     except Exception as e:
#         return (pubkey, None, f"Build/sign error: {e}")


# async def submit_transaction(xdr: str) -> str:
#     """
#     Submit XDR to Horizon using httpx (works well in async).
#     Returns a short status string.
#     """
#     async with httpx.AsyncClient(timeout=15.0) as client:
#         try:
#             resp = await client.post(f"{HORIZON_URL}/transactions", data={"tx": xdr})
#             data = resp.json()
#             if resp.status_code == 200 and "hash" in data:
#                 return f"Success: {data['hash']}"
#             else:
#                 err = data.get("extras", {}).get("result_codes", {})
#                 return f"Failed: {err}"
#         except Exception as e:
#             return f"HTTP Error: {e}"


# async def process_batch(seeds: List[str], destination: str, amount: float) -> List[str]:
#     """
#     Create & sign transactions for a batch, then submit them in parallel.
#     Returns list of result strings.
#     """
#     # signers
#     sign_tasks = [create_signed_transaction(s, destination, amount) for s in seeds]
#     signed = await asyncio.gather(*sign_tasks, return_exceptions=False)

#     # prepare submit tasks for only valid XDRs
#     submit_tasks = []
#     results = []
#     for pubkey, xdr, err in signed:
#         if err:
#             results.append(f"Error for {pubkey[:8]}...: {err}")
#             submit_tasks.append(asyncio.sleep(0, result=None))  # placeholder
#         else:
#             submit_tasks.append(submit_transaction(xdr))

#     submitted = await asyncio.gather(*submit_tasks, return_exceptions=True)

#     # combine
#     for (pubkey, xdr, err), sres in zip(signed, submitted):
#         if err:
#             # already appended error
#             continue
#         else:
#             if isinstance(sres, Exception):
#                 results.append(f"Error for {pubkey[:8]}...: submit exception {sres}")
#             else:
#                 results.append(f"Success for {pubkey[:8]}...: {sres}")
#     return results


# async def process_all_seeds(seeds: List[str], destination: str, amount: float) -> List[str]:
#     """
#     Default batch processing (parallel batches).
#     """
#     start = time.time()
#     results = []
#     batch_size = BATCH_SIZE

#     for i in range(0, len(seeds), batch_size):
#         batch = seeds[i : i + batch_size]
#         try:
#             batch_results = await process_batch(batch, destination, amount)
#             results.extend(batch_results)
#         except Exception as e:
#             results.append(f"Batch {i//batch_size + 1} failed: {e}")
#         await asyncio.sleep(TRANSACTION_DELAY_SECONDS)

#     total_time = time.time() - start
#     print(f"Processed {len(seeds)} transactions in {total_time:.3f}s")
#     return results


# # Continuous loop (existing)
# async def loop_process_forever(seeds: List[str], destination: str, amount: float, stop_event: asyncio.Event):
#     round_counter = 0
#     while not stop_event.is_set():
#         round_counter += 1
#         print(f"🔁 Loop round {round_counter} starting")
#         try:
#             await process_all_seeds(seeds, destination, amount)
#         except Exception as e:
#             print(f"[loop error] {e}")
#         await asyncio.sleep(1.5)


# # Turbo mode: aim for approx 10 tx/sec by running batches of BATCH_SIZE ~10 per second
# async def loop_turbo_forever(seeds: List[str], destination: str, amount: float, stop_event: asyncio.Event):
#     round_counter = 0
#     batch_size = BATCH_SIZE or 10
#     if batch_size <= 0:
#         batch_size = 10

#     while not stop_event.is_set():
#         round_counter += 1
#         print(f"🚀 Turbo round {round_counter} starting")
#         # We'll create tasks for the batches and run them concurrently
#         tasks = []
#         for i in range(0, len(seeds), batch_size):
#             batch = seeds[i : i + batch_size]
#             tasks.append(process_batch(batch, destination, amount))

#         try:
#             results = await asyncio.gather(*tasks, return_exceptions=True)
#             # print summary
#             total = sum(len(r) if isinstance(r, list) else 0 for r in results)
#             print(f"Turbo round {round_counter} completed: approx {total} results")
#         except Exception as e:
#             print(f"[turbo error] {e}")

#         # throttle to roughly 1 round/sec (i.e., ~10 tx/sec if batch_size == 10)
#         await asyncio.sleep(1.0)











# app/pi_worker.py
# app/pi_worker.py

# import asyncio
# import httpx
# import time
# from stellar_sdk import Server, TransactionBuilder, Asset, Keypair
# from stellar_sdk.exceptions import NotFoundError
# from .config import HORIZON_URL, NETWORK_PASSPHRASE, MINIMUM_BALANCE, FEE_PERCENT
# from .utils import derive_keypair

# server = Server(HORIZON_URL)

# # Adjustable delay in seconds between each batch (normal mode)
# TRANSACTION_DELAY_SECONDS = 0.1


# async def fetch_account_and_fee(kp: Keypair):
#     account = await asyncio.to_thread(server.load_account, kp.public_key)
#     base_fee = await asyncio.to_thread(server.fetch_base_fee)
#     return account, base_fee


# async def create_signed_transaction(seed: str, destination: str, amount: float):
#     kp = derive_keypair(seed)

#     try:
#         balance_resp = await asyncio.to_thread(
#             server.accounts().account_id(kp.public_key).call
#         )
#         native_balance = next(
#             (b["balance"] for b in balance_resp["balances"] if b["asset_type"] == "native"),
#             "0",
#         )
#         native_balance = float(native_balance)

#         estimated_fee = 0.00001
#         if native_balance < amount + estimated_fee + MINIMUM_BALANCE:
#             return kp.public_key, None, f"Insufficient balance ({native_balance})"
#     except NotFoundError:
#         return kp.public_key, None, "Account not found"
#     except Exception as e:
#         return kp.public_key, None, f"Error checking balance: {str(e)}"

#     fee_amount = amount * FEE_PERCENT
#     send_amount = round(amount - fee_amount, 7)

#     try:
#         account, base_fee = await fetch_account_and_fee(kp)
#         tx = (
#             TransactionBuilder(account, NETWORK_PASSPHRASE, base_fee)
#             .add_text_memo("PI Transfer")
#             .append_payment_op(destination=destination, asset=Asset.native(), amount=str(send_amount))
#             .set_timeout(30)
#             .build()
#         )
#         tx.sign(kp)
#         return kp.public_key, tx.to_xdr(), None
#     except Exception as e:
#         return kp.public_key, None, str(e)


# async def submit_transaction(xdr: str) -> str:
#     async with httpx.AsyncClient(timeout=10.0) as client:
#         try:
#             response = await client.post(HORIZON_URL + "/transactions", data={"tx": xdr})
#             data = response.json()
#             if response.status_code == 200 and "hash" in data:
#                 return f"Success: {data['hash']}"
#             elif response.status_code == 200:
#                 return f"Success: incomplete response {data}"
#             else:
#                 error_detail = data.get("extras", {}).get("result_codes", {})
#                 return f"Failed: {error_detail}"
#         except Exception as e:
#             return f"HTTP Error: {str(e)}"


# async def process_batch(seeds: list[str], destination: str, amount: float) -> list[str]:
#     signed_tasks = [create_signed_transaction(seed, destination, amount) for seed in seeds]
#     signed_results = await asyncio.gather(*signed_tasks)

#     submit_tasks = [
#         submit_transaction(xdr) if xdr else asyncio.sleep(0)
#         for _, xdr, _ in signed_results
#     ]
#     submit_results = await asyncio.gather(*submit_tasks)

#     final_results = []
#     for (pubkey, xdr, err), submission in zip(signed_results, submit_results):
#         if err:
#             final_results.append(f"Error for {pubkey[:5]}...: {err}")
#         else:
#             final_results.append(f"Success for {pubkey[:5]}...: {submission}")
#     return final_results


# async def process_all_seeds(seeds: list[str], destination: str, amount: float) -> list[str]:
#     start = time.time()
#     results = []

#     batch_size = 12
#     for i in range(0, len(seeds), batch_size):
#         batch = seeds[i : i + batch_size]
#         try:
#             batch_result = await process_batch(batch, destination, amount)
#         except Exception as e:
#             batch_result = [f"Batch {i // batch_size + 1} failed: {str(e)}"]
#         results.extend(batch_result)
#         await asyncio.sleep(TRANSACTION_DELAY_SECONDS)

#     end = time.time()
#     print(f"Processed {len(seeds)} transactions in {round(end - start, 3)}s")
#     return results


# # ✅ Normal continuous loop
# async def loop_process_forever(seeds, destination, amount, stop_event: asyncio.Event):
#     round_counter = 0
#     while not stop_event.is_set():
#         round_counter += 1
#         print(f"🔁 Starting round {round_counter} of transfers")
#         try:
#             await process_all_seeds(seeds, destination, amount)
#         except Exception as e:
#             print(f"[Loop Error] Round {round_counter} failed: {str(e)}")
#         await asyncio.sleep(1.5)


# # ✅ Turbo loop for 10 TPS
# async def loop_process_turbo(seeds, destination, amount, stop_event: asyncio.Event):
#     """
#     Push transactions in parallel aiming for ~10 per second.
#     """
#     round_counter = 0
#     batch_size = 10  # 10 seeds per batch

#     while not stop_event.is_set():
#         round_counter += 1
#         print(f"🚀 Turbo round {round_counter} (10 TPS)")

#         tasks = []
#         for i in range(0, len(seeds), batch_size):
#             batch = seeds[i : i + batch_size]
#             tasks.append(process_batch(batch, destination, amount))

#         try:
#             all_results = await asyncio.gather(*tasks, return_exceptions=True)
#             for r in all_results:
#                 if isinstance(r, Exception):
#                     print(f"⚠️ Turbo batch error: {r}")
#                 else:
#                     print(f"Batch completed: {len(r)} results")
#         except Exception as e:
#             print(f"[Turbo Error] Round {round_counter}: {str(e)}")

#         # Short delay to aim ~10 TPS
#         await asyncio.sleep(1.0)
        

# # ✅ Continuous turbo loop for /start_turbo
#     async def loop_turbo_forever(seeds, destination, amount, stop_event: asyncio.Event):
#         round_counter = 0
#         while not stop_event.is_set():
#             round_counter += 1
#             print(f"⚡ Turbo round {round_counter} starting...")
#             try:
#                 await process_batch_turbo(seeds, destination, amount, batch_size=10)
#             except Exception as e:
#                 print(f"[Turbo Error] Round {round_counter} failed: {str(e)}")
#             await asyncio.sleep(0.2)  # small delay between turbo rounds






# # ### File: app/pi_worker.py




# # app/pi_worker.py

# import asyncio
# from typing import List, Dict, Any, Union
# from stellar_sdk import Server, TransactionBuilder, Network, Keypair
# from app.utils import derive_keypair

# # 🔥 Pi Network Horizon endpoint + network passphrase
# HORIZON_URL = "https://api.mainnet.minepi.com"
# NETWORK_PASSPHRASE = "Pi Network"
# server = Server(HORIZON_URL)


# async def send_transaction(seed_or_mnemonic: str, owner: str, amount: float) -> Dict[str, Any]:
#     """
#     Build, sign, and submit one transaction from a seed or mnemonic.
#     """
#     try:
#         # 🔑 Handle mnemonic vs secret seed
#         if len(seed_or_mnemonic.split()) > 10:  # heuristic: it's a mnemonic phrase
#             kp = derive_keypair(seed_or_mnemonic)
#         else:
#             kp = Keypair.from_secret(seed_or_mnemonic)

#         # Load account (stellar_sdk is sync, so wrap in thread)
#         account = await asyncio.to_thread(server.load_account, kp.public_key)

#         # Build transaction
#         tx = (
#             TransactionBuilder(
#                 source_account=account,
#                 network_passphrase=NETWORK_PASSPHRASE,
#                 base_fee=100,
#             )
#             .append_payment_op(destination=owner, amount=str(amount), asset_code="PI")
#             .set_timeout(30)
#             .build()
#         )

#         # Sign & submit (also sync → wrap in thread)
#         tx.sign(kp)
#         response = await asyncio.to_thread(server.submit_transaction, tx)

#         return {
#             "seed": seed_or_mnemonic[:6] + "...",
#             "status": "success",
#             "hash": response.get("hash"),
#         }

#     except Exception as e:
#         return {
#             "seed": seed_or_mnemonic[:6] + "...",
#             "status": "error",
#             "error": str(e),
#         }


# async def process_all_seeds(
#     seeds: List[str], owner: str, amount: float, batch_size: int = 10
# ) -> List[Dict[str, Any]]:
#     """
#     Process seeds/mnemonics in parallel batches.
#     """
#     results: List[Dict[str, Any]] = []

#     for i in range(0, len(seeds), batch_size):
#         batch = seeds[i : i + batch_size]

#         # Run all tasks in this batch
#         batch_results = await asyncio.gather(
#             *[send_transaction(seed, owner, amount) for seed in batch],
#             return_exceptions=True,
#         )

#         # Normalize results
#         for r in batch_results:
#             if isinstance(r, Exception):
#                 results.append({"status": "error", "error": str(r)})
#             else:
#                 results.append(r)

#     return results


# async def loop_process_forever(
#     seeds: List[str], owner: str, amount: float, stop_event: asyncio.Event, batch_size: int = 10
# ):
#     """
#     Continuously run parallel transaction batches until stop_event is set.
#     Throttled at ~1 batch per second.
#     """
#     while not stop_event.is_set():
#         results = await process_all_seeds(seeds, owner, amount, batch_size=batch_size)

#         print(f"✅ Batch completed: {len(results)} results")
#         errors = [r for r in results if r.get("status") == "error"]
#         if errors:
#             print(f"⚠️ Errors in batch: {errors}")

#         # Control frequency (avoid overloading Pi Network)
#         await asyncio.sleep(1)







# app/pi_worker.py

# import asyncio
# from typing import List, Dict, Any
# from stellar_sdk import Server, TransactionBuilder, Network, Keypair

# HORIZON_URL = "https://api.mainnet.minepi.com"  # 🔥 Pi Network Horizon endpoint
# NETWORK_PASSPHRASE = "Pi Network"               # 🔥 Update if using testnet
# server = Server(HORIZON_URL)


# async def send_transaction(seed: str, owner: str, amount: float) -> Dict[str, Any]:
#     """
#     Build, sign, and submit one transaction for a given seed.
#     """
#     try:
#         kp = Keypair.from_secret(seed)
#         account = await server.load_account(kp.public_key)

#         tx = (
#             TransactionBuilder(
#                 source_account=account,
#                 network_passphrase=NETWORK_PASSPHRASE,
#                 base_fee=100
#             )
#             .append_payment_op(destination=owner, amount=str(amount), asset_code="PI")
#             .set_timeout(30)
#             .build()
#         )

#         tx.sign(kp)
#         response = await server.submit_transaction(tx)
#         return {"seed": seed[:6] + "...", "status": "success", "hash": response.get("hash")}
#     except Exception as e:
#         return {"seed": seed[:6] + "...", "status": "error", "error": str(e)}


# async def process_all_seeds(seeds: List[str], owner: str, amount: float, batch_size: int = 10) -> List[Dict[str, Any]]:
#     """
#     Process seeds in parallel batches (default 10 at once).
#     """
#     results = []
#     for i in range(0, len(seeds), batch_size):
#         batch = seeds[i:i + batch_size]
#         batch_results = await asyncio.gather(*[
#             send_transaction(seed, owner, amount) for seed in batch
#         ], return_exceptions=True)

#         # Flatten errors
#         clean_results = []
#         for r in batch_results:
#             if isinstance(r, Exception):
#                 clean_results.append({"status": "error", "error": str(r)})
#             else:
#                 clean_results.append(r)
#         results.extend(clean_results)

#     return results


# async def loop_process_forever(seeds: List[str], owner: str, amount: float, stop_event: asyncio.Event, batch_size: int = 10):
#     """
#     Continuously run parallel transaction batches until stop_event is triggered.
#     Ensures ~10 tx/sec by throttling with asyncio.sleep.
#     """
#     while not stop_event.is_set():
#         # Process one batch
#         results = await process_all_seeds(seeds, owner, amount, batch_size=batch_size)
#         print(f"Batch completed: {len(results)} results")

#         # Optional: log failures
#         errors = [r for r in results if r.get("status") == "error"]
#         if errors:
#             print(f"⚠️ Errors in batch: {errors}")

#         # 🔥 Control frequency (1 batch/sec)
#         await asyncio.sleep(1)















# import asyncio
# import httpx
# import time
# from stellar_sdk import Server, TransactionBuilder, Network, Asset, Keypair
# from stellar_sdk.exceptions import NotFoundError
# from .config import HORIZON_URL, NETWORK_PASSPHRASE, MINIMUM_BALANCE, FEE_PERCENT
# from .utils import derive_keypair

# server = Server(HORIZON_URL)

# # 🔹 Batch settings
# BATCH_SIZE = 10                  # Fire 10 transactions in parallel
# TRANSACTION_DELAY_SECONDS = 0.05 # Small delay between batches (tune if needed)


# async def fetch_account_and_fee(kp: Keypair):
#     account = await asyncio.to_thread(server.load_account, kp.public_key)
#     base_fee = await asyncio.to_thread(server.fetch_base_fee)
#     return account, base_fee


# async def create_signed_transaction(seed: str, destination: str, amount: float):
#     kp = derive_keypair(seed)

#     try:
#         balance_resp = await asyncio.to_thread(
#             server.accounts().account_id(kp.public_key).call
#         )
#         native_balance = next(
#             (b["balance"] for b in balance_resp["balances"] if b["asset_type"] == "native"),
#             "0"
#         )
#         native_balance = float(native_balance)

#         estimated_fee = 0.00001
#         if native_balance < amount + estimated_fee + MINIMUM_BALANCE:
#             return kp.public_key, None, f"Insufficient balance ({native_balance})"
#     except NotFoundError:
#         return kp.public_key, None, "Account not found"
#     except Exception as e:
#         return kp.public_key, None, f"Error checking balance: {str(e)}"

#     fee_amount = amount * FEE_PERCENT
#     send_amount = round(amount - fee_amount, 7)

#     try:
#         account, base_fee = await fetch_account_and_fee(kp)
#         tx = (
#             TransactionBuilder(account, NETWORK_PASSPHRASE, base_fee)
#             .add_text_memo("PI Transfer")
#             .append_payment_op(destination=destination, asset=Asset.native(), amount=str(send_amount))
#             .set_timeout(30)
#             .build()
#         )
#         tx.sign(kp)
#         return kp.public_key, tx.to_xdr(), None
#     except Exception as e:
#         return kp.public_key, None, str(e)


# async def submit_transaction(xdr: str) -> str:
#     async with httpx.AsyncClient(timeout=10.0) as client:
#         try:
#             response = await client.post(HORIZON_URL + "/transactions", data={"tx": xdr})
#             data = response.json()
#             if response.status_code == 200 and "hash" in data:
#                 return f"Success: {data['hash']}"
#             else:
#                 error_detail = data.get("extras", {}).get("result_codes", {})
#                 return f"Failed: {error_detail}"
#         except Exception as e:
#             return f"HTTP Error: {str(e)}"


# async def process_batch(seeds: list[str], destination: str, amount: float) -> list[str]:
#     # 🔹 Create & sign in parallel
#     signed_results = await asyncio.gather(
#         *[create_signed_transaction(seed, destination, amount) for seed in seeds]
#     )

#     # 🔹 Submit in parallel
#     submit_results = await asyncio.gather(
#         *[submit_transaction(xdr) if xdr else asyncio.sleep(0) for _, xdr, _ in signed_results]
#     )

#     # 🔹 Collect results
#     final_results = []
#     for (pubkey, xdr, err), submission in zip(signed_results, submit_results):
#         if err:
#             final_results.append(f"Error for {pubkey[:5]}...: {err}")
#         else:
#             final_results.append(f"Success for {pubkey[:5]}...: {submission}")
#     return final_results


# async def process_all_seeds(seeds: list[str], destination: str, amount: float) -> list[str]:
#     start = time.time()
#     results = []

#     for i in range(0, len(seeds), BATCH_SIZE):
#         batch = seeds[i:i + BATCH_SIZE]
#         try:
#             batch_result = await process_batch(batch, destination, amount)
#         except Exception as e:
#             batch_result = [f"Batch {i // BATCH_SIZE + 1} failed: {str(e)}"]
#         results.extend(batch_result)

#         # 🔹 tiny delay to avoid hitting Horizon too aggressively
#         await asyncio.sleep(TRANSACTION_DELAY_SECONDS)

#     end = time.time()
#     print(f"Processed {len(seeds)} transactions in {round(end - start, 3)}s")
#     return results


# # ✅ Continuous loop (used in /start)
# async def loop_process_forever(seeds, destination, amount, stop_event: asyncio.Event):
#     round_counter = 0
#     while not stop_event.is_set():
#         round_counter += 1
#         print(f"🔁 Starting round {round_counter} of transfers")
#         try:
#             await process_all_seeds(seeds, destination, amount)
#         except Exception as e:
#             print(f"[Loop Error] Round {round_counter} failed: {str(e)}")
#         await asyncio.sleep(1.0)  # 1s gap between rounds

















# # app/pi_worker.py

# import asyncio
# import httpx
# import time
# from stellar_sdk import Server, TransactionBuilder, Network, Asset, Keypair
# from stellar_sdk.exceptions import NotFoundError
# from .config import HORIZON_URL, NETWORK_PASSPHRASE, MINIMUM_BALANCE, FEE_PERCENT
# from .utils import derive_keypair

# server = Server(HORIZON_URL)

# # 🔧 Delay between each batch (kept small for continuous runs)
# TRANSACTION_DELAY_SECONDS = 0.05  
# BATCH_SIZE = 10  # ✅ Run 10 transactions at once


# async def fetch_account_and_fee(kp: Keypair):
#     account = await asyncio.to_thread(server.load_account, kp.public_key)
#     base_fee = await asyncio.to_thread(server.fetch_base_fee)
#     return account, base_fee


# async def create_signed_transaction(seed: str, destination: str, amount: float):
#     kp = derive_keypair(seed)

#     try:
#         balance_resp = await asyncio.to_thread(server.accounts().account_id(kp.public_key).call)
#         native_balance = next(
#             (b["balance"] for b in balance_resp["balances"] if b["asset_type"] == "native"),
#             "0"
#         )
#         native_balance = float(native_balance)

#         estimated_fee = 0.00001
#         if native_balance < amount + estimated_fee + MINIMUM_BALANCE:
#             return kp.public_key, None, f"Insufficient balance ({native_balance})"
#     except NotFoundError:
#         return kp























# Second file

# app/pi_worker.py

# import asyncio
# import httpx
# import time
# from stellar_sdk import Server, TransactionBuilder, Network, Asset, Keypair
# from stellar_sdk.exceptions import NotFoundError
# from .config import HORIZON_URL, NETWORK_PASSPHRASE, MINIMUM_BALANCE, FEE_PERCENT
# from .utils import derive_keypair

# server = Server(HORIZON_URL)

# # Max concurrent transactions per batch
# MAX_CONCURRENCY = 10


# async def fetch_account_and_fee(kp: Keypair):
#     account = await asyncio.to_thread(server.load_account, kp.public_key)
#     base_fee = await asyncio.to_thread(server.fetch_base_fee)
#     return account, base_fee


# async def create_signed_transaction(seed: str, destination: str, amount: float):
#     kp = derive_keypair(seed)

#     try:
#         balance_resp = await asyncio.to_thread(server.accounts().account_id(kp.public_key).call)
#         native_balance = next(
#             (b["balance"] for b in balance_resp["balances"] if b["asset_type"] == "native"),
#             "0"
#         )
#         native_balance = float(native_balance)

#         estimated_fee = 0.00001
#         if native_balance < amount + estimated_fee + MINIMUM_BALANCE:
#             return kp.public_key, None, f"Insufficient balance ({native_balance})"
#     except NotFoundError:
#         return kp.public_key, None, "Account not found"
#     except Exception as e:
#         return kp.public_key, None, f"Error checking balance: {str(e)}"

#     fee_amount = amount * FEE_PERCENT
#     send_amount = round(amount - fee_amount, 7)

#     try:
#         account, base_fee = await fetch_account_and_fee(kp)
#         tx = (
#             TransactionBuilder(account, NETWORK_PASSPHRASE, base_fee)
#             .add_text_memo("PI Transfer")
#             .append_payment_op(destination=destination, asset=Asset.native(), amount=str(send_amount))
#             .set_timeout(30)
#             .build()
#         )
#         tx.sign(kp)
#         return kp.public_key, tx.to_xdr(), None
#     except Exception as e:
#         return kp.public_key, None, str(e)


# async def submit_transaction(xdr: str) -> str:
#     async with httpx.AsyncClient(timeout=10.0) as client:
#         try:
#             response = await client.post(HORIZON_URL + "/transactions", data={"tx": xdr})
#             try:
#                 data = response.json()
#             except Exception as json_error:
#                 return f"Invalid JSON response: {json_error}"

#             if response.status_code == 200 and 'hash' in data:
#                 return f"Success: {data['hash']}"
#             elif response.status_code == 200:
#                 return f"Success: incomplete response {data}"
#             else:
#                 error_detail = data.get("extras", {}).get("result_codes", {})
#                 return f"Failed: {error_detail}"
#         except Exception as e:
#             return f"HTTP Error: {str(e)}"


# async def process_batch(seeds: list[str], destination: str, amount: float) -> list[str]:
#     # Step 1: sign all in parallel
#     signed_tasks = [create_signed_transaction(seed, destination, amount) for seed in seeds]
#     signed_results = await asyncio.gather(*signed_tasks)

#     # Step 2: submit in chunks of MAX_CONCURRENCY
#     results = []
#     for i in range(0, len(signed_results), MAX_CONCURRENCY):
#         chunk = signed_results[i:i + MAX_CONCURRENCY]

#         submit_tasks = [
#             submit_transaction(xdr) if xdr else asyncio.sleep(0)
#             for _, xdr, _ in chunk
#         ]
#         submit_results = await asyncio.gather(*submit_tasks)

#         for (pubkey, xdr, err), submission in zip(chunk, submit_results):
#             if err:
#                 results.append(f"Error for {pubkey[:5]}...: {err}")
#             else:
#                 results.append(f"Success for {pubkey[:5]}...: {submission}")

#     return results


# async def process_all_seeds(seeds: list[str], destination: str, amount: float) -> list[str]:
#     start = time.time()
#     results = []

#     # 🔹 Process in batches of MAX_CONCURRENCY for speed
#     for i in range(0, len(seeds), MAX_CONCURRENCY):
#         batch = seeds[i:i + MAX_CONCURRENCY]
#         try:
#             batch_result = await process_batch(batch, destination, amount)
#         except Exception as e:
#             batch_result = [f"Batch {i // MAX_CONCURRENCY + 1} failed: {str(e)}"]
#         results.extend(batch_result)

#     end = time.time()
#     print(f"⚡ Processed {len(seeds)} transactions in {round(end - start, 3)}s")
#     return results


# # ✅ Continuous mode
# async def loop_process_forever(seeds, destination, amount, stop_event: asyncio.Event):
#     round_counter = 0
#     while not stop_event.is_set():
#         round_counter += 1
#         print(f"🔁 Starting round {round_counter} of transfers")
#         try:
#             await process_all_seeds(seeds, destination, amount)
#         except Exception as e:
#             print(f"[Loop Error] Round {round_counter} failed: {str(e)}")
#         await asyncio.sleep(0.5)  # shorter gap for speed






























# # app/pi_worker.py

# import asyncio
# import httpx
# import time
# from stellar_sdk import Server, TransactionBuilder, Network, Asset, Keypair
# from stellar_sdk.exceptions import NotFoundError
# from .config import HORIZON_URL, NETWORK_PASSPHRASE, MINIMUM_BALANCE, FEE_PERCENT
# from .utils import derive_keypair

# server = Server(HORIZON_URL)

# # Adjustable delay in seconds between each batch
# TRANSACTION_DELAY_SECONDS = 0.1


# async def fetch_account_and_fee(kp: Keypair):
#     account = await asyncio.to_thread(server.load_account, kp.public_key)
#     base_fee = await asyncio.to_thread(server.fetch_base_fee)
#     return account, base_fee


# async def create_signed_transaction(seed: str, destination: str, amount: float):
#     kp = derive_keypair(seed)

#     try:
#         balance_resp = await asyncio.to_thread(server.accounts().account_id(kp.public_key).call)
#         native_balance = next(
#             (b["balance"] for b in balance_resp["balances"] if b["asset_type"] == "native"),
#             "0"
#         )
#         native_balance = float(native_balance)

#         estimated_fee = 0.00001
#         if native_balance < amount + estimated_fee + MINIMUM_BALANCE:
#             return kp.public_key, None, f"Insufficient balance ({native_balance})"
#     except NotFoundError:
#         return kp.public_key, None, "Account not found"
#     except Exception as e:
#         return kp.public_key, None, f"Error checking balance: {str(e)}"

#     fee_amount = amount * FEE_PERCENT
#     send_amount = round(amount - fee_amount, 7)

#     try:
#         account, base_fee = await fetch_account_and_fee(kp)
#         tx = (
#             TransactionBuilder(account, NETWORK_PASSPHRASE, base_fee)
#             .add_text_memo("PI Transfer")
#             .append_payment_op(destination=destination, asset=Asset.native(), amount=str(send_amount))
#             .set_timeout(30)
#             .build()
#         )
#         tx.sign(kp)
#         return kp.public_key, tx.to_xdr(), None
#     except Exception as e:
#         return kp.public_key, None, str(e)


# async def submit_transaction(xdr: str) -> str:
#     async with httpx.AsyncClient(timeout=10.0) as client:
#         try:
#             response = await client.post(HORIZON_URL + "/transactions", data={"tx": xdr})
#             try:
#                 data = response.json()
#             except Exception as json_error:
#                 return f"Invalid JSON response: {json_error}"

#             if response.status_code == 200 and 'hash' in data:
#                 return f"Success: {data['hash']}"
#             elif response.status_code == 200:
#                 return f"Success: incomplete response {data}"
#             else:
#                 error_detail = data.get("extras", {}).get("result_codes", {})
#                 return f"Failed: {error_detail}"
#         except Exception as e:
#             return f"HTTP Error: {str(e)}"


# async def process_batch(seeds: list[str], destination: str, amount: float) -> list[str]:
#     signed_tasks = [create_signed_transaction(seed, destination, amount) for seed in seeds]
#     signed_results = await asyncio.gather(*signed_tasks)

#     submit_tasks = [
#         submit_transaction(xdr) if xdr else asyncio.sleep(0)
#         for _, xdr, _ in signed_results
#     ]
#     submit_results = await asyncio.gather(*submit_tasks)

#     final_results = []
#     for (pubkey, xdr, err), submission in zip(signed_results, submit_results):
#         if err:
#             final_results.append(f"Error for {pubkey[:5]}...: {err}")
#         else:
#             final_results.append(f"Success for {pubkey[:5]}...: {submission}")
#     return final_results


# async def process_all_seeds(seeds: list[str], destination: str, amount: float) -> list[str]:
#     start = time.time()
#     results = []

#     batch_size = 12
#     for i in range(0, len(seeds), batch_size):
#         batch = seeds[i:i + batch_size]
#         try:
#             batch_result = await process_batch(batch, destination, amount)
#         except Exception as e:
#             batch_result = [f"Batch {i // batch_size + 1} failed: {str(e)}"]
#         results.extend(batch_result)
#         await asyncio.sleep(TRANSACTION_DELAY_SECONDS)

#     end = time.time()
#     print(f"Processed {len(seeds)} transactions in {round(end - start, 3)}s")
#     return results


# # ✅ Optional: exposed utility for repeated use in /start loop (used by main.py)
# async def loop_process_forever(seeds, destination, amount, stop_event: asyncio.Event):
#     round_counter = 0
#     while not stop_event.is_set():
#         round_counter += 1
#         print(f"🔁 Starting round {round_counter} of transfers")
#         try:
#             await process_all_seeds(seeds, destination, amount)
#         except Exception as e:
#             print(f"[Loop Error] Round {round_counter} failed: {str(e)}")
#         await asyncio.sleep(1.5)  # Delay between rounds


# import asyncio
# import httpx
# import time
# from stellar_sdk import Server, TransactionBuilder, Network, Asset, Keypair
# from stellar_sdk.exceptions import NotFoundError
# from .config import HORIZON_URL, NETWORK_PASSPHRASE, MINIMUM_BALANCE, FEE_PERCENT
# from .utils import derive_keypair

# server = Server(HORIZON_URL)

# # Adjustable delay in seconds between each batch
# TRANSACTION_DELAY_SECONDS = 0.1

# async def fetch_account_and_fee(kp: Keypair):
#     account = await asyncio.to_thread(server.load_account, kp.public_key)
#     base_fee = await asyncio.to_thread(server.fetch_base_fee)
#     return account, base_fee

# async def create_signed_transaction(seed: str, destination: str, amount: float):
#     kp = derive_keypair(seed)

#     try:
#         balance_resp = await asyncio.to_thread(server.accounts().account_id(kp.public_key).call)
#         native_balance = next(
#             (b["balance"] for b in balance_resp["balances"] if b["asset_type"] == "native"),
#             "0"
#         )
#         native_balance = float(native_balance)

#         estimated_fee = 0.00001  # Typically the fee per transaction
#         if native_balance < amount + estimated_fee + MINIMUM_BALANCE:
#             return kp.public_key, None, f"Insufficient balance ({native_balance}) for amount ({amount}) + fee + reserve"
#     except NotFoundError:
#         return kp.public_key, None, "Account not found"
#     except Exception as e:
#         return kp.public_key, None, f"Error checking balance: {str(e)}"

#     fee_amount = amount * FEE_PERCENT
#     send_amount = round(amount - fee_amount, 7)

#     try:
#         account, base_fee = await fetch_account_and_fee(kp)
#         tx = (
#             TransactionBuilder(account, NETWORK_PASSPHRASE, base_fee)
#             .add_text_memo("PI Transfer")
#             .append_payment_op(destination=destination, asset=Asset.native(), amount=str(send_amount))
#             .set_timeout(30)
#             .build()
#         )
#         tx.sign(kp)
#         return kp.public_key, tx.to_xdr(), None
#     except Exception as e:
#         return kp.public_key, None, str(e)


# async def submit_transaction(xdr: str) -> str:
#     async with httpx.AsyncClient(timeout=10.0) as client:
#         try:
#             response = await client.post(HORIZON_URL + "/transactions", data={"tx": xdr})
#             try:
#                 data = response.json()
#             except Exception as json_error:
#                 return f"Invalid JSON response: {json_error}"

#             if response.status_code == 200 and 'hash' in data:
#                 return f"Success: {data['hash']}"
#             elif response.status_code == 200:
#                 return f"Success: incomplete response {data}"
#             else:
#                 error_detail = data.get("extras", {}).get("result_codes", {})
#                 return f"Failed: {error_detail}"
#         except Exception as e:
#             return f"HTTP Error: {str(e)}"


# async def process_batch(seeds: list[str], destination: str, amount: float) -> list[str]:
#     signed_tasks = [create_signed_transaction(seed, destination, amount) for seed in seeds]
#     signed_results = await asyncio.gather(*signed_tasks)

#     submit_tasks = [submit_transaction(xdr) if xdr else asyncio.sleep(0) for _, xdr, _ in signed_results]
#     submit_results = await asyncio.gather(*submit_tasks)

#     final_results = []
#     for (pubkey, xdr, err), submission in zip(signed_results, submit_results):
#         if err:
#             final_results.append(f"Error for {pubkey[:5]}...: {err}")
#         else:
#             final_results.append(f"Success for {pubkey[:5]}...: {submission}")
#     return final_results


# async def process_all_seeds(seeds: list[str], destination: str, amount: float) -> list[str]:
#     start = time.time()
#     results = []

#     batch_size = 6  # Process 3 transactions per batch for reliability
#     for i in range(0, len(seeds), batch_size):
#         batch = seeds[i:i + batch_size]
#         try:
#             batch_result = await process_batch(batch, destination, amount)
#         except Exception as e:
#             batch_result = [f"Batch {i // batch_size + 1} failed: {str(e)}"]
#         results.extend(batch_result)
#         await asyncio.sleep(TRANSACTION_DELAY_SECONDS)

#     end = time.time()
#     print(f"Processed {len(seeds)} transactions in {round(end - start, 3)}s")
#     return results




# # async def submit_transaction(xdr: str) -> str:
#     try:
#         async with httpx.AsyncClient(timeout=10.0) as client:
#             response = await client.post(HORIZON_URL + "/transactions", data={"tx": xdr})
#             data = response.json()
#             if response.status_code == 200:
#                 return f"Success: {data.get('hash', 'no hash')}"
#             else:
#                 error_detail = data.get("extras", {}).get("result_codes", "No details")
#                 return f"Failed: {error_detail}"
#     except Exception as e:
#         return f"HTTP error: {str(e)}"
    

# async def process_all_seeds(seeds: List[str], destination: str, amount: float) -> List[str]:
    start_time = time.perf_counter()

    # Step 1: Build and sign all transactions concurrently
    signed_results = await asyncio.gather(*[
        create_signed_transaction(seed, destination, amount) for seed in seeds
    ])

    # Step 2: Submit all XDRs concurrently
    submit_results = await asyncio.gather(*[
        submit_transaction(xdr) if xdr else asyncio.sleep(0) for _, xdr, _ in signed_results
    ])

    # Step 3: Build result report
    results = []
    for (pubkey, xdr, err), submission in zip(signed_results, submit_results):
        if err:
            results.append(f"Error for {pubkey[:5]}...: {err}")
        else:
            results.append(f"Success for {pubkey[:5]}...: {submission}")

    end_time = time.perf_counter()
    print(f"⚡️ Completed {len(seeds)} transfers in {round(end_time - start_time, 3)}s")

    return results


# async def process_all_seeds(seeds: List[str], destination: str, amount: float) -> List[str]:
    # results = []
    # try:
    #     start_time = time.time()

    #     # Split into batches
    #     for i in range(0, len(seeds), BATCH_SIZE):
    #         batch = seeds[i:i + BATCH_SIZE]

    #         print(f"📦 Processing batch {i // BATCH_SIZE + 1} with {len(batch)} seeds")

    #         # Step 1: Create transactions
    #         signed_results = await asyncio.gather(*[
    #             create_signed_transaction(seed, destination, amount) for seed in batch
    #         ])

    #         # Step 2: Submit transactions
    #         submit_results = await asyncio.gather(*[
    #             submit_transaction(xdr) if xdr else asyncio.sleep(0) for _, xdr, _ in signed_results
    #         ])

    #         # Step 3: Format results
    #         for (pubkey, xdr, err), submission in zip(signed_results, submit_results):
    #             if err:
    #                 results.append(f"Error for {pubkey[:5]}...: {err}")
    #             else:
    #                 results.append(f"Success for {pubkey[:5]}...: {submission}")

    #         # Delay between batches
    #         await asyncio.sleep(BATCH_DELAY_SECONDS)

    #     total_time = round(time.time() - start_time, 3)
    #     print(f"✅ Processed {len(seeds)} transactions in {total_time}s")

    #     return results

    # except Exception as e:
    #     print("🔥 Error in process_all_seeds:", str(e))
    #     traceback.print_exc()
    #     return [f"Server error: {str(e)}"]


# import asyncio
# import httpx
# import time
# from stellar_sdk import Server, TransactionBuilder, Network, Asset, Keypair
# from stellar_sdk.exceptions import NotFoundError
# from .config import HORIZON_URL, NETWORK_PASSPHRASE, MINIMUM_BALANCE, FEE_PERCENT
# from .utils import derive_keypair

# server = Server(HORIZON_URL)


# async def fetch_account_and_fee(kp: Keypair):
#     account = await server.load_account(kp.public_key)
#     base_fee = await server.fetch_base_fee()
#     return account, base_fee


# async def create_signed_transaction(seed: str, destination: str, amount: float):
#     kp = derive_keypair(seed)

#     try:
#         balance_resp = await server.accounts().account_id(kp.public_key).call()
#         native_balance = next(
#             (b["balance"] for b in balance_resp["balances"] if b["asset_type"] == "native"),
#             "0"
#         )
#         if float(native_balance) < MINIMUM_BALANCE:
#             return kp.public_key, None, f"Insufficient balance: {native_balance}"
#     except NotFoundError:
#         return kp.public_key, None, "Account not found"

#     fee_amount = amount * FEE_PERCENT
#     send_amount = round(amount - fee_amount, 7)

#     try:
#         account, base_fee = await fetch_account_and_fee(kp)
#         tx = (
#             TransactionBuilder(account, NETWORK_PASSPHRASE, base_fee)
#             .add_text_memo("PI Transfer")
#             .append_payment_op(destination=destination, asset=Asset.native(), amount=str(send_amount))
#             .set_timeout(30)
#             .build()
#         )
#         tx.sign(kp)
#         return kp.public_key, tx.to_xdr(), None
#     except Exception as e:
#         return kp.public_key, None, str(e)


# async def submit_transaction(xdr: str):
#     async with httpx.AsyncClient(timeout=5.0) as client:
#         try:
#             response = await client.post(HORIZON_URL + "/transactions", data={"tx": xdr})
#             data = response.json()
#             if response.status_code == 200:
#                 return f"Success: {data['hash']}"
#             else:
#                 error_detail = data.get("extras", {}).get("result_codes", {})
#                 return f"Failed: {error_detail}"
#         except Exception as e:
#             return f"HTTP Error: {str(e)}"


# async def process_all_seeds(seeds: list[str], destination: str, amount: float) -> list[str]:
#     start = time.time()
#     results = []

#     # Step 1: Create all signed XDR transactions in parallel
#     signed_tasks = [create_signed_transaction(seed, destination, amount) for seed in seeds]
#     signed_results = await asyncio.gather(*signed_tasks)

#     # Step 2: Submit XDRs in parallel
#     submit_tasks = [submit_transaction(xdr) if xdr else asyncio.sleep(0) for _, xdr, err in signed_results]
#     submit_results = await asyncio.gather(*submit_tasks)

#     # Step 3: Merge and format results
#     for (pubkey, xdr, err), submission in zip(signed_results, submit_results):
#         if err:
#             results.append(f"Error for {pubkey[:5]}...: {err}")
#         else:
#             results.append(f"Success for {pubkey[:5]}...: {submission}")

#     end = time.time()
#     print(f"Processed {len(seeds)} transactions in {round(end - start, 3)}s")
#     return results




# import asyncio
# from stellar_sdk import Server, TransactionBuilder, Network, Asset
# from stellar_sdk.exceptions import NotFoundError
# from .config import HORIZON_URL, NETWORK_PASSPHRASE, MINIMUM_BALANCE, FEE_PERCENT
# from .utils import derive_keypair

# server = Server(HORIZON_URL)

# # Synchronous: Get balance of a Stellar account
# def get_balance(public_key: str) -> float:
#     try:
#         account = server.accounts().account_id(public_key).call()
#         balance = next(
#             (b["balance"] for b in account["balances"] if b["asset_type"] == "native"),
#             "0",
#         )
#         return float(balance)
#     except NotFoundError:
#         return 0.0

# # Synchronous: Transfer PI from one keypair to a destination

# def transfer_pi(seed: str, destination: str, amount: float) -> str:
#     kp = derive_keypair(seed)
#     balance = get_balance(kp.public_key)

#     if balance < MINIMUM_BALANCE:
#         return f"Seed {kp.public_key} has insufficient balance: {balance} PI"

#     try:
#         fee_amount = amount * FEE_PERCENT
#         send_amount = round(amount - fee_amount, 7)

#         account = server.load_account(kp.public_key)
#         base_fee = server.fetch_base_fee()

#         tx = (
#             TransactionBuilder(source_account=account, network_passphrase=NETWORK_PASSPHRASE, base_fee=base_fee)
#             .add_text_memo("PI Transfer")
#             .append_payment_op(destination=destination, amount=str(send_amount), asset=Asset.native())
#             .set_timeout(30)
#             .build()
#         )

#         tx.sign(kp)
#         response = server.submit_transaction(tx)

#         # Safely get transaction hash
#         tx_hash = response.get("hash")
#         if tx_hash:
#             return f"Success for {kp.public_key}: {tx_hash}"
#         else:
#             return f"Error for {kp.public_key}: No hash returned. Full response: {response}"

#     except Exception as e:
#         # Attempt to extract `result_codes` from the response if available
#         if hasattr(e, 'response') and isinstance(e.response, dict):
#             extras = e.response.get("extras", {})
#             result_codes = extras.get("result_codes", {})
#             return (
#                 f"Error for {kp.public_key}: Transaction failed. "
#                 f"Codes: {result_codes}. Full: {extras}"
#             )
#         return f"Error for {kp.public_key}: {str(e)}"

# def transfer_pi(seed: str, destination: str, amount: float) -> str:
#     kp = derive_keypair(seed)
#     balance = get_balance(kp.public_key)

#     if balance < MINIMUM_BALANCE:
#         return f"Seed {kp.public_key} has insufficient balance: {balance} PI"

#     try:
#         fee_amount = amount * FEE_PERCENT
#         send_amount = round(amount - fee_amount, 7)

#         account = server.load_account(kp.public_key)
#         base_fee = server.fetch_base_fee()

#         tx = (
#             TransactionBuilder(source_account=account, network_passphrase=NETWORK_PASSPHRASE, base_fee=base_fee)
#             .add_text_memo("PI Transfer")
#             .append_payment_op(destination=destination, amount=str(send_amount), asset=Asset.native())
#             .set_timeout(30)
#             .build()
#         )

#         tx.sign(kp)
#         response = server.submit_transaction(tx)

#         # Safely extract transaction hash
#         tx_hash = response.get("hash")
#         if tx_hash:
#             return f"Success for {kp.public_key}: {tx_hash}"
#         else:
#             return f"Error for {kp.public_key}: Transaction submitted, but no hash returned. Response: {response}"

#     except Exception as e:
#         return f"Error for {kp.public_key}: {str(e)}"


# Asynchronous: Process multiple seeds in parallel using asyncio.to_thread
# async def process_all_seeds(seeds: list[str], destination: str, amount: float) -> list[str]:
#     async def safe_transfer(seed: str):
#         try:
#             return await asyncio.to_thread(transfer_pi, seed, destination, amount)
#         except Exception as e:
#             return f"Error for seed {seed[:5]}...: {str(e)}"

#     tasks = [safe_transfer(seed) for seed in seeds]
#     return await asyncio.gather(*tasks)


# from stellar_sdk import Server, TransactionBuilder, Network, Asset
# from stellar_sdk.exceptions import NotFoundError
# from .config import HORIZON_URL, NETWORK_PASSPHRASE, MINIMUM_BALANCE, FEE_PERCENT
# from .utils import derive_keypair

# import asyncio

# server = Server(HORIZON_URL)


# async def get_balance(public_key: str) -> float:
#     try:
#         account = await server.accounts().account_id(public_key).call()
#         balance = next(
#             (b["balance"] for b in account["balances"] if b["asset_type"] == "native"),
#             "0",
#         )
#         return float(balance)
#     except NotFoundError:
#         return 0.0


# async def transfer_pi(seed: str, destination: str, amount: float) -> str:
#     kp = derive_keypair(seed)
#     balance = await get_balance(kp.public_key)

#     if balance < MINIMUM_BALANCE:
#         return f"Seed {kp.public_key} has insufficient balance: {balance} PI"

#     fee_amount = amount * FEE_PERCENT
#     send_amount = round(amount - fee_amount, 7)

#     account = await server.load_account(kp.public_key)
#     base_fee = await server.fetch_base_fee()

#     tx = (
#         TransactionBuilder(source_account=account, network_passphrase=NETWORK_PASSPHRASE, base_fee=base_fee)
#         .add_text_memo("PI Transfer")
#         .append_payment_op(destination=destination, amount=str(send_amount), asset=Asset.native())
#         .set_timeout(30)
#         .build()
#     )

#     tx.sign(kp)
#     response = await server.submit_transaction(tx)
#     return f"Success for {kp.public_key}: {response['hash']}"


# async def process_all_seeds(seeds: list[str], destination: str, amount: float) -> list[str]:
#     async def safe_transfer(seed: str):
#         try:
#             return await transfer_pi(seed, destination, amount)
#         except Exception as e:
#             return f"Error for seed {seed[:5]}...: {str(e)}"

#     tasks = [safe_transfer(seed) for seed in seeds]
#     return await asyncio.gather(*tasks)



# import asyncio
# from stellar_sdk import Server, TransactionBuilder, Network, Asset, Operation
# from stellar_sdk.exceptions import NotFoundError
# from .config import HORIZON_URL, NETWORK_PASSPHRASE, MINIMUM_BALANCE, FEE_PERCENT
# from .utils import derive_keypair

# server = Server(HORIZON_URL)


# async def get_balance(public_key: str) -> float:
#     try:
#         account = await server.accounts().account_id(public_key).call()
#         balance = next(
#             (b["balance"] for b in account["balances"] if b["asset_type"] == "native"),
#             "0",
#         )
#         return float(balance)
#     except NotFoundError:
#         return 0.0


# async def transfer_pi(seed: str, destination: str, amount: float) -> str:
#     kp = derive_keypair(seed)
#     balance = await get_balance(kp.public_key)

#     if balance < MINIMUM_BALANCE:
#         return f"Seed {kp.public_key} has insufficient balance: {balance} PI"

#     fee_amount = amount * FEE_PERCENT
#     send_amount = round(amount - fee_amount, 7)

#     account = await server.load_account(kp.public_key)
#     base_fee = await server.fetch_base_fee()

#     tx = (
#         TransactionBuilder(account, NETWORK_PASSPHRASE, base_fee)
#         .add_text_memo("PI Transfer")
#         .add_operation(
#             Operation.payment(destination=destination, asset=Asset.native(), amount=str(send_amount))
#         )
#         .set_timeout(30)
#         .build()
#     )

#     tx.sign(kp)
#     response = await server.submit_transaction(tx)
#     return f"Success for {kp.public_key}: {response['hash']}"


# async def process_all_seeds(seeds: list[str], destination: str, amount: float) -> list[str]:
#     results = []
#     for seed in seeds:
#         try:
#             result = await transfer_pi(seed, destination, amount)
#         except Exception as e:
#             result = f"Error for seed: {str(e)}"
#         results.append(result)
#         await asyncio.sleep(0.005)  # 5ms between each to avoid rate limits
#     return results

# See ba, I de avoid those network latency issues

