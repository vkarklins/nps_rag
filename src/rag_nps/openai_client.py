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


def model_options(model, effort):
    """Extra keyword arguments for a Responses API call to `model` at reasoning `effort`.

    GPT-6 models are reasoning models: they take a reasoning effort, and accept
    temperature only when that effort is "none". Older models (gpt-4o-mini) reject the
    reasoning parameter. Temperature 0 is sent whenever the model accepts it, so repeated
    calls give answers as close to identical as possible.
    """
    if not model.startswith("gpt-6"):
        return {"temperature": 0}
    options = {"reasoning": {"effort": effort}}
    if effort == "none":
        options["temperature"] = 0
    return options
