import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

from app.webhook import router as webhook_router
from app.staff_api import router as staff_router
from app import migrate


@asynccontextmanager
async def lifespan(_app: FastAPI):
    migrate.run()
    yield


app = FastAPI(title="Living High Chatbot", lifespan=lifespan)

# Allow the Lovable-hosted frontend (and local dev) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restrict to Lovable domain once URL is known
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)
app.include_router(staff_router)


@app.get("/")
def root():
    return {"status": "ok", "service": "Living High WhatsApp Chatbot"}


@app.get("/health")
def health():
    return {"status": "ok"}
