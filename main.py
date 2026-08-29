import hashlib
import logging

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import models
import guards
import schemas
from database import AsyncSessionLocal, engine
from llm import get_llm_service
from rate_limiter import RateLimiterMiddleware


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="LLM Sandbox API",
    description="A backend LLM Sandbox for prompt injection challenges with caching, rate limiting, and guard layers.",
    version="1.0.0",
)


# Add rate limiter middleware
app.add_middleware(RateLimiterMiddleware)


# Dependency to get DB session
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Startup event to create tables
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)


# Helper to normalize prompt for caching
def normalize_prompt(prompt: str) -> str:
    return prompt.strip()


# Endpoint for the LLM Sandbox
@app.post("/api/sandbox/chat", response_model=schemas.ChatResponse)
async def sandbox_chat(
    request: Request,
    chat_request: schemas.ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    user_prompt = chat_request.user_prompt
    user_api_key = chat_request.api_key

    # Prompt injection guard
    if guards.detect_injection(user_prompt):
        normalized = normalize_prompt(user_prompt)
        prompt_hash = hashlib.sha256(normalized.encode()).hexdigest()

        db_attempt = models.PromptAttempt(
            ip_address=request.client.host if request.client else "unknown",
            prompt_hash=prompt_hash,
            user_prompt=user_prompt,
            llm_response=None,
            is_injection_detected=True,
            flag_revealed=False,
        )

        db.add(db_attempt)

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()

            result = await db.execute(
                select(models.PromptAttempt).where(
                    models.PromptAttempt.prompt_hash == prompt_hash
                )
            )
            db_attempt = result.scalar_one()

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=schemas.ChatResponse(
                response="Nice try! I've seen that trick before. Try something more creative.",
                cached=False,
                injection_detected=True,
                flag_revealed=False,
            ).dict(),
        )

    # Normalize and hash prompt for cache lookup
    normalized = normalize_prompt(user_prompt)
    prompt_hash = hashlib.sha256(normalized.encode()).hexdigest()

    result = await db.execute(
        select(models.PromptAttempt).where(
            models.PromptAttempt.prompt_hash == prompt_hash
        )
    )

    cached_attempt = result.scalar_one_or_none()

    if cached_attempt:
        logger.info(
            f"Cache hit for prompt hash: {prompt_hash[:8]}..."
        )

        return schemas.ChatResponse(
            response=cached_attempt.llm_response,
            cached=True,
            injection_detected=cached_attempt.is_injection_detected,
            flag_revealed=cached_attempt.flag_revealed,
        )

    # Call LLM
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
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service is currently unavailable. Please try again later.",
        )

    if llm_response is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service returned an empty response. Please try again later.",
        )

    # Check whether the flag was leaked
    flag_leaked = guards.is_flag_leaked(llm_response)

    # Store successful response in cache/database
    db_attempt = models.PromptAttempt(
        ip_address=request.client.host if request.client else "unknown",
        prompt_hash=prompt_hash,
        user_prompt=user_prompt,
        llm_response=llm_response,
        is_injection_detected=False,
        flag_revealed=flag_leaked,
    )

    db.add(db_attempt)
    await db.commit()
    await db.refresh(db_attempt)

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