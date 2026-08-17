"""
LLM Module - Adapter for backend.common.llm to voice-chat usage.

Wraps common.llm functions and injects voice-chat config automatically.

[VOICE-CHAT SPECIFIC]
- init_llm() injects engine and base_url from config
- get_chat_stream() injects model and config values
"""

from backend import config
from backend.common import llm as common_llm


def init_llm():
    """[VOICE-CHAT SPECIFIC] Initialize LLM with voice-chat config."""
    common_llm.init_llm(
        engine=config.ENGINE,
        base_url=config.BASE_URL,
        api_key="local-endpoint"
    )


async def get_chat_stream(history_messages: list):
    """
    [VOICE-CHAT SPECIFIC] Get chat stream with voice-chat config.
    
    Automatically injects voice-chat MODEL, ENGINE, and BASE_URL.
    """
    return await common_llm.get_chat_stream(
        history_messages=history_messages,
        model=config.MODEL,
        engine=config.ENGINE,
        base_url=config.BASE_URL,
        temperature=0.7,
        num_predict=150
    )


__all__ = ["init_llm", "get_chat_stream"]
