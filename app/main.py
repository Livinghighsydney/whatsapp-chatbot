import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

from app import migrate
from app.routes.webhook import router as webhook_router
from app.routes.staff import router as staff_router
from app.routes.internal import router as internal_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate.run()
    yield


app = FastAPI(title="Living High Chatbot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)
app.include_router(staff_router)
app.include_router(internal_router)


@app.get("/")
def root():
    return {"status": "ok", "service": "Living High WhatsApp Chatbot"}


@app.get("/health")
def health():
    return {"status": "ok"}
