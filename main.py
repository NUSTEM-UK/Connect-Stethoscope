"""Pico pinout diagram:

 GP00 (available)   1       40  VBUS (5V, from USB: SERVO +)
 GP01 (available)   2       39  VSYS
              GND   3       38  GND
 GP02  (SERVO D5)   4       37  3V3EN
 GP03  (SERVO D7)   5       36  3V3  ROTARY ENCODER 3V3 (red)
 GP04  (SERVO 03)   6       35  ADC VREF (do not use)
 GP05  (SERVO 04)   7       34  GP28 ADC2 (available)
              GND   8       33  GND
    DISPLAY LED_R   9       32  GP27 (available)
    DISPLAY LED_G  10       31  GP26 ROTARY ENCODER BUTTON (orange)
         UART1 TX  11       30  DISPLAY LCD_RESET
         UART1 RX  12       29  GP22 ROTARY ENCODER DT (yellow)
              GND  13       28  GND  ROTARY ENCODER GND (brown)
 GP10 (available)  14       27  GP21 ROTARY ENCODER CLK (green)
 GP11 (available)  15       26  DISPLAY BL_EN
    DISPLAY SW_A   16       25  SPI0 DISPLAY LCD_MOSI
    DISPLAY SW_B   17       24  SPI0 DISPLAY LCD_SCLK
              GND  18       23  GND
    DISPLAY SW_X   19       22  SPI0 DISPLAY LCD_CS
    DISPLAY SW_Y   20       21  SPI0 DISPLAY LCD_DC

Total power supply on pin 36: <300 mA. Stall current of a microservo is ~500 mA, so... oops.

"""

import utime
from machine import Pin
from pimoroni import Button
from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY
# import picodisplay as display # DONE: Update to PicoGraphics
from rotary_irq_rp2 import RotaryIRQ
from servo_controller import ServoController

# Set up and initialise Pico Display
# DONE: This won't work for PicoGraphics, there's a different way around.
display = PicoGraphics(display=DISPLAY_PICO_DISPLAY, rotate=0)
# buf = bytearray(display.get_width() * display.get_height() * 2)
# display.init(buf)
display.set_backlight(0.8)

# Set up colours
white = display.create_pen(255, 255, 255)
black = display.create_pen(0, 0, 0)
red = display.create_pen(255, 0, 0)
green = display.create_pen(0, 255, 0)
blue = display.create_pen(0, 0, 255)
yellow = display.create_pen(255, 255, 0)
cyan = display.create_pen(0, 255, 255)
magenta = display.create_pen(255, 0, 255)
dark_grey = display.create_pen(70, 70, 70)

# Set up buttons
button_a = Button(12)
button_b = Button(13)
button_x = Button(14)
button_y = Button(15)

# Display mode
display_mode = 1 # Default


def increment_application_mode():
    """Loops through application modes."""
    global display_mode
    display_mode += 1
    if display_mode > 1:
        display_mode = 0


class PinButton:
    """Wrap an input Pin in button accessor methods."""

    def __init__(self, pin, pullup=False):
        self._pin = pin
        self._pullup = pullup
        self._button = Pin(pin, Pin.IN, Pin.PULL_UP if self._pullup else Pin.PULL_DOWN)

    def value(self):
        return self._button.value()

    def is_pressed(self):
        if self._pullup:
            return self.value() == 0
        else:
            return self.value() == 1

class ButtonController:
    """Poll buttons and dispatch events.

    Takes a mapping dictionary of buttons, objects and method calls.
    Polls the buttons and calls the appropriate method on the object.
    Could instantiate a ButtonController object per menu mode.
    """

    def __init__(self, mapping, debounce_interval=500):
        """Initialise the controller."""
        self._mapping = mapping
        self.debounce_interval = debounce_interval
        self._time_last_checked = utime.ticks_ms()

    def check(self):
        """Check the buttons and call the appropriate method."""
        # Check for button presses
        for button in self._mapping:
            if button.is_pressed and utime.ticks_diff(utime.ticks_ms(), self._time_last_checked) > self.debounce_interval:
                self._time_last_checked = utime.ticks_ms()
                # Have to use getattr here for dynamic method call
                getattr(self._mapping[button]['object'], self._mapping[button]['method'])()


class PinButtonController:
    """Lazy duplicate of ButtonController to avoid dependency on display."""

    def __init__(self, mapping, debounce_interval=500):
        """Initialise the controller."""
        self._mapping = mapping
        self.debounce_interval = debounce_interval
        self._time_last_checked = utime.ticks_ms()

    def check(self):
        """Check the buttons and call the appropriate method."""
        # Check for button presses
        for button in self._mapping:
            # DONE: Gaah, it doesn't look like is_pressed() exists in the new PicoGraphics/PicoDisplay library?!
            #        Oh, but there is a Button class in pimoroni module (https://github.com/pimoroni/pimoroni-pico/blob/main/micropython/modules_py/pimoroni.py)
            #        ...and that does have is_pressed().
            # Correction: has Button.is_pressed, it's a property not a call.
            # 2023-03-29 OK, we've built our own button controller, so this next line _does_ have a called to is_pressed()
            # rather than a check of the is_pressed property. We should bring these two approaches back in line, this
            # is messy.
            if button.is_pressed() and utime.ticks_diff(utime.ticks_ms(), self._time_last_checked) > self.debounce_interval:
                self._time_last_checked = utime.ticks_ms()
                # Have to use getattr here for dynamic method call
                getattr(self._mapping[button]['object'], self._mapping[button]['method'])()


class ApplicationController:
    """Handle application state changes."""

    def __init__(self, object_list, menu_list, display, colors, application_state=0, num_states=3):
        """Initialise the controller.

        Default to the upper servo view (application state 1)."""
        self.application_state = application_state
        self._object_list = object_list
        self._num_states = num_states
        self._menu_list = menu_list
        self._display = display
        self._colors = colors
        # Update devices to force correct drawing.
        self._handle_state_change()

    def increment_state(self):
        """Cycle application state."""
        self.application_state += 1
        if self.application_state > (self._num_states - 1):
            self.application_state = 0
        self._handle_state_change()

    def _handle_state_change(self):
        """Update application state.

        Application logic goes here."""
        if self.application_state == 0:
            for thing in self._object_list:
                thing.display_small()
                thing.run()
        elif self.application_state == 1:
            for thing in self._object_list:
                thing.stop()
            self._object_list[0].display_full()
        elif self.application_state == 2:
            for thing in self._object_list:
                thing.stop()
            self._object_list[1].display_full()

    def update(self):
        if self.application_state == 0:
            self._menu_list[0].check()
            for thing in self._object_list:
                thing.update()
                thing.draw(self._display, self._colors)
        elif self.application_state == 1:
            self._menu_list[1].check()
            self._object_list[0].update()
            self._object_list[0].draw(self._display, self._colors)
        elif self.application_state == 2:
            self._menu_list[2].check()
            self._object_list[1].update()
            self._object_list[1].draw(self._display, self._colors)

class RotaryController():
    """Read rotary encoder value and dispatch accordingly.

    Takes a mapping dictionary of servo objects and method calls.
    Polls the encoder and calls the appropriate method on the object.
    """

    def __init__(self, mapping, debounce_interval=60):
        """Initialize the controller."""
        self._mapping = mapping
        self._debounce_interval = debounce_interval
        self._time_last_checked = utime.ticks_ms()

        self._r = RotaryIRQ(pin_num_clk=21,
              pin_num_dt=22,
              min_val=-5000,
              max_val=+5000,
              reverse=False,
              range_mode=RotaryIRQ.RANGE_WRAP, # set wrap, as range starts at min_val
              pull_up=False,
              half_step=True)

        self._old_value = self._r.value()
        self._new_value = self._r.value()

    def check(self):
        """Check the rotary encoder value and dispatch accordingly."""

        if utime.ticks_diff(utime.ticks_ms(), self._time_last_checked) > self._debounce_interval:
            self._time_last_checked = utime.ticks_ms()
            self._new_value = self._r.value()
            if self._new_value > self._old_value:
                self._old_value = self._new_value
                for object in self._mapping:
                    getattr(object, self._mapping[object]['inc_method'])()
                    # print("Incrementing")
                    # print(object, self._mapping[object]['inc_method'])
            if self._new_value < self._old_value:
                self._old_value = self._new_value
                for object in self._mapping:
                    # Note the (): you still have to call the method once you've found it.
                    getattr(object, self._mapping[object]['dec_method'])()
                    # print("Decrementing")


if __name__ == '__main__':
    print("Starting...")

    # Create colors dictionary for ServoController
    colors = {
        'white': white,
        'black': black,
        'red': red,
        'green': green,
        'blue': blue,
        'yellow': yellow,
        'cyan': cyan,
        'magenta': magenta,
        'dark_grey': dark_grey
    }

    servoD5 = ServoController(2)
    servoD7 = ServoController(pin=3, speed=60, vertical_offset=90, marker=down_arrow, marker_offset=-25)

    # For some reason, we need to draw everything once, or the methods error out in the loop. weird.
    display.set_pen(black)
    display.clear()
    servoD5.draw(display, colors)
    servoD7.draw(display, colors)
    display.update()

    application_mode = 0       # Default animation playback mode


    # Setting up callbacks for buttons and rotary encoder.
    # This is for the main screen: later modes will pass their own sets here.
    # DONE : Buttons are now handled by the Button module, so this will need to be updated.
    #        Suspect we'll have to instantiate each Button object first, since it isn't predeclared in the
    #        display module now.
    button_mapping_main = {
        button_a: {
            "object": servoD5, "method": "min_position_setting_toggle" },
        button_x: {
            "object": servoD5, "method": "max_position_setting_toggle" },
        button_b: {
            "object": servoD7, "method": "min_position_setting_toggle" },
        button_y: {
            "object": servoD7, "method": "max_position_setting_toggle" }
    }

    button_mapping_servoD5 = {
        button_a: {
            "object": servoD5, "method": "position_and_min_setting_toggle" },
        button_x: {
            "object": servoD5, "method": "position_and_max_setting_toggle" },
        button_b: {
            "object": servoD5, "method": "speed_setting_toggle" },
        button_y: {
            "object": servoD5, "method": "toggle_run" }
    }

    button_mapping_servoD7 = {
        button_a: {
            "object": servoD7, "method": "speed_setting_toggle" },
        button_x: {
            "object": servoD7, "method": "toggle_run" },
        button_b: {
            "object": servoD7, "method": "position_and_min_setting_toggle" },
        button_y: {
            "object": servoD7, "method": "position_and_max_setting_toggle" }
    }

    # TODO: Feels like this should be some sort of indexed data structure, rather than discrete objects.
    buttons0 = ButtonController(button_mapping_main)
    buttons1 = ButtonController(button_mapping_servoD5)
    buttons2 = ButtonController(button_mapping_servoD7)

    # TODO: Look! Look! We're even passing a tuple of the objects into ApplicationController!
    app = ApplicationController((servoD5, servoD7), (buttons0, buttons1, buttons2), display, colors, 0, 3)

    # Rotary encoder button
    # Shorts to ground when pressed
    # Have to do this outside of app, because I can't work out how to pass
    # a reference to parent in button mapping, without weakrefs.
    # There'll be a way. Meh.
    app_control_button = PinButton(26, True)
    control_button_mapping = {
        app_control_button: {
            "object": app, "method": "increment_state" } }
    app_control_button_controller = PinButtonController(control_button_mapping)

    rotary_mapping_main = {
        servoD5: {
            "inc_method": "increment_value",
            "dec_method": "decrement_value"
        },
        servoD7: {
            "inc_method": "increment_value",
            "dec_method": "decrement_value"
        }
    }
    rotary = RotaryController(rotary_mapping_main)

    while True:
        # DONE: This will change
        display.set_pen(black)
        display.clear()
        # servoD5.draw()
        # servoD7.draw()

        # servoD5.update()
        # servoD7.update()

        rotary.check()
        app_control_button_controller.check()
        app.update()
        # DONE: This will change
        display.update()

        # utime.sleep_ms(20)

