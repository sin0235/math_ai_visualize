"""NLP layer: understand math input → canonical form for mathcore.

- ``interpret_input``: multi-target rule-based interpret (sync, preflight).
- ``resolve_algebra_nlp``: algebra orchestration (LLM primary for natural language).
"""

def interpret_input(*args, **kwargs):
    from app.services.nlp.pipeline import interpret_input as run

    return run(*args, **kwargs)


async def resolve_algebra_nlp(*args, **kwargs):
    from app.services.nlp.algebra_nlp import resolve_algebra_nlp as run

    return await run(*args, **kwargs)


__all__ = ["interpret_input", "resolve_algebra_nlp"]
