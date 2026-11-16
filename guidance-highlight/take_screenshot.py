"""Capture the primary screen into memory. Nothing is written to disk (NFR-03)."""
import mss
import numpy as np

_MSS = getattr(mss, "MSS", None) or mss.mss  # newer mss renamed the class


def _primary(monitors):
    # monitors[0] is the union of all screens; the primary one sits at (0, 0) on Windows.
    for m in monitors[1:]:
        if m["left"] == 0 and m["top"] == 0:
            return m
    return monitors[1]


def take_screenshot():
    """Return the primary screen as a BGR numpy array in physical pixels."""
    with _MSS() as sct:
        shot = sct.grab(_primary(sct.monitors))
    return np.ascontiguousarray(np.asarray(shot)[:, :, :3])  # BGRA -> BGR
