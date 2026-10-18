import logging
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

from app.webhook import router

app = FastAPI(title="Living High Chatbot")
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
