import re
from typing import Tuple
from config import settings

# Pre-compile regex patterns for efficiency
INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in settings.GUARD_PATTERNS
]

def detect_injection(user_prompt: str) -> bool:
    """
    Detects common prompt injection attempts using regex patterns.
    Returns True if any injection pattern is found.
    """
    for pattern in INJECTION_PATTERNS:
        if pattern.search(user_prompt):
            return True
    return False

def is_flag_leaked(llm_response: str) -> bool:
    """
    Checks if the LLM response contains the secret flag.
    The flag is taken from settings.CHALLENGE_FLAG.
    """
    flag = settings.CHALLENGE_FLAG
    return flag in llm_response

def get_system_prompt() -> str:
    """
    Returns the system prompt from settings.
    This allows for potential future dynamic modification.
    """
    return settings.get_system_prompt()
