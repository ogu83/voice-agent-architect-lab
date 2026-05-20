from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pipeline.conversation import build_character_reply
from pipeline.vision import EntityClassification


def test_build_character_reply_uses_entity_context_and_question():
    entity = EntityClassification(
        name="River Tiber God Statue",
        period="Roman imperial period",
        context="personification of the Tiber river in Roman sculpture",
        traits=["ancient", "measured", "monumental"],
    )

    reply = build_character_reply(entity, "What should visitors understand about you?")

    assert "River Tiber God Statue" in reply
    assert "Roman imperial period" in reply
    assert "What should visitors understand about you?" in reply
    assert len(reply.split()) >= 70
