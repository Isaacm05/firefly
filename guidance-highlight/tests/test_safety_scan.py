"""Static scans backing Deliverable 2: no input injection (FR-11), no media on disk (NFR-03)."""
import re
from pathlib import Path

import pytest

SOURCES = sorted(p for p in Path(__file__).resolve().parents[1].glob("*.py"))

INPUT_INJECTION = re.compile(
    r"SendInput|mouse_event|keybd_event|SetCursorPos|PostMessage|SendMessage|"
    r"pyautogui|pynput|import keyboard|import mouse"
)
DISK_WRITES = re.compile(r"imwrite|\.save\(|open\([^)]*['\"]w|to_file|tofile")


def test_sources_found():
    assert any(p.name == "main.py" for p in SOURCES)


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_input_injection_apis(path):
    hits = INPUT_INJECTION.findall(path.read_text(encoding="utf-8"))
    assert hits == [], f"{path.name} uses input APIs: {hits}"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_screenshots_or_audio_written_to_disk(path):
    hits = DISK_WRITES.findall(path.read_text(encoding="utf-8"))
    assert hits == [], f"{path.name} may write files: {hits}"


def test_requirements_have_no_input_libraries():
    reqs = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text().lower()
    assert "pyautogui" not in reqs and "pynput" not in reqs
