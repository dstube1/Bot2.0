"""
Test: look in 4 directions by yaw +90° increments.
- Calibrates current view using 'ccc' clipboard.
- Parses current position from clipboard.
- Rotates yaw in 90° steps, waiting 1 second between turns.
"""

import time
import os
import sys

try:
    import pyperclip  # type: ignore
except Exception:
    pyperclip = None

# Ensure workspace root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.base import PlayerInput, BotState


def parse_clipboard_pos() -> float | None:
    """Parse the position value from the current clipboard (last three tokens: pos yaw pitch)."""
    if pyperclip is None:
        return None
    try:
        clip = pyperclip.paste() or ""
        parts = clip.strip().split()
        if len(parts) >= 3:
            return float(parts[-3])
    except Exception:
        return None
    return None


def main():
    pi = PlayerInput()
    bs = BotState()

    print("Calibrating current view. Bring ARK to foreground; sending 'ccc'...")
    time.sleep(5)
    pi.calibrate_current_view(bs)
    pos = parse_clipboard_pos()
    if pos is not None:
        bs.position = pos
    print(f"Start: position={bs.position}, view={bs.view_direction}")

    base_yaw, base_pitch = bs.view_direction if bs.view_direction else (0.0, 0.0)
    # Look in four directions: +90°, +180°, +270°, +360° relative to starting yaw
    for i in range(1, 5):
        target_yaw = base_yaw + 90.0 * i
        target_pitch = base_pitch
        print(f"Looking to yaw={target_yaw:.2f}, pitch={target_pitch:.2f}")
        pi.look_at((target_yaw, target_pitch), bs)
        time.sleep(1)


if __name__ == "__main__":
    main()
