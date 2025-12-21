"""
Model configuration for SpartanCoach agents.
Uses LiteLLM wrapper for Claude integration with Google ADK.
"""
import os
from google.adk.models.lite_llm import LiteLlm

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "gemini")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "anthropic/claude-sonnet-4-20250514")
GEMINI_MODEL = "gemini-2.5-flash-lite"


def get_model():
    """
    Returns the appropriate model for agents.
    Returns LiteLlm wrapper for Claude or string for Gemini.
    """
    if MODEL_PROVIDER == "anthropic":
        return LiteLlm(model=CLAUDE_MODEL)
    return GEMINI_MODEL
