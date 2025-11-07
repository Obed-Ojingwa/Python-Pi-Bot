# app/main.py

import asyncio
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request


from app.pi_worker import process_all_seeds, process_all_seeds_turbo, loop_process_forever, loop_turbo_forever

app = FastAPI(title="Pi Transaction Bot")

# Mount static folder (for JS/CSS if needed)
# app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Globals for continuous execution
continuous_task = None
turbo_task = None
stop_event = asyncio.Event()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the index page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/transfer")
async def api_transfer(
    seeds: str = Form(..., description="Comma-separated list of raw seeds"),
    destination: str = Form(..., description="Destination address"),
    amount: float = Form(..., description="Amount to send"),
):
    """
    Perform a one-off batch transfer.
    """
    seeds_list = [s.strip() for s in seeds.split(",") if s.strip()]
    results = await process_all_seeds(seeds_list, destination, amount)
    return {"results": results}


@app.post("/start")
async def start_continuous(
    seeds: str = Form(...),
    destination: str = Form(...),
    amount: float = Form(...),
):
    """
    Start continuous normal transfers.
    """
    global continuous_task, stop_event
    if continuous_task and not continuous_task.done():
        return {"message": "Normal loop already running"}

    stop_event = asyncio.Event()
    seeds_list = [s.strip() for s in seeds.split(",") if s.strip()]
    continuous_task = asyncio.create_task(loop_process_forever(seeds_list, destination, amount, stop_event))
    return {"message": "Normal continuous transfers started 🚀"}


@app.post("/stop")
async def stop_continuous():
    """
    Stop continuous normal transfers.
    """
    global stop_event
    if not stop_event.is_set():
        stop_event.set()
        return {"message": "Normal continuous transfers stopped ⛔"}
    return {"message": "No normal loop running"}


@app.post("/start_turbo")
async def start_turbo(
    seeds: str = Form(...),
    destination: str = Form(...),
    amount: float = Form(...),
):
    """
    Start continuous turbo transfers (10 tx/sec).
    """
    global turbo_task, stop_event
    if turbo_task and not turbo_task.done():
        return {"message": "Turbo loop already running"}

    stop_event = asyncio.Event()
    seeds_list = [s.strip() for s in seeds.split(",") if s.strip()]
    turbo_task = asyncio.create_task(loop_turbo_forever(seeds_list, destination, amount, stop_event))
    return {"message": "🚀 Turbo continuous transfers started (10 tx/sec)"}


@app.post("/stop_turbo")
async def stop_turbo():
    """
    Stop continuous turbo transfers.
    """
    global stop_event
    if not stop_event.is_set():
        stop_event.set()
        return {"message": "Turbo continuous transfers stopped ⛔"}
    return {"message": "No turbo loop running"}










# app/main.py








# # File: app/main.py

# import asyncio 
# from fastapi import FastAPI, Form
# from fastapi.responses import HTMLResponse
# from fastapi.staticfiles import StaticFiles
# from fastapi.templating import Jinja2Templates
# from starlette.requests import Request
# from app.pi_worker import process_all_seeds, loop_process_forever, loop_turbo_forever
# from app.pi_worker import loop_process_forever, loop_turbo_batches
# import threading

# app = FastAPI()

# # Mount static files (css, js if you add them later)
# app.mount("/static", StaticFiles(directory="app/static"), name="static")

# # Setup Jinja2 templates
# templates = Jinja2Templates(directory="app/templates")

# # Global background task handles
# continuous_task = None
# turbo_task = None
# stop_event = None
# turbo_stop_event = None


# @app.get("/", response_class=HTMLResponse)
# async def index(request: Request):
#     return templates.TemplateResponse("index.html", {"request": request})


# @app.post("/start")
# async def start(seeds: str = Form(...), destination: str = Form(...), amount: str = Form(...)):
#     global continuous_task, stop_event

#     if continuous_task and not continuous_task.done():
#         return {"message": "⚠️ Continuous transfers already running"}

#     stop_event = asyncio.Event()
#     seeds_list = [s.strip() for s in seeds.splitlines() if s.strip()]

#     try:
#         amount_f = float(amount)
#     except ValueError:
#         return {"message": "⚠️ Invalid amount"}

#     continuous_task = asyncio.create_task(
#         loop_process_forever(seeds_list, destination, amount_f, stop_event)
#     )

#     return {"message": "🚀 Continuous transfer started"}


# @app.post("/stop")
# async def stop():
#     global continuous_task, stop_event

#     if stop_event:
#         stop_event.set()
#     continuous_task = None
#     return {"message": "🛑 Continuous transfer stopped"}


# @app.post("/start_turbo")
# async def start_turbo(seeds: str = Form(...), destination: str = Form(...), amount: str = Form(...)):
#     global turbo_task, turbo_stop_event

#     if turbo_task and not turbo_task.done():
#         return {"message": "⚠️ Turbo batching already running"}

#     turbo_stop_event = asyncio.Event()
#     seeds_list = [s.strip() for s in seeds.splitlines() if s.strip()]

#     try:
#         amount_f = float(amount)
#     except ValueError:
#         return {"message": "⚠️ Invalid amount"}

#     # Launch turbo batching loop
#     turbo_task = asyncio.create_task(
#         loop_turbo_batches(seeds_list, destination, amount_f, turbo_stop_event)
#     )

#     return {"message": "🚀 Turbo batching started (≈10 tx/sec)"}


# @app.post("/stop_turbo")
# async def stop_turbo():
#     global turbo_task, turbo_stop_event

#     if turbo_stop_event:
#         turbo_stop_event.set()
#     turbo_task = None
#     return {"message": "🛑 Turbo batching stopped"}
















# import asyncio
# from fastapi import FastAPI, Request
# from fastapi.responses import HTMLResponse, JSONResponse
# from fastapi.templating import Jinja2Templates

# from app.routes import router
# from .pi_worker import process_all_seeds, loop_process_forever

# from pydantic import BaseModel
# from typing import List, Optional

# app = FastAPI()
# app.include_router(router)
# templates = Jinja2Templates(directory="app/templates")


# class TransferRequest(BaseModel):
#     owner: str
#     amount: float
#     seeds: List[str]


# # Globals to control the background loop
# continuous_task: Optional[asyncio.Task] = None
# stop_event: Optional[asyncio.Event] = None


# @app.get("/", response_class=HTMLResponse)
# async def form_ui(request: Request):
#     return templates.TemplateResponse("index.html", {"request": request})


# @app.post("/api/transfer")
# async def transfer(data: TransferRequest):
#     try:
#         results = await process_all_seeds(data.seeds, data.owner, data.amount)
#         return JSONResponse(content={"results": results})
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"error": f"Internal Server Error: {str(e)}"})


# def _parse_seeds_input(seeds_raw) -> List[str]:
#     """Normalize seeds input: accept list, newline-separated, or comma-separated string."""
#     if seeds_raw is None:
#         return []
#     if isinstance(seeds_raw, list):
#         # Flatten any lines inside list entries
#         out = []
#         for item in seeds_raw:
#             if isinstance(item, str):
#                 out.extend([s.strip() for s in item.splitlines() if s.strip()])
#         return out
#     if isinstance(seeds_raw, str):
#         # prefer newlines
#         if "\n" in seeds_raw:
#             return [s.strip() for s in seeds_raw.splitlines() if s.strip()]
#         if "," in seeds_raw:
#             return [s.strip() for s in seeds_raw.split(",") if s.strip()]
#         return [seeds_raw.strip()] if seeds_raw.strip() else []
#     return []


# @app.post("/start")
# async def start_loop(request: Request):
#     """
#     Start continuous transfers.
#     Accepts either:
#       - FormData with fields: seeds (string), destination (string), amount (string/number)
#       - JSON body: { "seeds": [... or "a,b,c" or "line\nline"], "owner"/"destination": "...", "amount": ... }
#     """
#     global continuous_task, stop_event

#     if continuous_task and not continuous_task.done():
#         return JSONResponse(content={"message": "Transfer loop already running."})

#     # Try to parse form first, otherwise JSON
#     seeds_raw = None
#     destination = None
#     amount_val = None

#     content_type = request.headers.get("content-type", "")
#     try:
#         if "application/json" in content_type:
#             body = await request.json()
#             seeds_raw = body.get("seeds")
#             destination = body.get("owner") or body.get("destination")
#             amount_val = body.get("amount")
#         else:
#             form = await request.form()
#             seeds_raw = form.get("seeds")
#             destination = form.get("destination") or form.get("owner")
#             amount_val = form.get("amount")
#     except Exception:
#         # fallback attempt for JSON
#         try:
#             body = await request.json()
#             seeds_raw = body.get("seeds")
#             destination = body.get("owner") or body.get("destination")
#             amount_val = body.get("amount")
#         except Exception:
#             return JSONResponse(status_code=400, content={"message": "Bad request — could not parse body."})

#     seeds_list = _parse_seeds_input(seeds_raw)
#     if not seeds_list:
#         return JSONResponse(status_code=400, content={"message": "No valid seeds provided."})
#     if not destination:
#         return JSONResponse(status_code=400, content={"message": "Destination (owner) missing."})
    
#         # --- Amount handling ---
#     try:
#         if amount_val is None:
#             return JSONResponse(status_code=400, content={"message": "Amount missing."})

#         # Force to string first (handles UploadFile, int, float, str)
#         amount_str = str(amount_val)
#         amount_f = float(amount_str)
#     except Exception:
#         return JSONResponse(status_code=400, content={"message": "Invalid amount."})


#     # try:
#     #     amount_f = float(amount_val)
#     # except Exception:
#     #     return JSONResponse(status_code=400, content={"message": "Invalid amount."})

#     # # create stop_event and start background task (pass stop_event into loop)
#     # stop_event = asyncio.Event()
#     # continuous_task = asyncio.create_task(loop_process_forever(seeds_list, destination, amount_f, stop_event))

#     # return JSONResponse(content={"message": "Continuous transfer started.", "seeds_count": len(seeds_list)})


# @app.post("/stop")
# async def stop_loop():
#     """
#     Stop background continuous transfers.
#     """
#     global continuous_task, stop_event

#     if stop_event:
#         stop_event.set()

#     if continuous_task:
#         try:
#             # wait for the loop to finish gracefully
#             await continuous_task
#         except asyncio.CancelledError:
#             pass
#         continuous_task = None

#     return JSONResponse(content={"message": "Transfer loop stopped."})


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)






"""
    With an error below:
    Parsing error.
"""

# # app/main.py

# import asyncio
# from fastapi import FastAPI, Request, Form
# from fastapi.responses import HTMLResponse
# from fastapi.templating import Jinja2Templates
# from fastapi.staticfiles import StaticFiles

# from app.routes import router as api_router
# from app.pi_worker import loop_process_forever, stop_processing

# app = FastAPI()

# # Mount static files (CSS, JS, etc.)
# app.mount("/static", StaticFiles(directory="app/static"), name="static")

# # Templates
# templates = Jinja2Templates(directory="app/templates")

# # Global task reference for continuous loop
# continuous_task: asyncio.Task | None = None


# @app.get("/", response_class=HTMLResponse)
# async def read_root(request: Request):
#     """
#     Render the main data-entry page.
#     """
#     return templates.TemplateResponse("index.html", {"request": request})


# @app.post("/start")
# async def start_transfers(
#     request: Request,
#     seeds: str = Form(..., description="Comma-separated list of mnemonics/seeds"),
#     destination: str = Form(..., description="Recipient Pi/Stellar address"),
#     amount: str = Form(..., description="Amount to send")
# ):
#     """
#     Start continuous parallel transaction batching.
#     Runs until /stop is called.
#     """
#     global continuous_task
#     if continuous_task and not continuous_task.done():
#         return {"status": "already_running"}

#     seeds_list = [s.strip() for s in seeds.split(",") if s.strip()]

#     # Kick off continuous background loop
#     continuous_task = asyncio.create_task(
#         loop_process_forever(seeds_list, destination, amount)
#     )

#     return {"status": "started", "seeds_count": len(seeds_list)}


# @app.post("/stop")
# async def stop_transfers():
#     """
#     Stop continuous batching gracefully.
#     """
#     global continuous_task
#     stop_processing()
#     if continuous_task:
#         continuous_task.cancel()
#         try:
#             await continuous_task
#         except asyncio.CancelledError:
#             pass
#         continuous_task = None

#     return {"status": "stopped"}


# # Register API routes (like /check-address)
# app.include_router(api_router, prefix="/api")


# # app/main.py

# from fastapi import FastAPI, Request
# from fastapi.responses import HTMLResponse, JSONResponse
# from fastapi.templating import Jinja2Templates
# from fastapi.staticfiles import StaticFiles
# from .pi_worker import process_all_seeds, loop_process_forever
# from app.routes import router

# import asyncio
# from pydantic import BaseModel
# from typing import List, Optional

# class TransferRequest(BaseModel):
#     owner: str
#     amount: float
#     seeds: List[str]

# app = FastAPI()
# app.include_router(router)
# templates = Jinja2Templates(directory="app/templates")

# @app.get("/", response_class=HTMLResponse)
# async def form_ui(request: Request):
#     return templates.TemplateResponse("index.html", {"request": request})


# @app.post("/api/transfer")
# async def transfer(data: TransferRequest):
#     """
#     One-time execution of parallel batch transfers.
#     """
#     try:
#         results = await process_all_seeds(
#             seeds=data.seeds,
#             owner=data.owner,
#             amount=data.amount,
#             batch_size=10   # 🔥 force batching here
#         )
#         return JSONResponse(content={"results": results})
#     except Exception as e:
#         return JSONResponse(
#             status_code=500,
#             content={"error": f"Internal Server Error: {str(e)}"}
#         )


# # ✅ Background continuous loop control
# loop_task: Optional[asyncio.Task] = None
# stop_event: Optional[asyncio.Event] = None


# @app.post("/start")
# async def start_loop(data: TransferRequest):
#     """
#     Start continuous transfers in parallel batching mode.
#     """
#     global loop_task, stop_event

#     if loop_task and not loop_task.done():
#         return {"message": "⚠️ Transfer loop already running."}

#     stop_event = asyncio.Event()
#     loop_task = asyncio.create_task(
#         loop_process_forever(
#             seeds=data.seeds,
#             owner=data.owner,
#             amount=data.amount,
#             stop_event=stop_event,
#             batch_size=10   # 🔥 ensure continuous batching
#         )
#     )
#     return {"message": "🚀 Continuous transfer loop started."}


# @app.post("/stop")
# async def stop_loop():
#     """
#     Stop continuous transfers cleanly.
#     """
#     global stop_event, loop_task

#     if not loop_task or not stop_event:
#         return {"message": "ℹ️ No active transfer loop."}

#     stop_event.set()
#     await loop_task
#     return {"message": "🛑 Transfer loop stopped."}


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)



















# from fastapi import FastAPI, Request, BackgroundTasks
# from fastapi.responses import HTMLResponse, JSONResponse
# from fastapi.templating import Jinja2Templates
# from fastapi.staticfiles import StaticFiles
# from .pi_worker import process_all_seeds, loop_process_forever
# from app.routes import router

# import asyncio
# from pydantic import BaseModel
# from typing import List

# class TransferRequest(BaseModel):
#     owner: str
#     amount: float
#     seeds: List[str]

# app = FastAPI()
# app.include_router(router)
# templates = Jinja2Templates(directory="app/templates")

# @app.get("/", response_class=HTMLResponse)
# async def form_ui(request: Request):
#     return templates.TemplateResponse("index.html", {"request": request})

# @app.post("/api/transfer")
# async def transfer(data: TransferRequest):
#     try:
#         results = await process_all_seeds(data.seeds, data.owner, data.amount)
#         return JSONResponse(content={"results": results})
#     except Exception as e:
#         return JSONResponse(
#             status_code=500,
#             content={"error": f"Internal Server Error: {str(e)}"}
#         )


# # ✅ Background control
# loop_task: asyncio.Task | None = None
# stop_event: asyncio.Event | None = None

# @app.post("/start")
# async def start_loop(data: TransferRequest):
#     global loop_task, stop_event
#     if loop_task and not loop_task.done():
#         return {"message": "Transfer already running."}

#     stop_event = asyncio.Event()
#     loop_task = asyncio.create_task(loop_process_forever(data.seeds, data.owner, data.amount, stop_event))
#     return {"message": "Continuous transfer started."}

# @app.post("/stop")
# async def stop_loop():
#     global stop_event, loop_task
#     if stop_event:
#         stop_event.set()
#     if loop_task:
#         await loop_task
#     return {"message": "Transfer stopped."}


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)



# from fastapi import FastAPI, Request, BackgroundTasks
# from fastapi.responses import HTMLResponse, JSONResponse
# from fastapi.staticfiles import StaticFiles
# from fastapi.templating import Jinja2Templates
# from .pi_worker import process_all_seeds
# from app.routes import router

# import uvicorn
# from pydantic import BaseModel
# from typing import List

# class TransferRequest(BaseModel):
#     owner: str
#     amount: float
#     seeds: List[str]

# app = FastAPI()
# app.include_router(router)
# # app.mount("/static", StaticFiles(directory="app/templates"), name="static")
# templates = Jinja2Templates(directory="app/templates")

# @app.get("/", response_class=HTMLResponse)
# async def form_ui(request: Request):
#     return templates.TemplateResponse("index.html", {"request": request})

# @app.post("/api/transfer")
# async def transfer(data: TransferRequest):
#     try:
#         results = await process_all_seeds(data.seeds, data.owner, data.amount)
#         return JSONResponse(content={"results": results})
#     except Exception as e:
#         return JSONResponse(
#             status_code=500,
#             content={"error": f"Internal Server Error: {str(e)}"}
#         )

# if __name__ == "__main__":
#     uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
