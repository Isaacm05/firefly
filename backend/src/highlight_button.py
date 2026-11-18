"""Locate one step's element on a fresh screenshot and return it as a bounding box."""
import logging

from gemini import ask_about_screen
from targets import TARGET_RULES, Step, Target, TargetAnswer, to_target

LOCATE_TIMEOUT_MS = 10000  # FR-09: no answer within 10 s -> no highlight
log = logging.getLogger(__name__)

PROMPT = """
Look at this screenshot. A beginner's next step is: "{instruction}".
Find the element labelled "{label}".
""" + TARGET_RULES


def locate_button(image, step: Step) -> Target | None:
    """Return the target box, or None on timeout / bad answer / low confidence (FR-09)."""
    try:
        answer = ask_about_screen(
            PROMPT.format(instruction=step.instruction, label=step.label),
            image, TargetAnswer, LOCATE_TIMEOUT_MS,
        )
    except Exception as e:  # timeouts and API errors fail safe: no highlight
        log.warning("[locate_button] %s", e)
        return None
    return to_target(answer, step)
