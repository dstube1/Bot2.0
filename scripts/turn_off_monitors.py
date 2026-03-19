import ctypes
import keyboard

# Windows API call to turn off the monitor
def turn_off_monitors():
    HWND_BROADCAST = 0xFFFF
    WM_SYSCOMMAND = 0x0112
    SC_MONITORPOWER = 0xF170
    # 2 = power off, 1 = power on, -1 = power on
    ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2)

print("Press F3 to turn off all monitors. Move mouse or press a key to turn them back on.")
keyboard.add_hotkey('F3', turn_off_monitors)
keyboard.wait()