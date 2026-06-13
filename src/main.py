import time
import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.cache.semantic_cache import SemanticCache

app = FastAPI(title="Low-Latency Voice Agent Backend")
# Initialize our semantic vector cache matching at 90% accuracy
cache = SemanticCache(threshold=0.90)

# Securely grab configuration links from the hosting server variables
DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


class VapiMessagePayload(BaseModel):
    text: str


@app.post("/vapi/custom-llm")
async def handle_vapi_request(payload: VapiMessagePayload):
    start_time = time.time()
    user_query = payload.text

    # 1. Look inside our Vector Cache first to try and avoid calling the AI
    cached_response = cache.check_cache(user_query)
    if cached_response:
        latency = (time.time() - start_time) * 1000
        print(f"[CACHE HIT] Served in {latency:.2f} ms")
        return {"response": cached_response, "source": "cache"}

    # 2. If it's a CACHE MISS, simulate generating an AI answer or tool call
    try:
        # In production, this segment triggers a fast call to Gemini 2.0 Flash
        ai_generated_response = f"I have processed your request regarding: '{user_query}'."

        # 3. Simulate calling an external workflow tool like n8n if an appointment is mentioned
        if "book" in user_query.lower() or "appointment" in user_query.lower():
            ai_generated_response = "Perfect, I am sending a booking request right now to our ledger."

        # 4. Save this new dialogue pattern into the cache so the next user gets it instantly
        cache.add_to_cache(user_query, ai_generated_response)

        latency = (time.time() - start_time) * 1000
        print(f"[CACHE MISS] AI generated answer. Latency: {latency:.2f} ms")
        return {"response": ai_generated_response, "source": "gemini_api"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
