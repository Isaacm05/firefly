"""Manual smoke test: run the real Gemini plan + locate calls on a screenshot file.

Dev only, never deployed. Needs GEMINI_API_KEY in backend/.env.

    python scripts/try_gemini.py path/to/screenshot.png "click print, then OK"
"""
import logging
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.path.insert(0, str(SRC))
    from create_instructions import create_instructions
    from highlight_button import locate_button

    path, task = Path(sys.argv[1]), sys.argv[2]
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    image = path.read_bytes()
    steps, target = create_instructions(image, task)
    print("\nsteps:", steps)
    print("first target:", target)
    for step in steps[1:]:
        print(f"locate {step.label!r}:", locate_button(image, step))


if __name__ == "__main__":
    main()
