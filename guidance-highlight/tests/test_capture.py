"""Screen capture and encoding: right shape, in memory only (NFR-03)."""
import os

import numpy as np
import pytest

from encode_for_api import encode_for_api
from take_screenshot import _primary, take_screenshot


def test_primary_monitor_is_the_one_at_origin():
    monitors = [
        {"left": -1920, "top": 0, "width": 3840, "height": 1080},  # [0] = all screens
        {"left": -1920, "top": 0, "width": 1920, "height": 1080},
        {"left": 0, "top": 0, "width": 1920, "height": 1080},
    ]
    assert _primary(monitors) is monitors[2]


def test_primary_falls_back_to_first_monitor():
    monitors = [{"left": 5, "top": 5}, {"left": 5, "top": 5}]
    assert _primary(monitors) is monitors[1]


def test_screenshot_is_bgr_array():
    img = take_screenshot()
    assert img.ndim == 3 and img.shape[2] == 3
    assert img.dtype == np.uint8
    assert img.flags["C_CONTIGUOUS"]


def test_screenshot_and_encoding_write_nothing_to_disk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    encode_for_api(take_screenshot())
    assert os.listdir(tmp_path) == []


def test_encode_downscales_wide_images():
    import cv2
    img = np.full((1000, 4000, 3), 128, dtype=np.uint8)
    data = encode_for_api(img, max_width=1280)
    decoded = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape[:2] == (320, 1280)


def test_encode_keeps_small_images_and_returns_jpeg():
    img = np.zeros((100, 200, 3), dtype=np.uint8)
    data = encode_for_api(img)
    assert data[:2] == b"\xff\xd8"  # JPEG magic number
