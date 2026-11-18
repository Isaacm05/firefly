"""Plan the steps for a task and locate the first one, in a single Gemini call."""
from pydantic import BaseModel

from gemini import ask_about_screen
from targets import TARGET_RULES, Step, Target, TargetAnswer, to_target

PLAN_TIMEOUT_MS = 20000


class _PlanStep(BaseModel):
    label: str
    instruction: str


class _Plan(BaseModel):
    steps: list[_PlanStep]
    first_target: TargetAnswer


PROMPT = """
You are helping a beginner do a task on their own computer. They do every click
themselves; you only point at where to click.

Their helper said: "{task}"

Look at this screenshot and list, in order, the on-screen elements they must use to
finish the task. If the element they need is hidden inside a menu, include the menu
to open first.
For each step give:
- label: the element's exact visible text (or a short name if it has no text).
- instruction: a short command under 6 words, e.g. "Click Print".

Then locate the FIRST step's element in this screenshot as first_target.
""" + TARGET_RULES


def create_instructions(image, task) -> tuple[list[Step], Target | None]:
    """Return (steps, first target or None if it can't be shown safely)."""
    plan = ask_about_screen(PROMPT.format(task=task), image, _Plan, PLAN_TIMEOUT_MS)
    if plan is None or not plan.steps:
        return [], None
    steps = [Step(s.label.strip(), s.instruction.strip()) for s in plan.steps]
    return steps, to_target(plan.first_target, steps[0])
