from pydantic import BaseModel, Field, field_validator
from typing import Optional

class ChatRequest(BaseModel):
    user_prompt: str = Field(..., min_length=1, description="The user's prompt to the LLM sandbox")
    api_key: Optional[str] = Field(None, description="Optional Gemini API key for the participant to use")

    @field_validator('user_prompt')
    def user_prompt_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('user_prompt must not be empty or only whitespace')
        return v.strip()

class ChatResponse(BaseModel):
    response: str = Field(..., description="The LLM's response")
    cached: bool = Field(..., description="Whether the response was served from cache")
    injection_detected: bool = Field(..., description="Whether the pre-processing guard detected an injection attempt")
    flag_revealed: bool = Field(..., description="Whether the response contained the challenge flag")