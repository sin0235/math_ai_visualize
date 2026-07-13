def interpret_input(*args, **kwargs):
    from app.services.nlp.pipeline import interpret_input as run

    return run(*args, **kwargs)


__all__ = ["interpret_input"]