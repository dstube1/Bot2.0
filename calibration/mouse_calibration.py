import time
import ctypes
import pyperclip
import keyboard  # To detect key presses
from pynput.keyboard import Key, Controller
import configparser


keyboard_controller = Controller()

# Load configuration
config = configparser.ConfigParser()
config.read("config.ini")


def move_mouse_relative(dx: int, dy: int) -> None:
    """
    Moves the mouse dx to the right/left and dy up/down from the current position.
    """
    ctypes.windll.user32.mouse_event(0x0001, dx, dy, 0, 0)  # 0x0001 = MOUSEEVENTF_MOVE


def press_key(key: str, hold_time=0):
    """
    Presses a key and holds it for hold_time
    """
    special_keys = {
        'backspace': Key.backspace,
        'enter': Key.enter,
        'esc': Key.esc,
        'space': Key.space,
        'left': Key.left,
        'up': Key.up,
        'right': Key.right,
        'down': Key.down,
        'tab': Key.tab
    }
    
    key_to_press = special_keys.get(key.lower(), key)
    
    keyboard_controller.press(key_to_press)
    if hold_time > 0:
        time.sleep(hold_time)
    keyboard_controller.release(key_to_press)


def get_roll_and_pitch():
    """
    Extracts the pitch and roll (yaw) values from the clipboard data.
    
    Returns:
        tuple: (roll, pitch) as floats.
    """
    press_key('tab')
    time.sleep(2)
    press_key('c')
    time.sleep(0.2)
    press_key('c')
    time.sleep(0.2)
    press_key('c')
    time.sleep(0.2)
    press_key('enter')
    time.sleep(1)
    
    try:
        # Get the clipboard data
        clipboard_data = pyperclip.paste()
        print(f"Clipboard data: {clipboard_data}")  # Debugging: Print the clipboard data
        
        # Extract roll and pitch from the clipboard data
        pitch_str = clipboard_data.split()[-1]
        roll_str = clipboard_data.split()[-2]
        
        # Convert strings to floats
        pitch = float(pitch_str)
        roll = float(roll_str)
        print(f"Roll: {roll}, Pitch: {pitch}")
        return roll, pitch
    
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None

def test_mouse_movement(dx: int, dy: int):
    """
    Tests how moving the mouse affects the roll and pitch in-game.
    
    Args:
        dx (int): The amount to move the mouse horizontally (right/left).
        dy (int): The amount to move the mouse vertically (up/down).
    """
    print("\nCapturing initial roll and pitch...")
    initial_roll, initial_pitch = get_roll_and_pitch()
    
    if initial_roll is None or initial_pitch is None:
        print("Failed to capture initial roll and pitch.")
        return

    print(f"Moving mouse by dx={dx}, dy={dy}...")
    move_mouse_relative(dx, dy)
    time.sleep(1)  # Wait for the game to process the view change

    print("Capturing new roll and pitch...")
    new_roll, new_pitch = get_roll_and_pitch()
    time.sleep(1)

    if new_roll is None or new_pitch is None:
        print("Failed to capture new roll and pitch.")
        return
    time.sleep(1)
    # Calculate the change
    roll_change = new_roll - initial_roll
    pitch_change = new_pitch - initial_pitch

    print(f"Roll change: {roll_change} degrees")
    print(f"Pitch change: {pitch_change} degrees")
    
    # Sensitivity estimation
    if dx != 0:
        yaw_sensitivity = abs(roll_change / dx)
        print(f"Estimated Yaw Sensitivity: {yaw_sensitivity} degrees per pixel")
        
    if dy != 0:
        pitch_sensitivity = abs(pitch_change / dy)
        print(f"Estimated Pitch Sensitivity: {pitch_sensitivity} degrees per pixel")

    return round(yaw_sensitivity, 5), round(-pitch_sensitivity, 5)

def save_config(sensitivity):
    yaw_sensitivity, pitch_sensitivity = sensitivity  # Unpack the tuple

    if 'CCC_CONVERSION' not in config.sections():
        config.add_section('CCC_CONVERSION')
    
    # Format as "yaw,pitch"
    sensitivity_str = f"{yaw_sensitivity},{pitch_sensitivity}"
    
    config.set('CCC_CONVERSION', 'conversion', sensitivity_str)
    
    with open('config.ini', 'w') as configfile:
        config.write(configfile)
    
    print("Saved CCC_CONVERSION to config.ini")



def main():
    dx = 500 # Horizontal mouse movement in pixels
    dy = 500  # Vertical mouse movement in pixels (negative to move up)

    print("Press 'P' to perform the test. Press 'Esc' to exit.")
    while True:
        if keyboard.is_pressed('p'):
            test_mouse_movement(dx, dy)
            sensitivity = test_mouse_movement(-dx, -dy)
            save_config(sensitivity)
            time.sleep(1)  # Prevent accidental double triggering due to key holding
        
        if keyboard.is_pressed('esc'):
            print("Exiting the program.")
            break

# Run the main loop
main()

###! ADD TO CONFIG.JSON ###