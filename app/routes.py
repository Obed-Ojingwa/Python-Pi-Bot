# app/routes.py



# app/routes.py

from fastapi import APIRouter, Query
from app.utils import derive_keypair

router = APIRouter()

@router.get("/check-address")
async def check_address(mnemonic: str = Query(..., description="BIP39 mnemonic phrase")):
    """
    Returns the public address for a given mnemonic (useful to validate seed).
    """
    try:
        kp = derive_keypair(mnemonic)
        return {"address": kp.public_key}
    except Exception as e:
        return {"error": str(e)}




# from fastapi import APIRouter, Query
# from app.utils import derive_keypair

# router = APIRouter()

# @router.get("/check-address")
# async def check_address(mnemonic: str = Query(..., description="BIP39 mnemonic phrase")):
#     try:
#         keypair = derive_keypair(mnemonic)
#         return {"address": keypair.public_key}
#     except Exception as e:
#         return {"error": str(e)}
