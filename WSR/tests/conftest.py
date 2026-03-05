"""
Shared pytest fixtures for WSR Flask app tests.
"""

import io
import pytest
import numpy as np
from PIL import Image


@pytest.fixture
def app():
    """Create the Flask app in testing mode."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    from app import app as flask_app
    flask_app.config['TESTING'] = True
    flask_app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    return flask_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


def make_png_bytes(width=50, height=50, mode='RGBA', color=(255, 0, 0, 255)):
    """Helper to create a minimal PNG image as bytes."""
    img = Image.new(mode, (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.read()


def make_png_with_white_bg(width=100, height=100):
    """Create a PNG with white background and a red circle in the center."""
    img = Image.new('RGBA', (width, height), (255, 255, 255, 255))
    pixels = img.load()
    cx, cy, r = width // 2, height // 2, min(width, height) // 4
    for x in range(width):
        for y in range(height):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r ** 2:
                pixels[x, y] = (200, 50, 50, 255)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.read()


@pytest.fixture
def small_png():
    """A small solid-color PNG for basic upload tests."""
    return make_png_bytes()


@pytest.fixture
def logo_png():
    """A PNG with white background and a colored shape."""
    return make_png_with_white_bg()
