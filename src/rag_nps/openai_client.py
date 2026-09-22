"""
Shared OpenAI client: the one place that reads the API key and builds the client, so
every part of the app (embeddings, chat) talks to OpenAI through the exact same setup.

Usage:
    from rag_nps.openai_client import client
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
API_KEY = os.getenv("OPENAI_API_KEY")

# The SDK retries rate-limit (429) and transient server errors with backoff; its default is
# 2 retries, which is thin for a job that makes many requests back to back.
client = OpenAI(api_key=API_KEY, max_retries=5)
