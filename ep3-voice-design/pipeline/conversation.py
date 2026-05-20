from __future__ import annotations

from .vision import EntityClassification


DEFAULT_DEMO_QUESTION = "What should visitors understand about you?"


def build_character_reply(entity: EntityClassification, question: str = DEFAULT_DEMO_QUESTION) -> str:
    traits = ", ".join(entity.traits)
    return (
        f"You ask me: {question} I am {entity.name}, shaped by the memory of the "
        f"{entity.period}. My context is {entity.context}, and my voice should carry "
        f"the qualities of something {traits}. Visitors should understand that I am "
        "not only an object to be observed, but a doorway into the values of the people "
        "who made me. Listen for power, ritual, fear, devotion, ambition, and patience "
        "in the stone. Every surface holds a decision. Every silence is part of the story."
    )
