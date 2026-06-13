import time
import os
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from src.cache.semantic_cache import SemanticCache

app = FastAPI(title="Low-Latency Voice Agent Backend")
cache = SemanticCache(threshold=0.90)

@app.post("/vapi/custom-llm")
async def handle_vapi_request(request: Request):
    start_time = time.time()
    
    # 1. Safely parse Vapi's nested webhook structural packet
    try:
        body = await request.json()
        print(f"[VAPI RECEIVE] Payload payload detected: {body}")
        
        # Pull text from Vapi's message array or raw transcripts
        messages = body.get("message", {}).get("messages", [])
        if messages:
            user_query = messages[-1].get("content", "")
        else:
            user_query = body.get("message", {}).get("transcript", "")
            
        if not user_query:
            user_query = "Hello"
    except Exception as e:
        print(f"[PARSING ERROR] Failed to parse payload: {e}")
        user_query = "Hello"

    print(f"[USER SAYS]: {user_query}")

    # 2. Vector Cache Check
    cached_response = cache.check_cache(user_query)
    if cached_response:
        latency = (time.time() - start_time) * 1000
        print(f"[CACHE HIT] Served in {latency:.2f} ms")
        # Format the return data EXACTLY how Vapi's Custom LLM engine expects it
        return JSONResponse(content={
            "choices": [{"message": {"role": "assistant", "content": cached_response}}]
        })

    # 3. Cache Miss Loop -> Generate dynamic response 
    # (In production, this segment executes a quick call to Gemini 2.0 Flash)
    ai_generated_response = f"We are open from 9 AM to 6 PM on weekends. I have processed your request regarding: {user_query}."
    
    # Save pattern to cache for future lookups
    cache.add_to_cache(user_query, ai_generated_response)
    
    latency = (time.time() - start_time) * 1000
    print(f"[CACHE MISS] AI generated answer. Latency: {latency:.2f} ms")
    
    # Return standard LLM choice block mapping
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
