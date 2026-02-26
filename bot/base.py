
"""
Core base functions and classes for ARK Survival Ascended automation bot.
"""

import ctypes
import pyautogui
import json
import os
import time
from PIL import ImageGrab
import pytesseract
import cv2
import numpy as np
import threading
import tkinter as tk
import pyperclip
from typing import Optional, Tuple, List


# --- Simple logging levels (configurable via config.json -> "Logging") ---
LOG_LEVELS = {"NONE": 50, "ERROR": 40, "WARN": 30, "INFO": 20, "DEBUG": 10}
LOG_LEVEL_NAME = "INFO"
LOG_LEVEL = LOG_LEVELS[LOG_LEVEL_NAME]

def _normalize_level(level):
    try:
        if isinstance(level, int):
            return level
        if isinstance(level, str):
            upper = level.strip().upper()
            return LOG_LEVELS.get(upper, LOG_LEVELS["INFO"])
    except Exception:
        pass
    return LOG_LEVELS["INFO"]

def set_log_level(level):
    global LOG_LEVEL, LOG_LEVEL_NAME
    LOG_LEVEL = _normalize_level(level)
    try:
        inv = {v: k for k, v in LOG_LEVELS.items()}
        LOG_LEVEL_NAME = inv.get(LOG_LEVEL, "INFO")
    except Exception:
        LOG_LEVEL_NAME = "INFO"

def should_log(level: str) -> bool:
    return LOG_LEVELS.get(level.upper(), 999) >= LOG_LEVEL

def log(level: str, msg: str) -> None:
    if should_log(level):
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] [{level.upper()}] {msg}")

def debug(msg: str) -> None:
    log("DEBUG", msg)

def info(msg: str) -> None:
    log("INFO", msg)

def warn(msg: str) -> None:
    log("WARN", msg)

def error(msg: str) -> None:
    log("ERROR", msg)



class BotState:
    """Tracks the current state of the bot and player."""
    def __init__(self):
        self.position = None
        self.view_direction = None
        self.last_action_success = True
        self.is_crouching = False
        self.current_task = None  # Name/description of the currently executing task
        self.last_failed_step = None  # Stores task name or context of last failure
        self.recovery_count = 0       # Number of recovery attempts executed
        self.current_task_obj = None  # Reference to current task object
        self.recovery_restarts = 0    # Number of task restarts performed after recovery
        self.recovery_max_restarts = None  # Unlimited restarts when using external driver reruns
        self.restart_requested = False  # Flag set when a task should be restarted externally
        # Inventory UI state tracking
        self.inventory_open = False         # True if any inventory UI is open
        self.inventory_type = None          # 'own', 'teleporter', or a custom label


class RestartTask(Exception):
    """Raised to abort the current task flow so it can be restarted cleanly."""
    pass


class PlayerInput:
    """Handles all player input actions: view, mouse, keyboard, console."""
    def __init__(self):
        self.ocr = OCR()
        self.recovery = Recovery(self)
        # Load global config values
        config_path = os.path.join(os.path.dirname(__file__), '../config/config.json')
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            factor = config.get('degree_to_pixel_factor', {"x": 10, "y": 10})
            self.degree_to_pixel_factor_x = factor.get('x', 10)
            self.degree_to_pixel_factor_y = factor.get('y', 10)
            # Set logging level from config if present
            try:
                set_log_level(config.get('Logging', LOG_LEVEL_NAME))
            except Exception:
                pass
        except Exception:
            error("Error loading pixel_factor from config.json")

        config_path = os.path.join(os.path.dirname(__file__), '../config/look_positions.json')
        try:
            with open(config_path, 'r') as f:
                config_look = json.load(f)
            # Keep raw for later lookups
            self._look_cfg = config_look
            # Use new format: each entry has 'position', 'view_direction' (tuple of yaw, pitch)
            self.tp = next((item for item in config_look.get("calibrations", []) if item.get("name") == "tp"), None)
            self.tp_nudge = next((item for item in config_look.get("calibrations", []) if item.get("name") == "tp_nudge"), None)
            self.sleep_pod = next((item for item in config_look.get("calibrations", []) if item.get("name") == "sleep_pod"), None)
        except Exception:
            error("Error loading look_positions from config.json")

        # Load click positions and normalize to tuples; support 'position' or 'click'
        config_path = os.path.join(os.path.dirname(__file__), '../config/click_positions.json')
        try:
            with open(config_path, 'r') as f:
                clicks_cfg = json.load(f)
            # Keep raw for later lookups
            self._clicks_cfg = clicks_cfg
            inventories = clicks_cfg.get("inventories", [])
            def find_inv(name):
                item = next((it for it in inventories if it.get("name") == name), None)
                if item:
                    if isinstance(item.get("position"), list):
                        item["position"] = tuple(item["position"])  # list -> tuple
                    # Some entries may use 'click' instead of 'position'
                    if "position" not in item and isinstance(item.get("click"), list):
                        item["position"] = tuple(item["click"]) 
                return item
            self.tp_textfield       = find_inv("tp_textfield")
            self.choose_top_tp      = find_inv("choose_top_tp")
            self.teleport_button    = find_inv("teleport_button")
            self.top_screen         = tuple(find_inv("top_screen")["position"]) if find_inv("top_screen") else None
            self.take_all           = tuple(find_inv("take_all")["position"]) if find_inv("take_all") else None
            self.store_all          = tuple(find_inv("store_all")["position"]) if find_inv("store_all") else None
            self.drop_all           = tuple(find_inv("drop_all")["position"]) if find_inv("drop_all") else None
            self.textfield_right    = tuple(find_inv("textfield_right")["position"]) if find_inv("textfield_right") else None
            self.textfield_left     = tuple(find_inv("textfield_left")["position"]) if find_inv("textfield_left") else None
            self.sleep_click        = tuple(find_inv("sleep_click")["position"]) if find_inv("sleep_click") else None
            # Optional: first slot in own inventory for crystal cracking
            self.first_slot_own     = tuple(find_inv("first_slot_own")["position"]) if find_inv("first_slot_own") else None
            # Optional: small mouse nudge used during crystal checks
            self.nudge_mouse        = tuple(find_inv("nudge_mouse")["position"]) if find_inv("nudge_mouse") else None
            # Optional scan region for drop_item: prefer scan_windows entry, else fallback to drop_all scan
            # Note: region is not a click position; wired below after scan_windows load.
            self.drop_item_scan = None

            self.grind_button = tuple(find_inv("grind_button")["position"]) if find_inv("grind_button") else None

        except Exception as e:
            error(f"Error loading click_positions.json: {e}")
        # Load scan window regions and normalize to 4-tuple; JSON uses key 'window'
        config_path = os.path.join(os.path.dirname(__file__), '../config/scan_windows.json')
        try:
            with open(config_path, 'r') as f:
                scan_windows = json.load(f)
            others = scan_windows.get("other", [])
            def find_scan(name):
                item = next((it for it in others if it.get("name") == name), None)
                if item:
                    reg = item.get("window") or item.get("region")
                    if isinstance(reg, list):
                        if len(reg) == 4:
                            item_tuple = tuple(reg)
                        elif len(reg) == 2:
                            w, h = reg
                            item_tuple = (0, 0, w, h)
                    elif isinstance(reg, tuple):
                        item_tuple = reg
                    else:
                        item_tuple = None
                    return item_tuple
                return None
            self.tp_scan        = find_scan("teleporter")
            self.tp_inv_scan    = find_scan("tp_inv")
            self.tp_list_scan   = find_scan("tp_list")
            self.own_inv_scan   = find_scan("inventory")
            self.take_all_scan  = find_scan("take_all")
            self.store_all_scan = find_scan("store_all")
            self.drop_all_scan  = find_scan("drop_all")
            # If a specific drop_item scan region exists in 'other', use it; else fallback to drop_all_scan
            self.drop_item_scan = find_scan("drop_item") or self.drop_all_scan
            self.pod_scan       = find_scan("Pod")
            # Optional: region for first own inventory slot
            self.first_slot_own_scan = find_scan("first_slot_own")
            # Optional: region for first grinder inventory slot (for metal presorting loop)
            self.first_slot_grinder_scan = find_scan("first_slot_grinder")
            self.grinder_slots = find_scan("grinder_slots")
            # Player HUD metric: weight
            self.player_weight_scan = find_scan("player_weight")
            # Dedicated storage amount banner
            self.dedi_amt_scan = find_scan("dedi_amt")
        except Exception as e:
            error(f"Error loading scan_windows.json: {e}")
        # Load scan texts and normalize to text list
        config_path = os.path.join(os.path.dirname(__file__), '../config/scan_text.json')
        try:
            with open(config_path, 'r') as f:
                scan_texts = json.load(f)
            texts = scan_texts.get("texts", [])
            def find_text(name):
                item = next((it for it in texts if it.get("name") == name), None)
                # Ensure 'text' is a list
                if item:
                    if isinstance(item.get("text"), str):
                        item_list = [item["text"]]
                    else:
                        item_list = item.get("text", [])
                    return item_list
                return []
            self.tp_text         = find_text("tp_text")
            self.tp_inv_text     = find_text("tp_inv_text")
            self.tp_list_text    = find_text("tp_list_text")
            self.bag_text        = find_text("bag_text")
            self.inv_text        = find_text("inv_text")
            self.take_all_text   = find_text("take_all_text")
            self.store_all_text  = find_text("store_all_text")
            self.drop_all_text   = find_text("drop_all_text")
            # Some configs may not have a specific drop_item_text; fallback to drop_all_text
            tmp_drop_item_text   = find_text("drop_item_text")
            self.drop_item_text  = tmp_drop_item_text if tmp_drop_item_text else self.drop_all_text
            self.pod_text        = find_text("Pod")
        except Exception as e:
            error(f"Error loading scan_text.json: {e}")

        # Load teleporter destinations
        tp_cfg_path = os.path.join(os.path.dirname(__file__), '../config/teleporter.json')
        try:
            with open(tp_cfg_path, 'r') as f:
                data = json.load(f)
            items = data.get('teleporters', [])
            # Map name -> entry for quick lookup
            self.teleporters = { it.get('name'): it for it in items if it.get('name') }
            # Convenience: default bed destination
            self.teleporter_render = next((name for name, it in self.teleporters.items() if name == 'render' and it.get('enabled', True)), None)
            if not self.teleporter_render:
                # Fallback to first enabled teleporter
                enabled = [name for name, it in self.teleporters.items() if it.get('enabled', True)]
                self.teleporter_render = enabled[0] if enabled else 'render'
        except Exception as e:
            error(f"Error loading teleporter.json: {e}")
            self.teleporters = {}
            self.teleporter_render = 'render'

    # ---- Config helpers ----
    def load_json(self, filename: str) -> dict:
        """Load a JSON file from the config folder and return its dict (empty on failure)."""
        try:
            cfg_path = os.path.join(os.path.dirname(__file__), '..', 'config', filename)
            with open(cfg_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            error(f"load_json('{filename}'): failed: {e}")
            return {}

    def get_click_position(self, key: str):
        """Return a click position (x,y) for a top-level key in click_positions.json, or None."""
        try:
            data = getattr(self, '_clicks_cfg', None) or self.load_json('click_positions.json')
            pos = data.get(key)
            if isinstance(pos, (list, tuple)) and len(pos) == 2:
                return (float(pos[0]), float(pos[1]))
        except Exception:
            pass
        return None

    def get_calibration_view_direction(self, name: str):
        """Return (yaw,pitch) for a calibration entry by name from look_positions.json."""
        try:
            lp = getattr(self, '_look_cfg', None) or self.load_json('look_positions.json')
            cals = lp.get('calibrations', [])
            entry = next((c for c in cals if c.get('name') == name), None)
            vd = entry.get('view_direction') if entry else None
            if isinstance(vd, (list, tuple)) and len(vd) == 2:
                return (float(vd[0]), float(vd[1]))
        except Exception:
            pass
        return None

    def resolve_view_label(self, target_view) -> Optional[str]:
        """Try to resolve a human-friendly label for a given view by matching calibrations.

        Compares the provided yaw/pitch against entries in look_positions.json and
        returns the calibration 'name' when an exact match is found (float equality).
        """
        try:
            lp = getattr(self, '_look_cfg', None) or self.load_json('look_positions.json')
            cals = lp.get('calibrations', [])
            # Normalize input
            yaw_pitch = None
            if isinstance(target_view, (list, tuple)) and len(target_view) == 2:
                yaw_pitch = (float(target_view[0]), float(target_view[1]))
            elif isinstance(target_view, dict):
                if 'view_direction' in target_view and isinstance(target_view['view_direction'], (list, tuple)):
                    vp = target_view['view_direction']
                    if len(vp) == 2:
                        yaw_pitch = (float(vp[0]), float(vp[1]))
                elif 'yaw' in target_view and 'pitch' in target_view:
                    yaw_pitch = (float(target_view['yaw']), float(target_view['pitch']))
            if yaw_pitch is None:
                return None
            tyaw, tpitch = yaw_pitch
            for cal in cals:
                vd = cal.get('view_direction')
                if isinstance(vd, (list, tuple)) and len(vd) == 2:
                    cyaw, cpitch = float(vd[0]), float(vd[1])
                    if cyaw == tyaw and cpitch == tpitch:
                        return cal.get('name')
            return None
        except Exception:
            return None

    def move_mouse_relative(self, dx: int, dy: int)-> None:
        """
        Moves the mouse dx to the right/left and dy up/down from the current position
        """
        ctypes.windll.user32.mouse_event(0x0001, dx, dy, 0, 0)  # 0x0001 = MOUSEEVENTF_MOVE

    def move_mouse_absolute(self,x: int, y: int)-> None:
        """
        Moves the mouse to the coordinates x,y
        """
        pyautogui.moveTo(x, y)

    def smooth_mouse_move(self, dx: int, dy: int, move_steps: int = 6, move_pause: float = 0.01, key: str = 'e') -> None:
        """
        Moves the mouse smoothly by breaking movement into smaller steps, pressing a key while moving.
        Args:
            dx: Change in x-coordinate.
            dy: Change in y-coordinate.
            move_steps: Number of steps to break movement into.
            move_pause: Pause between each step.
            key: Key to press while moving (default 'e' for opening crystals; use 't' for transferring items).
        """
        try:
            step_x = dx / float(move_steps)
            step_y = dy / float(move_steps)
            for _ in range(int(move_steps)):
                # Use relative mouse move for fractional steps rounded
                self.move_mouse_relative(int(step_x), int(step_y))
                self.press_key(key)
                time.sleep(move_pause)
        except Exception as e:
            error(f"smooth_mouse_move: failed: {e}")

    def _reverse(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        """Return the negated (dx, dy) for a given movement tuple."""
        try:
            return (-int(pos[0]), -int(pos[1]))
        except Exception:
            return (0, 0)

    def crystal_left(self, region: Optional[Tuple[int, int, int, int]] = None, confidence: float = 0.4) -> bool:
        """
        Check if crystals are left in the Inventory by comparing the first slot with a reference image.
        Returns True if crystals remain in the slot, False otherwise.
        Uses pyautogui screenshot of `region` and OpenCV template matching against assets/Gacha_Crystal.png.
        """
        try:
            import cv2
            import pyautogui as pyg
            # Default to configured first slot scan region if not provided
            if region is None:
                region = getattr(self, 'first_slot_own_scan', None)
                if region is None:
                    warn("crystal_left: first_slot_own_scan not configured; assuming no crystals left.")
                    return False
            time.sleep(0.2)
            # Nudge mouse slightly if configured (optional)
            if getattr(self, 'nudge_mouse', None):
                dx, dy = self.nudge_mouse
                self.move_mouse_relative(int(dx), int(dy))
                time.sleep(0.2)
            debug(f"Capturing screenshot of region: {region}")
            # pyautogui expects (left, top, width, height)
            left, top, right, bottom = region
            width = right - left
            height = bottom - top
            screenshot = pyg.screenshot(region=(left, top, width, height))
            screenshot_path = os.path.join("assets", "first_slot.png")
            try:
                os.makedirs("assets", exist_ok=True)
            except Exception:
                pass
            screenshot.save(screenshot_path)
            # Load reference image (empty or crystal slot indicator)
            empty_slot_image_path = os.path.join("assets", "Gacha_Crystal.png")
            screenshot_cv = cv2.imread(screenshot_path, cv2.IMREAD_GRAYSCALE)
            empty_slot_image_cv = cv2.imread(empty_slot_image_path, cv2.IMREAD_GRAYSCALE)
            if screenshot_cv is None or empty_slot_image_cv is None:
                error("crystal_left: error loading images.")
                return False
            result = cv2.matchTemplate(screenshot_cv, empty_slot_image_cv, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            debug(f"Template matching max value: {max_val}")
            time.sleep(1)
            # Reverse nudge
            if getattr(self, 'nudge_mouse', None):
                rev = self._reverse(self.nudge_mouse)
                self.move_mouse_relative(int(rev[0]), int(rev[1]))
                time.sleep(0.2)
            threshold = float(confidence)
            if max_val >= threshold:
                debug("Still Crystals in Inv")
                return True
            else:
                debug("No Crystal left")
                return False
        except Exception as e:
            error(f"crystal_left: failed: {e}")
            return False

    def slot_empty(self, region: Optional[Tuple[int, int, int, int]] = None, template_path: Optional[str] = None, confidence: float = 0.4) -> bool:
        """Generic slot emptiness check using template matching.

        Returns True if the slot appears empty. Works similar to crystal_left but
        uses an empty-slot template. Region defaults to first_slot_grinder_scan if not provided.
        Template defaults to assets/Empty_Grinder_Slot.png.
        """
        try:
            import cv2
            import pyautogui as pyg
            if region is None:
                region = getattr(self, 'first_slot_grinder_scan', None)
                if region is None:
                    warn("slot_empty: no region provided and first_slot_grinder_scan missing; assuming not empty.")
                    return False
            if template_path is None:
                template_path = os.path.join("assets", "Empty_Grinder_Slot.png")
            # Capture screenshot
            left, top, right, bottom = region
            width = right - left
            height = bottom - top
            screenshot = pyg.screenshot(region=(left, top, width, height))
            os.makedirs("assets", exist_ok=True)
            tmp_path = os.path.join("assets", "grinder_slot_tmp.png")
            screenshot.save(tmp_path)
            shot_cv = cv2.imread(tmp_path, cv2.IMREAD_GRAYSCALE)
            templ_cv = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            if shot_cv is None or templ_cv is None:
                error("slot_empty: failed loading slot/template images; default False.")
                return False
            result = cv2.matchTemplate(shot_cv, templ_cv, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            return max_val >= float(confidence)
        except Exception as e:
            error(f"slot_empty: error: {e}")
            return False

    def look_at(self, target_view, bot_state: BotState):
        """
        Turns the character's view to the given yaw/pitch and updates the bot's view direction.
        Accepts either a dict with a 'view_direction' field, a dict with 'yaw'/'pitch',
        or a tuple/list of (yaw, pitch).

        Args:
            target_view: dict or (yaw, pitch) describing the target look direction.
            bot_state (BotState): The bot state instance to update.
        """
        if target_view is None:
            error("look_at: missing target_view!")
            return
        yaw_pitch = None
        if isinstance(target_view, (list, tuple)) and len(target_view) == 2:
            yaw_pitch = (float(target_view[0]), float(target_view[1]))
        elif isinstance(target_view, dict):
            if 'view_direction' in target_view and isinstance(target_view['view_direction'], (list, tuple)):
                vp = target_view['view_direction']
                if len(vp) == 2:
                    yaw_pitch = (float(vp[0]), float(vp[1]))
            elif 'yaw' in target_view and 'pitch' in target_view:
                yaw_pitch = (float(target_view['yaw']), float(target_view['pitch']))
            elif 'gacha_view_direction' in target_view and isinstance(target_view['gacha_view_direction'], (list, tuple)):
                vp = target_view['gacha_view_direction']
                if len(vp) == 2:
                    yaw_pitch = (float(vp[0]), float(vp[1]))
        if yaw_pitch is None:
            error("look_at: could not resolve yaw/pitch from target_view")
            return
        yaw, pitch = yaw_pitch
        current = bot_state.view_direction if bot_state.view_direction else (0.0, 0.0)
        dx_deg = yaw - current[0]
        dy_deg = pitch - current[1]
        dx_pix = int(dx_deg / self.degree_to_pixel_factor_x)
        dy_pix = int(dy_deg / self.degree_to_pixel_factor_y)
        self.move_mouse_relative(dx_pix, dy_pix)
        bot_state.view_direction = (yaw, pitch)

    def press_key(self, key):
        """
        Presses a key using pyautogui.
        Args:
            key (str): The key to press (e.g., 'a', 'enter').
        """
        pyautogui.press(key)

    def log_task(self, bot_state: BotState, task_name: str, task_obj=None):
        """Record current task name and optionally its object in bot_state (in-memory)."""
        bot_state.current_task = task_name
        bot_state.restart_requested = False  # clear any pending restart signal when a task (re)starts
        if task_obj is not None:
            bot_state.current_task_obj = task_obj

    def crouch(self, bot_state: BotState):
        """
        Toggle crouch. Presses the crouch key and flips bot_state.is_crouching.
        Assumes default crouch key is 'c'.
        """
        self.press_key('c')
        # Flip local state
        bot_state.is_crouching = not bot_state.is_crouching

    def enter_text(self, pos: tuple[float, float], text="")-> None:
        """
        Moves to the specified position, clicks, and types the given text letter by letter.
        Default: Text in own Inv

        Args:
            position (tuple): (x, y) coordinates of the text field on the screen.
            text (str): The text to enter into the field.
        """
        self.move_mouse_absolute(*pos)
        pyautogui.click()
        time.sleep(0.1)
        pyautogui.typewrite(text)

    def pos_to_str(self, pos: tuple[float, float]) -> str:
        """
        Converts a position tuple (x, y) to a string representation.
        """
        return f"({pos[0]}, {pos[1]})"

    def calibrate_current_view(self, bot_state: BotState, wait_seconds: float = 0.5) -> Optional[Tuple[float, float]]:
        """
        Trigger 'ccc' in-game, read clipboard, and save yaw/pitch to bot_state.view_direction.
        Mirrors the logic used in calibration.calibrator.

        Args:
            bot_state: BotState instance to update.
            wait_seconds: Delay to allow clipboard to update after sending ccc.

        Returns:
            (yaw, pitch) on success, otherwise None.
        """
        try:
            time.sleep(1)
            pyautogui.press('tab')
            pyautogui.typewrite('ccc')
            pyautogui.press('enter')
            time.sleep(wait_seconds)
            clipboard_data = pyperclip.paste()
            if not clipboard_data:
                error("calibrate_current_view: clipboard is empty after 'ccc'")
                return None
            parts = clipboard_data.strip().split()
            if len(parts) < 3:
                error(f"calibrate_current_view: unexpected clipboard format: {clipboard_data}")
                return None
            pos_str, yaw_str, pitch_str = parts[-3], parts[-2], parts[-1]
            # pos is not applied to state here, only view
            yaw = float(yaw_str)
            pitch = float(pitch_str)
            bot_state.view_direction = (yaw, pitch)
            debug(f"Calibrated view saved: yaw={yaw}, pitch={pitch}")
            return (yaw, pitch)
        except Exception as e:
            error(f"calibrate_current_view: failed to parse clipboard: {e}")
            return None

    def teleport_to(self, destination: str, bot_pos: BotState)-> None:
        """
        Teleports the player to the specified destination.
        
        Args:
            destination (str): The name of the destination Teleporter.
        """
        # Calibrate view before looking at tp
        self.calibrate_current_view(bot_pos)
        # Face teleporter UI region
        self.look_at(self.tp, bot_pos)
        # Checking if seeing teleporter using preloaded scan regions and expected texts
        state, read = self.ocr.wait_for_text(self.tp_scan, self.tp_text, False, bot_state=bot_pos, recovery=self.recovery)
        for expected_text in self.bag_text:
            if expected_text in read:
                self.look_at(self.tp_nudge, bot_pos)  # Nudge view
                time.sleep(0.2)
                break
        if destination != bot_pos.position:
            self.press_key('e')
            # Checking it teleporter inventory loaded
            self.ocr.wait_for_text(self.tp_inv_scan, self.tp_inv_text, False, bot_state=bot_pos, recovery=self.recovery)
            self.enter_text(tuple(self.tp_textfield['position']), destination)
            self.ocr.wait_for_text(self.tp_list_scan, self.tp_list_text, False, bot_state=bot_pos, recovery=self.recovery)
            self.move_mouse_absolute(*tuple(self.choose_top_tp['position']))
            pyautogui.click()
            time.sleep(0.2)
            self.move_mouse_absolute(*tuple(self.teleport_button['position']))
            pyautogui.click()
            #time.sleep(1)
            # Check if teleport was successful
            self.ocr.wait_for_text(self.tp_scan, self.tp_text, False, bot_state=bot_pos, recovery=self.recovery)
            self.look_at(self.tp, bot_pos)
            bot_pos.position = destination
            debug(f"Teleport successful -> '{destination}'")
            # Log as a task-like state for recovery referencing
            self.log_task(bot_pos, f"teleport:{destination}")
        else:
            debug('Already at destination....')

    def run_console_command(self, command):
        debug(f"Running console command: {command}")
        # Dummy: Simulate console command

    def go_to_bed(self, bot_state: BotState) -> bool:
        """Use the teleporter to port to the bed defined in teleporter.json."""
        try:
            # Use preloaded teleporter destination
            dest_name = self.teleporter_render or 'render'
            self.teleport_to(dest_name, bot_state)

            # After teleport, align to sleep pod and interact (sleep_pod loaded in __init__)

            if self.sleep_pod:
                self.look_at(self.sleep_pod, bot_state)
            else:
                warn("go_to_bed: sleep_pod calibration missing; skipping look alignment.")

            if getattr(self, 'pod_scan', None) and getattr(self, 'pod_text', None):
                self.ocr.wait_for_text(self.pod_scan, self.pod_text, False, bot_state=bot_state, recovery=self.recovery)

            # Hold 'e', click sleep, then release 'e' as requested
            pyautogui.keyDown('e')
            time.sleep(1)
            if self.sleep_click and isinstance(self.sleep_click, tuple):
                self.move_mouse_absolute(*self.sleep_click)
                time.sleep(1)
                pyautogui.click()
            else:
                warn("go_to_bed: sleep_click position missing; skipping click.")
            time.sleep(1)
            pyautogui.keyUp('e')
            time.sleep(0.7)

            return True
        except Exception as e:
            error(f"go_to_bed: teleport failed: {e}")
            return False

    def wake_up(self, bot_state: BotState, settle_seconds: float = 1) -> bool:
        """Wake up: press 'e', wait a moment, then refresh current view via 'ccc'."""
        try:
            self.press_key('e')
            time.sleep(settle_seconds)
            self.calibrate_current_view(bot_state)
            return True
        except Exception as e:
            error(f"wake_up: failed: {e}")
            return False


class InventoryManager:
    """Handles opening, closing, and interacting with inventories."""
    def grinder_slots(self, region: tuple[int, int, int, int], limit: int) -> bool:
        """
        Check if the grinder slots exceed the given limit by detecting the text 'xxx / 120' or 'xxx \ 120'.

        Args:
            region (tuple): The region (x1, y1, x2, y2) to capture.
            limit (int): The slot limit to check against.

        Returns:
            bool: True if the slots exceed the limit, False otherwise.
        """
        import re
        
        expected_texts = ['/120', '\120']
        found, read_text = self.ocr.wait_for_text(region, expected_texts, False)
        if found:
            try:
                debug(f"Captured text: {read_text}")
                match = re.search(r'(\d+)(/|\\)120', read_text)
                if match:
                    occupied_slots = int(match.group(1))
                    debug(f"Occupied slots: {occupied_slots}")
                    if occupied_slots >= limit:
                        debug(f"Slots exceed limit of {limit}, with: {occupied_slots} / 120 slots")
                        return True
                    else:
                        debug(f"Grinder is not full: {occupied_slots} / 120")
                        return False
                else:
                    error("Pattern not found in the cleaned text.")
                    return False
            except ValueError:
                error("Error parsing the number of occupied slots.")
                return False
        else:
            error("Text not found.")
            return False

    def __init__(self):
        self.ocr = OCR()
        self.input = PlayerInput()
        # Optional external injection of BotState; can be set by caller.
        self.bot_state = None
        # Internal cache to avoid redundant OCR checks
        self._last_open_check_ts = 0.0

    def _set_inv_state(self, open: bool, inv_type: Optional[str] = None):
        """Update bot_state inventory flags and print a concise log."""
        try:
            if hasattr(self, 'bot_state') and self.bot_state is not None:
                self.bot_state.inventory_open = bool(open)
                self.bot_state.inventory_type = inv_type if open else None
        except Exception:
            pass

    def open_inv(self, expected_label: Optional[str] = None) -> bool:
        """
        Opens a dinos or strucures Inventory.
        Args:
            dino (bool): True for dino inventory, to prevent lvl 1 bug.
        Returns:
            bool: True if inventory opened, False if not.
        """
        # If already open, verify the expected structure label when provided
        if hasattr(self, 'bot_state') and self.bot_state and self.bot_state.inventory_open:
            if expected_label and isinstance(self.bot_state.inventory_type, str) and self.bot_state.inventory_type.startswith('structure:'):
                current_label = self.bot_state.inventory_type.split(':', 1)[1]
                if current_label == expected_label:
                    info(f"open_inv: correct structure '{expected_label}' already open; skipping 'f'.")
                    return True
                else:
                    info(f"open_inv: different inventory open ('{self.bot_state.inventory_type}'); attempting to switch.")
            else:
                debug(f"open_inv: inventory already open ({self.bot_state.inventory_type}); skipping 'f'.")
                return True
        time.sleep(0.1)
        self.input.press_key('f')
        state, read = self.ocr.wait_for_text(self.input.own_inv_scan, self.input.inv_text, False, bot_state=self.bot_state if hasattr(self,'bot_state') else None, recovery=self.input.recovery)
        if state:
            # Attempt to label the current structure based on last view
            label = None
            try:
                current_view = self.bot_state.view_direction if (hasattr(self,'bot_state') and self.bot_state) else None
                label = self.input.resolve_view_label(current_view)
            except Exception:
                label = None
            inv_type = f"structure:{label}" if label else 'structure:unknown'
            self._set_inv_state(True, inv_type)
            # If expected_label provided, verify we opened the intended structure
            if expected_label and label and label != expected_label:
                warn(f"open_inv: opened structure '{label}' but expected '{expected_label}'.")
                # Optionally, we could press ESC and retry; for now, just report mismatch
        return state

    def open_own_inv(self):
        """
        Opens your own Inventory.

        Returns:
            bool: True if inventory opened, False if not.
        """
        # If already open and it's own inventory, skip
        if hasattr(self, 'bot_state') and self.bot_state and self.bot_state.inventory_open and self.bot_state.inventory_type == 'own':
            debug("open_own_inv: own inventory already open; skipping 'i'.")
            return True
        self.input.press_key('i')
        state, read = self.ocr.wait_for_text(self.input.own_inv_scan, self.input.inv_text, False, bot_state=self.bot_state if hasattr(self,'bot_state') else None, recovery=self.input.recovery)
        if state is True:
            self._set_inv_state(True, 'own')
            return True
        if state is False:
            return False
        # Fallback: try opening nearby inventory
        state = self.open_inv()
        return state

    def close_inv(self):
        """
        Closes the Inventory. (with 'F')
        """
        if self.input.top_screen:
            self.input.move_mouse_absolute(*self.input.top_screen)
        time.sleep(0.1)
        pyautogui.click()
        self.input.press_key('f')
        state = self.ocr.wait_for_no_text(self.input.own_inv_scan, self.input.inv_text)
        if not state:
            self.input.press_key('f')
            self.ocr.wait_for_no_text(self.input.own_inv_scan, self.input.inv_text, bot_state=self.bot_state if hasattr(self,'bot_state') else None, recovery=self.input.recovery)
        time.sleep(0.1)
        self._set_inv_state(False, None)

    def take_all(self) -> None:
        """
        Takes all items from the opened inventory.
        """
        if self.input.take_all:
            self.input.move_mouse_absolute(*self.input.take_all)
        self.ocr.wait_for_text(self.input.take_all_scan, self.input.take_all_text, True, bot_state=self.bot_state if hasattr(self,'bot_state') else None, recovery=self.input.recovery)

    def store_all(self) -> None:
        """
        Stores all items from the opened inventory.
        """
        if self.input.store_all:
            self.input.move_mouse_absolute(*self.input.store_all)
        self.ocr.wait_for_text(self.input.store_all_scan, self.input.store_all_text, True, bot_state=self.bot_state if hasattr(self,'bot_state') else None, recovery=self.input.recovery)

    def drop_all(self) -> None:
        """
        Drops all items in player inventory. (inventory needs to be open)
        """
        if self.input.drop_all:
            self.input.move_mouse_absolute(*self.input.drop_all)
        self.ocr.wait_for_text(self.input.drop_all_scan, self.input.drop_all_text, True, bot_state=self.bot_state if hasattr(self,'bot_state') else None, recovery=self.input.recovery)

    def drop_item(self,item: str)-> None:
        """
        Drops a specific item from the inventory.
        """
        if self.input.textfield_left:
            self.input.enter_text(self.input.textfield_left, item)
        if self.input.drop_all:
            self.input.move_mouse_absolute(*self.input.drop_all)
        self.ocr.wait_for_text(self.input.drop_item_scan, self.input.drop_item_text, True, bot_state=self.bot_state if hasattr(self,'bot_state') else None, recovery=self.input.recovery)

    def take_item(self, item: str)-> None:
        """
        Takes a specific item from the inventory.
        """
        if self.input.textfield_right:
            self.input.enter_text(self.input.textfield_right, item)
        if self.input.take_all:
            self.input.move_mouse_absolute(*self.input.take_all)
        self.ocr.wait_for_text(self.input.take_all_scan, self.input.take_all_text, True, bot_state=self.bot_state if hasattr(self,'bot_state') else None, recovery=self.input.recovery)


class OCR:
    """Handles screen text recognition using OCR (e.g., Tesseract)."""

    def _grab_region_np(self, region: tuple[int, int, int, int]):
        """Capture a screen region reliably and return an RGB numpy array.

        Tries multiple backends in order of reliability for games:
        1) dxcam (Desktop Duplication API) – best for fullscreen/DirectX
        2) mss – fast, cross-platform; BGRA frames
        3) pyautogui.screenshot – uses PIL under the hood
        4) PIL.ImageGrab – last resort
        """
        left, top, right, bottom = region
        width = right - left
        height = bottom - top
        # 1) dxcam
        try:
            import dxcam  # type: ignore
            cam = dxcam.create(output_idx=0)
            frame = cam.grab(region=(left, top, right, bottom))
            if frame is not None:
                # frame is BGRA or BGR
                if len(frame.shape) == 3 and frame.shape[2] == 4:
                    return cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                elif len(frame.shape) == 3 and frame.shape[2] == 3:
                    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except Exception:
            pass
        # 2) mss
        try:
            import mss  # type: ignore
            with mss.mss() as sct:
                mon = {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}
                sct_img = sct.grab(mon)  # BGRA
                arr = np.array(sct_img)
                return cv2.cvtColor(arr, cv2.COLOR_BGRA2RGB)
        except Exception:
            pass
        # 3) pyautogui
        try:
            pil_img = pyautogui.screenshot(region=(int(left), int(top), int(width), int(height)))
            return np.array(pil_img)  # PIL screenshot returns RGB
        except Exception:
            pass
        # 4) PIL.ImageGrab
        pil_img = ImageGrab.grab(bbox=(int(left), int(top), int(right), int(bottom)))
        return np.array(pil_img)

    def recognize_text(self, region: tuple[int, int, int, int]) -> str:
        """
        Capture a screenshot of the specified region and use OCR to read text. (This adds some filters to the image)
        Parameters:
            region (tuple): The region to capture (left_top_x, left_top_y, bottom_left_x, bottom_left_y).
        Returns:
            str: The text read from the region.
        """
        # Retry ImageGrab up to 30 times with brief backoff
        attempts = 30
        last_err = None
        screenshot_np = None
        for i in range(attempts):
            try:
                screenshot_np = self._grab_region_np(region)
                break
            except Exception as e:
                last_err = e
                warn(f"recognize_text: ImageGrab failed (attempt {i+1}/{attempts}) for region {region}: {e}")
                time.sleep(0.25)
        if screenshot_np is None:
            error(f"recognize_text: ImageGrab failed after {attempts} attempts for region {region}")
            raise RestartTask(f"screen grab failed after retries: {last_err}")
        gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
        text = pytesseract.image_to_string(gray, config='--psm 6')
        return text

    def read_dedi_amount(self, region: tuple[int, int, int, int]) -> tuple[int, str] | tuple[None, None]:
        """Read "CONTAINS xxx RESSOURCE" from a dedicated storage banner region.

        Returns (amount, resource) when parsed, else (None, None).
        """
        try:
            raw = self.recognize_text(region)
            cleaned = raw.replace('\n', ' ').replace('\r', ' ').strip().upper()
            import re
            m = re.search(r"CONTAINS\s+(\d+)\s+([A-Z]+)", cleaned)
            if m:
                amt = int(m.group(1))
                res = m.group(2)
                return amt, res
            return None, None
        except RestartTask:
            # propagate restart so callers can handle
            raise
        except Exception as e:
            warn(f"read_dedi_amount: parse failed: {e}")
            return None, None

    def _normalize_region(self, region: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
        """
        Normalize region to a 4-tuple (x1, y1, x2, y2).
        Allows passing (w, h) and converts to (0, 0, w, h).
        """
        if isinstance(region, tuple):
            if len(region) == 4:
                return region
            if len(region) == 2:
                w, h = region
                return (0, 0, int(w), int(h))
        if isinstance(region, list):
            if len(region) == 4:
                return tuple(region)
            if len(region) == 2:
                w, h = region
                return (0, 0, int(w), int(h))
        raise ValueError(f"Invalid region format: {region}")

    def create_overlay_window(self, region: Tuple[int, int, int, int]) -> tk.Tk:
        """
        Create a transparent overlay window with a red box frame.
        Parameters:
            region (tuple): The region to capture (left_top_x, left_top_y, bottom_left_x, bottom_left_y).
        Returns:
            tk.TK: Creates the red box.
        """
        root = tk.Tk()
        root.attributes('-topmost', True)
        root.attributes('-alpha', 0.3)  # Set transparency level
        root.overrideredirect(True)  # Remove window decorations
        root.wm_attributes('-transparentcolor', 'black')    # Make the window click-through
        # Set the geometry of the window based on the region
        width = region[2] - region[0]
        height = region[3] - region[1]
        root.geometry(f"{width}x{height}+{region[0]}+{region[1]}")
        canvas = tk.Canvas(root, width=width, height=height, bg='black', highlightthickness=0)
        canvas.pack()
        canvas.create_rectangle(0, 0, width, height, outline='red', width=4)    # Draw a red rectangle around the region
        return root

    def display_region(self, region: Tuple[int, int, int, int]) -> None:
        """
        Display the region with a red box in a separate thread.
        Parameters:
            region (tuple): The region to capture (left_top_x, left_top_y, bottom_left_x, bottom_left_y).
        """
        overlay_window = self.create_overlay_window(region)
        while getattr(threading.current_thread(), "do_run", True):
            overlay_window.update_idletasks()
            overlay_window.update()
            time.sleep(0.01)
        overlay_window.destroy()  # Close the tkinter window when the thread stops


    def wait_for_text(self, region: Tuple[int, int, int, int], expected_texts: List[str], click=False, bot_state: Optional[BotState] = None, recovery: Optional['Recovery'] = None, retry_after_recovery: bool = True)-> Tuple[bool, str]:
        """
        Wait until any expected text appears in region.
        - Normalizes region coordinates.
        - Cleans OCR text (remove whitespace/newlines) for matching.
        - Optional click when first match found.
        - Optional single recovery attempt if initial wait fails.

        Returns (True, cleaned_text) on success or (False, "") on failure.
        """
        region = self._normalize_region(region)
        # Start the thread to display the region
        display_thread = threading.Thread(target=self.display_region, args=(region,))
        display_thread.start()
        success = False
        cleaned_text = ""
        try:
            for _ in range(100):
                read_text = self.recognize_text(region)
                cleaned_text = read_text.replace(' ', '').replace('\n', '').replace('\r', '')
                upper_clean = cleaned_text.upper()
                for expected_text in expected_texts:
                    if expected_text.upper() in upper_clean:
                        debug(f'Detected "{expected_text}" in region {region}....proceeding')
                        if click:
                            pyautogui.click()
                            time.sleep(0.05)
                        success = True
                        return True, cleaned_text
                time.sleep(0.2)
        finally:
            display_thread.do_run = False
            display_thread.join()

        if not success:
            debug("wait_for_text: Requested text not found!")
            if recovery and retry_after_recovery:
                if bot_state:
                    bot_state.last_failed_step = bot_state.current_task
                    bot_state.last_action_success = False
                    bot_state.recovery_count += 1
                debug(f"Attempting recovery procedure... (bot_state is {'set' if bot_state else 'None'})")
                if recovery.reset_player(bot_state):
                    debug("Recovery successful.")
                    # Restart the entire task if within restart limits
                    if bot_state and bot_state.current_task_obj:
                        bot_state.recovery_restarts += 1
                        debug(f"Signaling restart for task '{bot_state.current_task}' after recovery.")
                        bot_state.restart_requested = True
                        raise RestartTask(f"Restart signal for: {bot_state.current_task}")
                    elif not bot_state or not bot_state.current_task_obj:
                        warn("No current_task_obj set; aborting current flow to avoid mid-step continuation.")
                        raise RestartTask("Abort current flow: recovery executed but no task object to restart.")
                    else:
                        debug("Restart limit reached; performing single OCR retry.")
                        return self.wait_for_text(region, expected_texts, click, bot_state, None, False)
            else:
                if not recovery:
                    warn("\033[33mReset view\033[0m")
                if not retry_after_recovery:
                    error("retry_after_recovery disabled; skipping recovery.")
                if not bot_state:
                    debug("bot_state is None; recovery cannot track or restart task.")
            return False, ""

    def wait_for_no_text(self, region: Tuple[int, int, int, int], expected_texts: List[str], timeout=10, bot_state: Optional[BotState] = None, recovery: Optional['Recovery'] = None, retry_after_recovery: bool = True)-> bool:
        """
        Wait for text to disappear in the given screen region.

        Args:
            region (tuple): The region (x1, y1, x2, y2) to capture.
            timeout (int): The maximum time to wait in seconds.

        Returns:
            bool: True if no text is detected within the timeout period, False otherwise.
        """
        start_time = time.time()
        # Start the thread to display the region
        display_thread = threading.Thread(target=self.display_region, args=(region,))
        display_thread.start()
        try:
            region = self._normalize_region(region)
            while time.time() - start_time < timeout:
                read_text = self.recognize_text(region)
                cleaned_text = read_text.replace(' ', '').replace('\n', '').replace('\r', '')
                upper_clean = cleaned_text.upper()
                # If any expected text is still present, continue waiting
                still_present = False
                for expected_text in expected_texts:
                    if expected_text.upper() in upper_clean:
                        still_present = True
                        break
                if not still_present:
                        time.sleep(0.1)
                        return True
                time.sleep(0.1)
            # Failure path
            if recovery and retry_after_recovery:
                if bot_state:
                    bot_state.last_failed_step = bot_state.current_task
                    bot_state.last_action_success = False
                    bot_state.recovery_count += 1
                warn("wait_for_no_text: text still present; initiating recovery...")
                if recovery.reset_player(bot_state):
                    debug("Recovery successful.")
                    if bot_state and bot_state.current_task_obj:
                        bot_state.recovery_restarts += 1
                        debug(f"Signaling restart for task '{bot_state.current_task}' after recovery.")
                        bot_state.restart_requested = True
                        raise RestartTask(f"Restart signal for: {bot_state.current_task}")
                    elif not bot_state or not bot_state.current_task_obj:
                        error("No current_task_obj set; aborting current flow to avoid mid-step continuation.")
                        raise RestartTask("Abort current flow: recovery executed but no task object to restart.")
                    else:
                        warn("Restart limit reached; performing single no-text retry.")
                        return self.wait_for_no_text(region, expected_texts, timeout, bot_state, None, False)
            else:
                if not recovery:
                    warn("\033[33mReset view\033[0m")
                if not retry_after_recovery:
                    warn("retry_after_recovery disabled; skipping recovery.")
                if not bot_state:
                    debug("bot_state is None; recovery cannot track or restart task.")
            return False
        finally:
            # Stop the display thread
            display_thread.do_run = False
            display_thread.join()
        

class Recovery:
                  
    def __init__(self, player_input: Optional[PlayerInput] = None):
        self.player_input = player_input
        self.ocr = player_input.ocr if player_input else OCR()

    def _text_present(self, region: Optional[Tuple[int,int,int,int]], expected_texts: Optional[List[str]]) -> bool:
        if not region or not expected_texts:
            return False
        try:
            text = self.ocr.recognize_text(region)
            cleaned = text.replace(' ', '').replace('\n', '').replace('\r', '').upper()
            for t in expected_texts:
                if t.upper() in cleaned:
                    return True
        except Exception:
            pass
        return False

    def reset_player(self, bot_state: Optional[BotState] = None) -> bool:
        """Minimal recovery: close inventory if open, calibrate view, and resume task."""
        pi = self.player_input
        if not pi:
            warn("Recovery: player_input not set; cannot perform UI checks. Assuming success.")
            return True

        # Only close inventory if open
        own_inv_open = self._text_present(pi.own_inv_scan, pi.inv_text)
        tp_inv_open  = self._text_present(pi.tp_inv_scan, pi.tp_inv_text)
        if own_inv_open or tp_inv_open:
            debug("Recovery: Inventory detected open; pressing ESC to close.")
            pyautogui.press('esc')
            time.sleep(0.2)
            # Optionally recheck and press again if still open
            own_inv_open = self._text_present(pi.own_inv_scan, pi.inv_text)
            tp_inv_open  = self._text_present(pi.tp_inv_scan, pi.tp_inv_text)
            if own_inv_open or tp_inv_open:
                debug("Recovery: Inventory still open after ESC; pressing ESC again.")
                pyautogui.press('esc')
                time.sleep(0.2)

        # Calibrate view
        try:
            self.player_input.calibrate_current_view(bot_state)
        except Exception as e:
            debug(f"Recovery: calibrate_current_view failed: {e}")
        return True

    def proceed_post_reset(self, bot_state: BotState) -> bool:
        """No-op: post-reset flow is now minimal."""
        return True

    def acquire_teleporter(self, bot_state: BotState, attempts: int = 8, horiz_step: int = 120) -> bool:
        """Attempt to make teleporter text visible.

        Strategy:
        1. Check current view.
        2. Direct look_at(tp) if calibration exists.
        3. Perform left/right horizontal sweeps updating approximate yaw until teleporter text appears.
           Yaw adjustment is heuristic based on degree_to_pixel_factor.

        Returns True if teleporter text detected, else False.
        """
        if not self.player_input:
            return False
        pi = self.player_input
        # Helper to test presence
        def visible():
            return self._text_present(pi.tp_scan, pi.tp_text)
        # Immediate check
        if visible():
            return True
        # Direct look using calibration
        if pi.tp:
            debug("acquire_teleporter: direct look_at(tp) attempt")
            pi.look_at(pi.tp, bot_state)
            time.sleep(0.15)
            if visible():
                return True
        # Optional nudge calibration attempt
        if getattr(pi, 'tp_nudge', None):
            debug("acquire_teleporter: using tp_nudge calibration once")
            pi.look_at(pi.tp_nudge, bot_state)
            time.sleep(0.15)
            if visible():
                return True
            # Return to tp again
            if pi.tp:
                pi.look_at(pi.tp, bot_state)
                time.sleep(0.15)
                if visible():
                    return True
        # Horizontal sweep search
        debug("acquire_teleporter: starting horizontal sweep search")
        direction = 1
        for i in range(attempts):
            pi.move_mouse_relative(horiz_step * direction, 0)
            # Heuristic update of yaw in bot_state
            if bot_state.view_direction:
                yaw, pitch = bot_state.view_direction
                # inverse of conversion in look_at: pixels * (degrees per pixel) where degrees per pixel ~= factor_x?
                # look_at used dx_pix = int(dx_deg / factor_x) => dx_deg ≈ dx_pix * factor_x
                yaw += (horiz_step * direction) / pi.degree_to_pixel_factor_x
                bot_state.view_direction = (yaw, pitch)
            time.sleep(0.12)
            if visible():
                debug(f"acquire_teleporter: teleporter detected during sweep (step {i}, dir {direction}).")
                return True
            # Alternate direction to fan outward
            direction *= -1
        warn("acquire_teleporter: teleporter not found after sweeps")
        return False

    
    def option1(self, bot_state: BotState) -> bool:
        """No-op: option1 is now unused."""
        return True

    def option2(self, bot_state: BotState) -> bool:
        """No-op: option2 is now unused."""
        return True


class RecoveryOld:
                  
    def __init__(self, player_input: Optional[PlayerInput] = None):
        self.player_input = player_input
        self.ocr = player_input.ocr if player_input else OCR()

    def _text_present_old(self, region: Optional[Tuple[int,int,int,int]], expected_texts: Optional[List[str]]) -> bool:
        if not region or not expected_texts:
            return False
        try:
            text = self.ocr.recognize_text(region)
            cleaned = text.replace(' ', '').replace('\n', '').replace('\r', '').upper()
            for t in expected_texts:
                if t.upper() in cleaned:
                    return True
        except Exception:
            pass
        return False

    def reset_player_old(self, bot_state: Optional[BotState] = None) -> bool:
        """Ensure no inventory UI is open; press ESC if needed, then recheck.

        Logic:
        - Detect if either own inventory or teleporter inventory text is visible.
        - If visible, press ESC and recheck once.
        - When neither is visible, proceed with post-reset flow (calibrate + teleporter branch).
        """
        pi = self.player_input
        if not pi:
            warn("Recovery: player_input not set; cannot perform UI checks. Assuming success.")
            return True

        own_inv_open = self._text_present(pi.own_inv_scan, pi.inv_text)
        tp_inv_open  = self._text_present(pi.tp_inv_scan, pi.tp_inv_text)
        if not own_inv_open and not tp_inv_open:
            debug("Recovery: No inventory detected; proceeding with post-reset flow.")
            try:
                if bot_state is not None:
                    bot_state.inventory_open = False
                    bot_state.inventory_type = None
            except Exception:
                pass
            return self.proceed_post_reset(bot_state) if bot_state is not None else True

        debug("Recovery: Inventory detected; pressing ESC to close.")
        pyautogui.press('esc')
        time.sleep(0.2)

        own_inv_open = self._text_present(pi.own_inv_scan, pi.inv_text)
        tp_inv_open  = self._text_present(pi.tp_inv_scan, pi.tp_inv_text)
        if not own_inv_open and not tp_inv_open:
            debug("Recovery: Inventory closed; proceeding with post-reset flow.")
            try:
                if bot_state is not None:
                    bot_state.inventory_open = False
                    bot_state.inventory_type = None
            except Exception:
                pass
            return self.proceed_post_reset(bot_state) if bot_state is not None else True
        
        debug("Recovery: Inventory still detected; pressing ESC again.")
        pyautogui.press('esc')
        time.sleep(0.2)

        own_inv_open = self._text_present(pi.own_inv_scan, pi.inv_text)
        tp_inv_open  = self._text_present(pi.tp_inv_scan, pi.tp_inv_text)
        if not own_inv_open and not tp_inv_open:
            debug("Recovery: Inventory closed; proceeding with post-reset flow.")
            try:
                if bot_state is not None:
                    bot_state.inventory_open = False
                    bot_state.inventory_type = None
            except Exception:
                pass
            return self.proceed_post_reset(bot_state) if bot_state is not None else True

        debug("Recovery: Inventory still open after ESC.")
        try:
            if bot_state is not None:
                bot_state.inventory_open = True
                bot_state.inventory_type = bot_state.inventory_type or 'structure:unknown'
        except Exception:
            pass
        return False

    def proceed_post_reset_old(self, bot_state: BotState) -> bool:
        """After reset, calibrate view, look at teleporter, and branch based on visibility."""
        if not self.player_input:
            return True
        # If currently crouching, uncrouch to ensure consistent post-reset movement/look
        try:
            if bool(getattr(bot_state, 'is_crouching', False)):
                debug("Recovery: Uncrouching before post-reset procedures.")
                self.player_input.crouch(bot_state)
                time.sleep(0.2)
        except Exception:
            # If uncrouch fails, continue with recovery flow anyway
            pass
        # Ensure inventory flags reflect closed state after recovery
        try:
            if bot_state is not None:
                bot_state.inventory_open = False
                bot_state.inventory_type = None
        except Exception:
            pass
        # Calibrate current view
        self.player_input.calibrate_current_view(bot_state)
        # Look at teleporter target
        self.player_input.look_at(self.player_input.tp, bot_state)
        # Try to acquire teleporter visibility (direct + scanning if needed)
        if self.acquire_teleporter(bot_state):
            debug("Recovery: Teleporter acquired; proceeding with option1.")
            return #self.option1(bot_state)
        else:
            debug("Recovery: Teleporter still not visible after scan; proceeding with option2.")
            return self.option2(bot_state)

    def acquire_teleporter_old(self, bot_state: BotState, attempts: int = 8, horiz_step: int = 120) -> bool:
        """Attempt to make teleporter text visible.

        Strategy:
        1. Check current view.
        2. Direct look_at(tp) if calibration exists.
        3. Perform left/right horizontal sweeps updating approximate yaw until teleporter text appears.
           Yaw adjustment is heuristic based on degree_to_pixel_factor.

        Returns True if teleporter text detected, else False.
        """
        if not self.player_input:
            return False
        pi = self.player_input
        # Helper to test presence
        def visible():
            return self._text_present(pi.tp_scan, pi.tp_text)
        # Immediate check
        if visible():
            return True
        # Direct look using calibration
        if pi.tp:
            debug("acquire_teleporter: direct look_at(tp) attempt")
            pi.look_at(pi.tp, bot_state)
            time.sleep(0.15)
            if visible():
                return True
        # Optional nudge calibration attempt
        if getattr(pi, 'tp_nudge', None):
            debug("acquire_teleporter: using tp_nudge calibration once")
            pi.look_at(pi.tp_nudge, bot_state)
            time.sleep(0.15)
            if visible():
                return True
            # Return to tp again
            if pi.tp:
                pi.look_at(pi.tp, bot_state)
                time.sleep(0.15)
                if visible():
                    return True
        # Horizontal sweep search
        debug("acquire_teleporter: starting horizontal sweep search")
        direction = 1
        for i in range(attempts):
            pi.move_mouse_relative(horiz_step * direction, 0)
            # Heuristic update of yaw in bot_state
            if bot_state.view_direction:
                yaw, pitch = bot_state.view_direction
                # inverse of conversion in look_at: pixels * (degrees per pixel) where degrees per pixel ~= factor_x?
                # look_at used dx_pix = int(dx_deg / factor_x) => dx_deg ≈ dx_pix * factor_x
                yaw += (horiz_step * direction) / pi.degree_to_pixel_factor_x
                bot_state.view_direction = (yaw, pitch)
            time.sleep(0.12)
            if visible():
                debug(f"acquire_teleporter: teleporter detected during sweep (step {i}, dir {direction}).")
                return True
            # Alternate direction to fan outward
            direction *= -1
        warn("acquire_teleporter: teleporter not found after sweeps")
        return False

    
    def option1_old(self, bot_state: BotState) -> bool:
        """Teleporter visible: go to bed, wake up, return to last teleporter, and proceed."""
        if not self.player_input:
            return False
        # Snapshot last known destination BEFORE going to bed
        previous_destination = bot_state.position
        # Go to bed
        if not self.player_input.go_to_bed(bot_state):
            error("Recovery option1: go_to_bed failed.")
            return False
        # Wait and wake up
        time.sleep(2)
        if not self.player_input.wake_up(bot_state, settle_seconds=0.7):
            error("Recovery option1: wake_up failed.")
            return False
        # Teleport back to the last known teleporter/position before failure
        last_dest = previous_destination
        if last_dest:
            try:
                self.player_input.teleport_to(last_dest, bot_state)
            except Exception as e:
                error(f"Recovery option1: teleport back to '{last_dest}' failed: {e}")
                return False
        else:
            debug("Recovery option1: no last destination recorded; skipping teleport back.")
        return True

    def option2_old(self, bot_state: BotState) -> bool:
        """Placeholder for post-reset branch when teleporter is not visible."""
        return True
class TaskExecutor:
    """Executes ordered tasks and verifies completion."""
    def execute_task(self, task):
        debug(f"Executing task: {task}")
        # Dummy: Simulate task execution and verification
        return True
    def verify_task(self, task):
        debug(f"Verifying task: {task}")
        return True
    def recover_if_failed(self):
        debug("Recovering from failure...")
        return True
