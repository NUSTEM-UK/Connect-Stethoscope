"""slosh.py - Servo slosh controller for Connect-Stethoscope.

Moves a single servo between two positions at a configurable amplitude and
frequency. No easing — the servo is commanded directly to each end position
and moves at its own hardware speed.

  Servo positions:  midpoint + 0.5*amplitude  (high)
                    midpoint - 0.5*amplitude  (low)

  servo.value() takes degrees relative to centre: -90 = 0°, 0 = 90°, +90 = 180°
  Midpoint is servo.value(0). High/low are ±(amplitude/2).

Controls:
  Rotary encoder button (GP26) — cycle selection: AMP → FREQ → neither → AMP
  Rotary encoder (CLK=GP21, DT=GP22) — adjust selected parameter
  Button A (GP12, top-left) — toggle RUN / STOP

Display (240×135, left–right split):
  Top-left:  RUN (green) or STOP (red) near button A
  Left half: amplitude value in degrees (green if selected, yellow otherwise)
  Right half: frequency value in Hz (green if selected, yellow otherwise)
  Selected panel has a dark-grey background highlight.

Defaults:  amplitude=0°, frequency=1.0 Hz, running, amplitude selected.
"""

import utime
from machine import Pin
from servo import Servo
from pimoroni import Button
from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY
from rotary_irq_rp2 import RotaryIRQ

# ---------------------------------------------------------------------------
# Hardware setup
# ---------------------------------------------------------------------------

display = PicoGraphics(display=DISPLAY_PICO_DISPLAY, rotate=0)
display.set_backlight(0.8)
WIDTH, HEIGHT = display.get_bounds()   # 240, 135

black     = display.create_pen(0,   0,   0)
yellow    = display.create_pen(255, 255, 0)
green     = display.create_pen(0,   255, 0)
red       = display.create_pen(255, 0,   0)
dark_grey = display.create_pen(40,  40,  40)
white     = display.create_pen(255, 255, 255)

# Button A: top-left edge — RUN/STOP
button_a = Button(12)

# Rotary encoder push-button on GP26, active-low (shorts to GND when pressed)
rotary_button = Pin(26, Pin.IN, Pin.PULL_UP)

# Rotary encoder (same pins as main.py)
rotary = RotaryIRQ(
    pin_num_clk=21,
    pin_num_dt=22,
    min_val=-5000,
    max_val=5000,
    reverse=False,
    range_mode=RotaryIRQ.RANGE_WRAP,
    pull_up=False,
    half_step=True,
)

# Servo on GP2 (D5 position)
servo = Servo(2)

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

amplitude  = 0     # degrees, total swing; range 0–180
frequency  = 1.0   # Hz; range 0.1–5.0; increments of 0.1

# 0 = amplitude selected, 1 = frequency selected, 2 = neither
selection = 0

is_running = True

# Servo oscillation tracking
_at_high        = False
_last_toggle_ms = utime.ticks_ms()

# Input debounce timestamps (start at 0 so first press registers immediately)
_btn_a_last_ms   = 0
_rot_btn_last_ms = 0
_rotary_last_ms  = utime.ticks_ms()
_rotary_old_val  = rotary.value()

ROTARY_DEBOUNCE = 60    # ms between rotary encoder reads
BUTTON_DEBOUNCE = 300   # ms between button presses

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def draw_display():
    """Redraw the full display."""
    display.set_pen(black)
    display.clear()

    # RUN / STOP indicator — top-left, near button A
    if is_running:
        display.set_pen(red)
        display.text("STOP", 5, 5, 80, 2)
    else:
        display.set_pen(green)
        display.text(" RUN", 5, 5, 80, 2)

    # Dividing line between the two panels
    display.set_pen(white)
    display.rectangle(119, 28, 2, HEIGHT - 28)

    # --- Amplitude panel (left half: x 0–118) ---
    if selection == 0:
        display.set_pen(dark_grey)
        display.rectangle(0, 28, 119, HEIGHT - 28)
        # Redraw divider on top of highlight
        display.set_pen(white)
        display.rectangle(119, 28, 2, HEIGHT - 28)

    display.set_pen(green if selection == 0 else yellow)
    display.text("AMP", 15, 33, 100, 2)
    display.text("{:03d}".format(int(amplitude)), 10, 57, 100, 4)
    display.text("deg", 75, 100, 100, 2)

    # --- Frequency panel (right half: x 121–239) ---
    if selection == 1:
        display.set_pen(dark_grey)
        display.rectangle(121, 28, WIDTH - 121, HEIGHT - 28)

    display.set_pen(green if selection == 1 else yellow)
    display.text("FREQ", 130, 33, 110, 2)
    display.text("{:.1f}".format(frequency), 130, 57, 110, 4)
    display.text("Hz", 205, 100, 60, 2)

    display.update()

# ---------------------------------------------------------------------------
# Servo update
# ---------------------------------------------------------------------------

def update_servo():
    """Command the servo to the correct position based on current state."""
    global _at_high, _last_toggle_ms

    if not is_running or amplitude == 0:
        servo.value(0)   # midpoint
        return

    half_period_ms = int(500 / frequency)
    now = utime.ticks_ms()

    if utime.ticks_diff(now, _last_toggle_ms) >= half_period_ms:
        _last_toggle_ms = now
        _at_high = not _at_high
        target = int(amplitude / 2) if _at_high else -int(amplitude / 2)
        servo.value(target)

# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------

def check_button_a():
    """Toggle RUN/STOP on button A press."""
    global is_running, _at_high, _last_toggle_ms, _btn_a_last_ms

    now = utime.ticks_ms()
    if button_a.is_pressed and utime.ticks_diff(now, _btn_a_last_ms) > BUTTON_DEBOUNCE:
        _btn_a_last_ms = now
        is_running = not is_running
        if is_running:
            # Reset oscillation so we don't instantly jump to a stale position
            _at_high = False
            _last_toggle_ms = utime.ticks_ms()
            servo.value(0)


def check_rotary_button():
    """Cycle parameter selection on rotary encoder button press."""
    global selection, _rot_btn_last_ms

    now = utime.ticks_ms()
    if rotary_button.value() == 0 and utime.ticks_diff(now, _rot_btn_last_ms) > BUTTON_DEBOUNCE:
        _rot_btn_last_ms = now
        selection = (selection + 1) % 3


def check_rotary():
    """Adjust the selected parameter when the encoder turns."""
    global amplitude, frequency, _rotary_old_val, _rotary_last_ms

    now = utime.ticks_ms()
    if utime.ticks_diff(now, _rotary_last_ms) < ROTARY_DEBOUNCE:
        return
    _rotary_last_ms = now

    new_val = rotary.value()
    if new_val == _rotary_old_val:
        return

    inc = new_val > _rotary_old_val
    _rotary_old_val = new_val

    if selection == 0:
        amplitude = min(amplitude + 2, 180) if inc else max(amplitude - 2, 0)
    elif selection == 1:
        frequency = round(min(frequency + 0.1, 5.0) if inc else max(frequency - 0.1, 0.1), 1)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print("Slosh starting...")
    servo.value(0)   # move to midpoint immediately
    draw_display()

    while True:
        check_button_a()
        check_rotary_button()
        check_rotary()
        update_servo()
        draw_display()
