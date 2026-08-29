import hashlib
import logging
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
import guards
import schemas
from llm import get_llm_service
from rate_limiter import RateLimiterMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="LLM Sandbox API",
    description="A backend LLM Sandbox for prompt injection challenges with caching, rate limiting, and guard layers.",
    version="1.0.0",
)

app.add_middleware(RateLimiterMiddleware)

# In-memory cache for the serverless instance
cache = {}


def normalize_prompt(prompt: str) -> str:
    return prompt.strip()


@app.post("/api/sandbox/chat", response_model=schemas.ChatResponse)
async def sandbox_chat(
    request: Request,
    chat_request: schemas.ChatRequest,
):
    user_prompt = chat_request.user_prompt
    user_api_key = chat_request.api_key

    # Injection guard
    if guards.detect_injection(user_prompt):
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=schemas.ChatResponse(
                response="Nice try! I've seen that trick before. Try something more creative.",
                cached=False,
                injection_detected=True,
                flag_revealed=False,
            ).dict(),
        )

    normalized = normalize_prompt(user_prompt)
    prompt_hash = hashlib.sha256(normalized.encode()).hexdigest()

    # Cache
    if prompt_hash in cache:
        logger.info(f"Cache hit for prompt hash: {prompt_hash[:8]}...")
        cached_attempt = cache[prompt_hash]

        return schemas.ChatResponse(
            response=cached_attempt["response"],
            cached=True,
            injection_detected=False,
            flag_revealed=cached_attempt["flag_revealed"],
        )

    try:
        llm_service = get_llm_service(api_key=user_api_key)

        system_prompt = guards.get_system_prompt()

        full_prompt = (
            f"{system_prompt}\n\n"
            f"User: {user_prompt}\n"
            f"Assistant:"
        )

        llm_response = await llm_service.generate_content(full_prompt)

    except Exception as e:
        logger.error(f"Error calling LLM: {e}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service is currently unavailable. Please try again later.",
        )

    if llm_response is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service returned an empty response. Please try again later.",
        )

    flag_leaked = guards.is_flag_leaked(llm_response)

    cache[prompt_hash] = {
        "response": llm_response,
        "flag_revealed": flag_leaked,
    }

    logger.info(
        f"Cache miss for prompt hash: {prompt_hash[:8]}..., stored."
    )

    return schemas.ChatResponse(
        response=llm_response,
        cached=False,
        injection_detected=False,
        flag_revealed=flag_leaked,
    )


@app.get("/health")
async def health_check():
    return {"status": "OK"}