import time
import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from src.cache.semantic_cache import SemanticCache

# 1. Setup proper logging to catch silent errors
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Bulletproof Voice Agent Backend")

# 2. Add CORS Middleware to ensure Vapi is never blocked for security reasons
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cache = SemanticCache(threshold=0.90)

@app.post("/vapi/custom-llm")
async def handle_vapi_request(request: Request):
    start_time = time.time()
    user_query = "Hello" # Failsafe default
    
    # 3. ULTRA-RESILIENT PARSING: Search everywhere for the user's text without crashing
    try:
        body = await request.json()
        
        # Check standard root messages array OR nested Vapi message array
        messages = body.get("messages") or body.get("message", {}).get("messages", [])
        
        if messages and isinstance(messages, list):
            # Scan backward to find the most recent thing the human said
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_query = msg.get("content", "Hello")
                    break
        else:
            # Fallback for raw transcript payloads
            transcript = body.get("message", {}).get("transcript")
            if transcript:
                user_query = transcript
                
    except Exception as e:
        logger.error(f"[PARSING ERROR] Ignored: {e}")

    logger.info(f"[USER SAYS]: {user_query}")

    # 4. SAFE CACHE CHECK
    try:
        cached_response = cache.check_cache(user_query)
        if cached_response:
            latency = (time.time() - start_time) * 1000
            logger.info(f"[CACHE HIT] {latency:.2f} ms")
            return JSONResponse(
                status_code=200, # ALWAYS return 200 so Vapi doesn't drop the call
                content={"choices": [{"message": {"role": "assistant", "content": cached_response}}]}
            )
    except Exception as e:
        logger.error(f"[CACHE ERROR] Skipped: {e}")

    # 5. SAFE GEMINI CALL (Inside the route, so it never crashes the server on boot)
    ai_generated_response = "I'm sorry, I am experiencing a brief network hiccup. Could you repeat that for me?"
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing from the Render environment")
            
        ai_client = genai.Client(api_key=api_key)
        response = ai_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=user_query,
            config=types.GenerateContentConfig(
                system_instruction="You are a helpful, voice-optimized customer support agent. Keep answers concise (1-2 sentences max).",
                max_output_tokens=150,
                temperature=0.7,
            )
        )
        
        if response and response.text:
            ai_generated_response = response.text
            
            # Only attempt to save to cache if Gemini successfully answered
            try:
                cache.add_to_cache(user_query, ai_generated_response)
            except Exception as ce:
                logger.error(f"[CACHE SAVE ERROR] Skipped: {ce}")

    except Exception as e:
        logger.error(f"[API ERROR] Gemini Call Failed: {e}")

    latency = (time.time() - start_time) * 1000
    logger.info(f"[PIPELINE COMPLETE] Latency: {latency:.2f} ms")
    
    # 6. GUARANTEED FALLBACK RETURN (Prevents providerfault entirely)
    return JSONResponse(
        status_code=200,
        content={"choices": [{"message": {"role": "assistant", "content": ai_generated_response}}]}
    )
