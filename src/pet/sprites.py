"""Generate simple pet sprites programmatically.

Creates a robot-style mascot using Pillow drawing.
All sprites are generated in code -- no external image files needed.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont


# Colors
BODY_COLOR = (30, 144, 255)       # Dodger blue
BODY_DARK = (20, 100, 200)        # Darker blue for shading
EYE_COLOR = (255, 255, 255)       # White
PUPIL_COLOR = (30, 30, 30)        # Near black
MOUTH_COLOR = (255, 255, 255)     # White
ACCENT_COLOR = (0, 200, 255)      # Cyan accent
ANTENNA_COLOR = (100, 180, 255)   # Light blue

SIZE = 80  # Sprite size


def _base_body(draw: ImageDraw.Draw, bounce: int = 0) -> None:
    """Draw the robot body -- rounded rectangle with antenna."""
    y_off = bounce

    # Antenna
    draw.line([(40, 8 + y_off), (40, 18 + y_off)], fill=ANTENNA_COLOR, width=2)
    draw.ellipse([36, 4 + y_off, 44, 12 + y_off], fill=ACCENT_COLOR)

    # Head / body (rounded rect via ellipses + rectangle)
    # Main body
    draw.rounded_rectangle(
        [18, 18 + y_off, 62, 65 + y_off],
        radius=12,
        fill=BODY_COLOR,
        outline=BODY_DARK,
        width=2,
    )

    # Visor area (darker band across eyes)
    draw.rounded_rectangle(
        [22, 28 + y_off, 58, 44 + y_off],
        radius=6,
        fill=(15, 80, 160),
    )

    # Feet
    draw.ellipse([22, 60 + y_off, 35, 72 + y_off], fill=BODY_DARK)
    draw.ellipse([45, 60 + y_off, 58, 72 + y_off], fill=BODY_DARK)


def _eyes(draw: ImageDraw.Draw, state: str = "normal", bounce: int = 0) -> None:
    """Draw eyes based on state."""
    y_off = bounce

    if state == "blink":
        # Closed eyes -- horizontal lines
        draw.line([(27, 36 + y_off), (35, 36 + y_off)], fill=EYE_COLOR, width=2)
        draw.line([(45, 36 + y_off), (53, 36 + y_off)], fill=EYE_COLOR, width=2)
    elif state == "happy":
        # Happy arched eyes
        draw.arc([27, 30 + y_off, 35, 40 + y_off], 200, 340, fill=EYE_COLOR, width=2)
        draw.arc([45, 30 + y_off, 53, 40 + y_off], 200, 340, fill=EYE_COLOR, width=2)
    elif state == "talk":
        # Normal eyes
        draw.ellipse([28, 31 + y_off, 35, 40 + y_off], fill=EYE_COLOR)
        draw.ellipse([45, 31 + y_off, 52, 40 + y_off], fill=EYE_COLOR)
        # Pupils shifted
        draw.ellipse([30, 33 + y_off, 34, 38 + y_off], fill=PUPIL_COLOR)
        draw.ellipse([47, 33 + y_off, 51, 38 + y_off], fill=PUPIL_COLOR)
    elif state == "sleep":
        # Z-Z-Z eyes
        draw.text((28, 30 + y_off), "z", fill=EYE_COLOR)
        draw.text((47, 28 + y_off), "Z", fill=EYE_COLOR)
    else:
        # Normal eyes
        draw.ellipse([28, 31 + y_off, 35, 40 + y_off], fill=EYE_COLOR)
        draw.ellipse([45, 31 + y_off, 52, 40 + y_off], fill=EYE_COLOR)
        # Pupils
        draw.ellipse([30, 34 + y_off, 33, 37 + y_off], fill=PUPIL_COLOR)
        draw.ellipse([48, 34 + y_off, 51, 37 + y_off], fill=PUPIL_COLOR)


def _mouth(draw: ImageDraw.Draw, state: str = "normal", bounce: int = 0) -> None:
    """Draw mouth based on state."""
    y_off = bounce

    if state == "talk":
        # Open mouth
        draw.ellipse([35, 48 + y_off, 45, 56 + y_off], fill=(15, 80, 160), outline=EYE_COLOR, width=1)
    elif state == "happy":
        # Smile
        draw.arc([33, 44 + y_off, 47, 56 + y_off], 10, 170, fill=EYE_COLOR, width=2)
    elif state == "sleep":
        # Flat line
        draw.line([(35, 52 + y_off), (45, 52 + y_off)], fill=EYE_COLOR, width=1)
    else:
        # Slight smile
        draw.arc([34, 46 + y_off, 46, 54 + y_off], 10, 170, fill=EYE_COLOR, width=2)


def create_sprite(state: str = "idle", frame: int = 0) -> Image.Image:
    """Create a single sprite frame.

    States: idle, walk, talk, happy, sleep, blink
    Frame: animation frame number (0-3)
    """
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Bounce for walk animation
    bounce = 0
    if state == "walk":
        bounce = [0, -3, 0, -3][frame % 4]
    elif state == "idle":
        bounce = [0, -1, 0, -1][frame % 4]

    _base_body(draw, bounce)

    # Eyes and mouth based on state
    if state == "blink":
        _eyes(draw, "blink", bounce)
        _mouth(draw, "normal", bounce)
    elif state == "talk":
        eye_state = "talk" if frame % 2 == 0 else "normal"
        mouth_state = "talk" if frame % 2 == 0 else "normal"
        _eyes(draw, eye_state, bounce)
        _mouth(draw, mouth_state, bounce)
    elif state == "happy":
        _eyes(draw, "happy", bounce)
        _mouth(draw, "happy", bounce)
    elif state == "sleep":
        _eyes(draw, "sleep", bounce)
        _mouth(draw, "sleep", bounce)
    else:
        _eyes(draw, "normal", bounce)
        _mouth(draw, "normal", bounce)

    return img


def create_all_sprites() -> dict[str, list[Image.Image]]:
    """Create all sprite animations as PIL Images."""
    sprites = {}
    for state in ["idle", "walk", "talk", "happy", "sleep", "blink"]:
        frames = [create_sprite(state, f) for f in range(4)]
        sprites[state] = frames
    return sprites
