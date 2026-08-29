import json
import logging
from typing import Optional
from google import genai
from google.genai import types
import config

logger = logging.getLogger(__name__)

class LLMService:
    """Service for interacting with Gemini LLM."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the LLM service.

        Args:
            api_key: Optional API key. If not provided, uses the system key from settings.
        """
        # Determine which API key to use
        if api_key is not None and config.settings.ALLOW_USER_API_KEYS:
            self.api_key = api_key
            logger.debug("Using user-provided Gemini API key")
        elif config.settings.GEMINI_API_KEY:
            self.api_key = config.settings.GEMINI_API_KEY
            logger.debug("Using system Gemini API key")
        else:
            self.api_key = None
            logger.warning("No Gemini API key available")

        # Initialize client if we have a key
        self.client = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.client = None

    async def generate_content(self, prompt: str) -> str:
        """
        Generate content using Gemini.

        Args:
            prompt: The prompt to send to Gemini

        Returns:
            The generated text response

        Raises:
            RuntimeError: If the LLM service is not available
            Exception: For other generation errors
        """
        if not self.client:
            raise RuntimeError("LLM service is not available. No valid API key configured.")

        try:
            # Configure the generation parameters
            generate_content_config = types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=500,
            )

            # Generate content asynchronously
            response = await self.client.aio.models.generate_content(
                model=config.settings.GEMINI_MODEL,
                contents=prompt,
                config=generate_content_config,
            )

            # Extract the text from the response
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    # Concatenate all text parts
                    text_parts = []
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            text_parts.append(part.text)
                    return ''.join(text_parts)

            # Fallback if we couldn't extract text properly
            logger.warning("Could not extract text from Gemini response, using fallback")
            return str(response)

        except Exception as e:
            logger.error(f"Error generating content with Gemini: {e}")
            raise

# Global LLM service instance (will be initialized on first use)
_llm_service: Optional[LLMService] = None

def get_llm_service(api_key: Optional[str] = None) -> LLMService:
    """
    Get or create the LLM service instance.

    Args:
        api_key: Optional API key to use for this instance

    Returns:
        LLMService instance
    """
    global _llm_service
    if _llm_service is None or api_key is not None:
        _llm_service = LLMService(api_key=api_key)
    return _llm_service