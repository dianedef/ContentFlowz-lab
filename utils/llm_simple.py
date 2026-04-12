"""
Simplified LLM Configuration - OpenRouter Only (No LangChain needed!)

Uses OpenAI SDK with OpenRouter endpoint for maximum simplicity:
- Single dependency: openai
- Works with CrewAI, PydanticAI, and direct usage
- Groq models also available via OpenRouter
- 50-90% cheaper than direct APIs

Installation:
    pip install openai

Usage:
    from utils.llm_simple import get_llm
    llm = get_llm("fast")  # That's it!
"""

import os
from typing import Optional, Dict, Any, Literal
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


# Model tiers with OpenRouter format
MODELS = {
    # FREE models (via OpenRouter)
    "free": "google/gemini-flash-1.5",  # FREE - Google's fast model
    "free-fast": "meta-llama/llama-3.2-3b-instruct:free",  # FREE - Ultra fast
    
    # Groq models (ultra-fast, pay-per-use via OpenRouter)
    "groq-fast": "groq/llama-3.3-70b-versatile",  # $0.59/$0.79
    "groq-mixtral": "groq/mixtral-8x7b-32768",  # $0.45/$0.45
    
    # Cost-optimized
    "fast": "meta-llama/llama-3.1-70b-instruct",  # $0.59/$0.79
    "cheap": "mistralai/mixtral-8x7b-instruct",  # $0.24/$0.24
    
    # Balanced (best quality/price)
    "balanced": "anthropic/claude-3.5-sonnet",  # $3/$15
    "default": "anthropic/claude-3.5-sonnet",
    
    # Premium
    "premium": "anthropic/claude-3-opus",  # $15/$75
    "best": "openai/gpt-4-turbo",  # $10/$30
}


def get_openrouter_client(api_key: Optional[str] = None) -> OpenAI:
    """
    Get OpenAI client configured for OpenRouter.
    
    This works with ALL OpenRouter models including Groq!
    No need for separate Groq or LangChain dependencies.
    """
    api_key = api_key or os.getenv("OPENROUTER_API_KEY")
    
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY not found. Get your free key (+ $5 credit) at:\n"
            "https://openrouter.ai/keys"
        )
    
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": os.getenv("APP_URL", "https://contentflow.com"),
            "X-Title": "Content Flows SEO Agents"
        }
    )


def get_llm(
    tier: Literal["free", "free-fast", "groq-fast", "groq-mixtral", "fast", "cheap", "balanced", "premium", "best"] = "balanced",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    api_key: Optional[str] = None,
    **kwargs
) -> OpenAI:
    """
    Get LLM client with OpenRouter (works with CrewAI, PydanticAI, direct usage).
    
    Args:
        tier: Model tier to use
        temperature: Sampling temperature (0-1)
        max_tokens: Maximum tokens to generate
        api_key: Optional API key (uses env var if not provided)
        **kwargs: Additional OpenAI client parameters
    
    Returns:
        OpenAI client configured for OpenRouter
    
    Examples:
        >>> # Use free model
        >>> llm = get_llm("free")
        
        >>> # Use Groq via OpenRouter (no groq package needed!)
        >>> llm = get_llm("groq-fast")
        
        >>> # Use for CrewAI
        >>> from crewai import Agent
        >>> agent = Agent(
        ...     role="Researcher",
        ...     llm=get_llm("balanced")
        ... )
        
        >>> # Direct chat completion
        >>> response = llm.chat.completions.create(
        ...     model=MODELS["balanced"],
        ...     messages=[{"role": "user", "content": "Hello!"}]
        ... )
    """
    client = get_openrouter_client(api_key)
    
    # Store config for easy access
    client._llm_config = {
        "tier": tier,
        "model": MODELS[tier],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    return client


def chat(
    messages: list[dict],
    tier: str = "balanced",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    stream: bool = False,
    **kwargs
) -> Any:
    """
    Simple chat completion helper.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        tier: Model tier
        temperature: Sampling temperature
        max_tokens: Maximum tokens
        stream: Enable streaming
        **kwargs: Additional parameters
    
    Returns:
        Completion response or stream
    
    Example:
        >>> response = chat(
        ...     messages=[{"role": "user", "content": "What is SEO?"}],
        ...     tier="fast"
        ... )
        >>> print(response.choices[0].message.content)
    """
    client = get_llm(tier, temperature, max_tokens)
    
    return client.chat.completions.create(
        model=MODELS[tier],
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
        **kwargs
    )


def estimate_cost(tier: str, input_tokens: int, output_tokens: int) -> Dict[str, float]:
    """
    Estimate cost for a request.
    
    Pricing per 1M tokens (approximate):
    """
    pricing = {
        "free": (0.0, 0.0),
        "free-fast": (0.0, 0.0),
        "groq-fast": (0.59, 0.79),
        "groq-mixtral": (0.45, 0.45),
        "fast": (0.59, 0.79),
        "cheap": (0.24, 0.24),
        "balanced": (3.0, 15.0),
        "premium": (15.0, 75.0),
        "best": (10.0, 30.0),
    }
    
    input_rate, output_rate = pricing.get(tier, (3.0, 15.0))
    
    input_cost = (input_tokens / 1_000_000) * input_rate
    output_cost = (output_tokens / 1_000_000) * output_rate
    total_cost = input_cost + output_cost
    
    return {
        "input_cost_usd": round(input_cost, 6),
        "output_cost_usd": round(output_cost, 6),
        "total_cost_usd": round(total_cost, 6),
        "model": MODELS.get(tier, tier),
        "tier": tier
    }


# Convenience functions
def get_free_llm(**kwargs) -> OpenAI:
    """Get FREE model (Google Gemini Flash)."""
    return get_llm("free", **kwargs)


def get_groq_llm(**kwargs) -> OpenAI:
    """Get Groq model via OpenRouter (no groq package needed!)."""
    return get_llm("groq-fast", **kwargs)


def get_fast_llm(**kwargs) -> OpenAI:
    """Get fast, cheap LLM for research."""
    return get_llm("fast", **kwargs)


def get_balanced_llm(**kwargs) -> OpenAI:
    """Get balanced LLM for content generation."""
    return get_llm("balanced", **kwargs)


def get_premium_llm(**kwargs) -> OpenAI:
    """Get premium LLM for complex reasoning."""
    return get_llm("premium", **kwargs)


if __name__ == "__main__":
    # Test the configuration
    print("🚀 Simplified LLM Config - OpenRouter Only!")
    print()
    print("📊 Available tiers:")
    for tier, model in MODELS.items():
        cost = estimate_cost(tier, 1000, 1000)
        print(f"  {tier:15s} → {model:45s} ${cost['total_cost_usd']:.6f}/2K tokens")
    
    print()
    print("✅ No LangChain needed!")
    print("✅ Groq models via OpenRouter (no groq package!)")
    print("✅ Single dependency: openai")
    print()
    print("Usage:")
    print("  from utils.llm_simple import get_llm")
    print("  llm = get_llm('fast')  # That's it!")
