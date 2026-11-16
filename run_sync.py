"""Run bulk KB embedding sync locally. Writes to the live Neon DB."""
from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

from app.rag.sync import sync_all

print("Starting bulk sync...")
result = sync_all()
print(f"\nDone: {result}")
