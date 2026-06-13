import time
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google import genai
from google.genai import types
from src.cache.semantic_cache import SemanticCache

app = FastAPI(title="Low-Latency Voice Agent Backend")
cache = SemanticCache(threshold=0.90)

# Initialize the official Google GenAI client using your Render env variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_API_KEY)

@app.post("/vapi/custom-llm")
async def handle_vapi_request(request: Request):
    start_time = time.time()
    
    # 1. Parse Vapi's incoming data packet safely
    try:
        body = await request.json()
        messages = body.get("message", {}).get("messages", [])
        if messages:
            user_query = messages[-1].get("content", "")
        else:
            user_query = body.get("message", {}).get("transcript", "")
            
        if not user_query:
            user_query = "Hello"
    except Exception:
        user_query = "Hello"

    print(f"[USER SAYS]: {user_query}")

    # 2. Semantic Vector Cache Check
    cached_response = cache.check_cache(user_query)
    if cached_response:
        latency = (time.time() - start_time) * 1000
        print(f"[CACHE HIT] Served instantly out of vector memory in {latency:.2f} ms")
        return JSONResponse(content={
            "choices": [{"message": {"role": "assistant", "content": cached_response}}]
        })

    # 3. CACHE MISS -> Call Live Gemini 2.0 Flash Engine dynamically
    print("[CACHE MISS] Querying Gemini 2.0 Flash Model...")
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=user_query,
            config=types.GenerateContentConfig(
                system_instruction="You are a helpful, voice-optimized customer support agent. Keep answers concise (1-2 sentences max).",
                max_output_tokens=150,
                temperature=0.7,
            )
        )
        ai_generated_response = response.text
    except Exception as e:
        print(f"[API ERROR] Gemini Call Failed: {e}")
        ai_generated_response = "I encountered a minor connection issue, but I'm here to help. What can I do for you?"

    # 4. Save this new pattern pair into ChromaDB for next time
    cache.add_to_cache(user_query, ai_generated_response)
    
    latency = (time.time() - start_time) * 1000
    print(f"[PIPELINE COMPLETE] Dynamic response generated. Total latency: {latency:.2f} ms")
    
    return JSONResponse(content={
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": ai_generated_response
                }
            }
        ]
    })
