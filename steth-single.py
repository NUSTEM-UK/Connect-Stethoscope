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
from servo import Servo
import picodisplay as display
from rotary_irq_rp2 import RotaryIRQ

# Set up and initialise Pico Display
buf = bytearray(display.get_width() * display.get_height() * 2)
display.init(buf)
display.set_backlight(0.8)

# Borrowed from Tony Goodhew's PicoDisplay example code
up_arrow =[0,4,14,21,4,4,0,0]
down_arrow = [0,4,4,21,14,4,0,0]
bits = [128,64,32,16,8,4,2,1]  # Powers of 2

# Display mode
display_mode = 0 # Default

# Print defined character from set above
def draw_char(xpos, ypos, pattern):
    for line in range(8):  # 5x8 characters
        for ii in range(5): # Low value bits only
            i = ii + 3
            dot = pattern[line] & bits[i] # Extract bit
            if dot: # print white dots
                display.pixel(xpos+i*2, ypos+line*2)
                display.pixel(xpos+i*2, ypos+line*2+1)
                display.pixel(xpos+i*2+1, ypos+line*2)
                display.pixel(xpos+i*2+1, ypos+line*2+1)


def rescale(x, in_min, in_max, out_min, out_max):
    """Rescale a value from one range to another."""
    # print(x, in_min, in_max, out_min, out_max)
    # Check for range zero
    if in_max - in_min == 0:
        print("RESCALE: Caught a divide by zero.")
        return out_min
    else:
        return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)


def zfl(s, width=3, padchar='0'):
    """Pads string with leading zeros.

    From https://stackoverflow.com/questions/63271522/is-there-a-zfill-type-function-in-micro-python-zfill-in-micro-python
    then extended for variable fill character. There's no zfill() in Micropython, so... here we are."""
    # return '{:0>{w}}'.format(s, w=width)
    return '{:{p}>{w}}'.format(s, w=width, p=padchar)


def increment_application_mode():
    """Loops through application modes."""
    global display_mode
    display_mode += 1
    if display_mode > 1:
        display_mode = 0


class ServoController:
    """Visual and serial interface for servo control.
    """

    def __init__(self, pin, angle=90, speed=20, vertical_offset=25, marker=up_arrow, marker_offset=0):
        """Initialise the controller, with vaguely sane defaults."""
        self._servo = Servo(pin)
        self.angle = angle
        self.speed = speed
        self.vertical_offset = vertical_offset
        self.marker = marker
        self.marker_offset = marker_offset

        # TODO: I don't think @property/getter/setter decorators work
        #       in Micropython, so it's a pain to do input validation.
        #       But equally, I can't find any documentation on this. Sigh.

        self.min_angle = 90
        self.max_angle = 90

        self._min_display_position = 0
        self._max_display_position = 180

        self._reversing = False
        self.display_mode = 0   # 'normal'

        # Booleans to determine pen colour for drawing values
        self.min_position_being_updated = False
        self.max_position_being_updated = False
        self.position_being_updated = False
        self.speed_being_updated = False
        self.is_selected = False
        self.is_running = False

        # Set a time reference
        self._time_ref = utime.ticks_ms()

    def draw(self):
        """Draw the servo on the display.

        Also, write position to servo."""

        # Are we selected? if so, draw a background
        if self.is_selected:
            display.set_pen(70, 70, 70)
            display.rectangle(0, self.vertical_offset - 20, 240, self.vertical_offset + 20)

        # Display minimum angle
        # Set pen colour to green if being updated, else yellow
        display.set_pen(0, 255, 0) if self.min_position_being_updated else display.set_pen(255, 255, 0)
        display.text(zfl(str(self.min_angle), 3), 10, self.vertical_offset, 200, 2)
        # printstring(zfl(str(self.min_angle), 3), 10, self.vertical_offset, 1, False, False)

        # Display maximum angle
        display.set_pen(0, 255, 0) if self.max_position_being_updated else display.set_pen(255, 255, 0)
        display.text(zfl(str(self.max_angle), 3), 200, self.vertical_offset, 200, 2)

        # Draw scale line
        display.set_pen(255, 255, 255)
        display.rectangle(50, self.vertical_offset + 6, 140, 2)
        # display.pixel_span(50, self.vertical_offset + 6, 140)
        # display.pixel_span(50, self.vertical_offset + 7, 140)
        # display.update()

        # Draw movement end tic marks
        self._tick_min = rescale(self.min_angle, 0, 180, 50, 140 + 50)
        self._tick_max = rescale(self.max_angle, 0, 180, 50, 140 + 50)
        display.rectangle(self._tick_min, self.vertical_offset + 2, 2, 10)
        display.rectangle(self._tick_max, self.vertical_offset + 2, 2, 10)

        # Draw position marker
        self._marker_pos = rescale(self.angle, 0, 180, 50, 140 + 50) - 10
        display.set_pen(255, 0, 0)
        # I don't know why this print is necessary, but without it the code blows up after a very short time.
        # print(self._marker_pos, self.vertical_offset + 13 + self.marker_offset)
        draw_char(self._marker_pos, self.vertical_offset + 13 + self.marker_offset, self.marker)
        # Update physical servo position, correcting for angle range
        # self._servo.value((self.angle + 90) % 180)
        # self._servo.value(rescale(self.angle, -90, 90, 0, 180))

        if self.display_mode == 1:
            # Display speed data
            if self.vertical_offset == 90:
                # Display speed by other button
                display.set_pen(0, 255, 0) if self.speed_being_updated else display.set_pen(255, 255, 0)
                display.text(zfl(str(self.speed), 3) + " SPD", 10, 20, 200, 2)
                # DIsplay current angle in centre space
                display.set_pen(0, 255, 0) if self.position_being_updated else display.set_pen(255, 255, 0)
                display.text(zfl(str(int(self.angle)), 3), 95, 45, 200, 4)
                # Display RUN/STOP text
                if self.is_running:
                    display.set_pen(255, 0, 0)
                    display.text("STOP", 190, 25, 200, 2)
                else:
                    display.set_pen(0, 255, 0)
                    display.text(" RUN", 190, 25, 200, 2)
            else:
                # Display speed setting by lower-left button
                display.set_pen(0, 255, 0) if self.speed_being_updated else display.set_pen(255, 255, 0)
                display.text(zfl(str(self.speed), 3) + " SPD", 10, self.vertical_offset + 75, 200, 2)
                # Display current angle in centre space
                display.set_pen(0, 255, 0) if self.position_being_updated else display.set_pen(255, 255, 0)
                display.text(zfl(str(int(self.angle)), 3), 95, self.vertical_offset + 35, 200, 4)
                # Display RUN/STOP legend by lower right button
                if self.is_running:
                    display.set_pen(255, 0, 0)
                    display.text("STOP", 190, self.vertical_offset + 75, 200, 2)
                else:
                    display.set_pen(0, 255, 0)
                    display.text(" RUN", 190, self.vertical_offset + 75, 200, 2)


    def move(self):
        """Move the servo to the current position."""
        # self._servo.value(rescale(self.angle, 0, 180, -90, 90))
        self._servo.value(int(self.angle - 90))
        # self._servo.value(self.angle - 90)

    def min_position_setting_toggle(self):
        self.min_position_being_updated = not self.min_position_being_updated
        # Deselect the other thing if appropriate
        if self.min_position_being_updated:
            self.max_position_being_updated = False
            self.speed_being_updated = False
            self.stop()

    def max_position_setting_toggle(self):
        self.max_position_being_updated = not self.max_position_being_updated
        # Deselect the other thing if appropriate
        if self.max_position_being_updated:
            self.min_position_being_updated = False
            self.speed_being_updated = False
            self.stop()

    def position_and_min_setting_toggle(self):
        self.min_position_being_updated = not self.min_position_being_updated
        self.position_being_updated = self.min_position_being_updated
        self.angle = self.min_angle
        if self.min_position_being_updated:
            self.max_position_being_updated = False
            self.speed_being_updated = False

    def position_and_max_setting_toggle(self):
        self.max_position_being_updated = not self.max_position_being_updated
        self.position_being_updated = self.max_position_being_updated
        self.angle = self.max_angle
        if self.max_position_being_updated:
            self.min_position_being_updated = False
            self.speed_being_updated = False

    def speed_setting_toggle(self):
        self.speed_being_updated = not self.speed_being_updated
        # Deselect the other things if appropriate
        if self.speed_being_updated:
            self.min_position_being_updated = False
            self.max_position_being_updated = False
            self.position_being_updated = False

    def toggle_run(self):
        """Toggle run state."""
        self.is_running = not self.is_running
        self.min_position_being_updated = False
        self.max_position_being_updated = False
        self.position_being_updated = False
        self.speed_being_updated = False

    def run(self):
        """Start, or keep going."""
        self.is_running = True

    def stop(self):
        """Stop, or stay stopped."""
        self.is_running = False

    def display_small(self):
        """Display minimal bar only."""
        self.display_mode = 0

    def display_full(self):
        """Display detailed view."""
        self.display_mode = 1

    def increment_value(self):
        """Increment whatever we're incrementing.

        Keep it within bounds.
        """
        # print(">>> Incrementing")
        if self.min_position_being_updated:
            self.min_angle += 2
            if self.min_angle > 180:
                self.min_angle = 180

        if self.max_position_being_updated:
            self.max_angle += 2
            if self.max_angle > 180:
                self.max_angle = 180

        # if we're moving min and it's > max, increment max also
        if self.min_angle > self.max_angle:
            self.max_angle = self.min_angle

        if self.speed_being_updated:
            self.speed += 2
            if self.speed > 150:
                self.speed = 150

        if self.position_being_updated:
            self.angle += 2
            if self.angle > 180:
                self.angle = 180


        # print(f"[{self.min_angle}, {self.max_angle}]")

    def decrement_value(self):
        """Decrement whatever we're decrementing.

        Keep it within bounds.
        """
        if self.min_position_being_updated:
            self.min_angle -= 2
            if self.min_angle < 0:
                self.min_angle = 0

        if self.max_position_being_updated:
            self.max_angle -= 2
            if self.max_angle < 0:
                self.max_angle = 0

        if self.max_angle < self.min_angle:
            self.min_angle = self.max_angle


        if self.speed_being_updated:
            self.speed -= 1
            if self.speed < 1:
                self.speed = 1

        if self.position_being_updated:
            self.angle -= 2
            if self.angle < 0:
                self.angle = 0


    def update(self):
        """Update the servo position."""

        # Calculate angular movement since last update
        self._time_delta = utime.ticks_diff(utime.ticks_ms(), self._time_ref)
        self._time_ref = utime.ticks_ms()
        self._angle_delta = self.speed * self._time_delta / 1000

        # Update angular position, catching end points
        if self.is_running:
            if self._reversing:
                self.angle -= self._angle_delta
                if self.angle < self.min_angle:
                    self.angle = self.min_angle
                    self._reversing = False
            else:
                self.angle += self._angle_delta
                if self.angle > self.max_angle:
                    self.angle = self.max_angle
                    self._reversing = True

        # Update physical servo position
        self.move()


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
            if display.is_pressed(button) and utime.ticks_diff(utime.ticks_ms(), self._time_last_checked) > self.debounce_interval:
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
            if button.is_pressed() and utime.ticks_diff(utime.ticks_ms(), self._time_last_checked) > self.debounce_interval:
                self._time_last_checked = utime.ticks_ms()
                # Have to use getattr here for dynamic method call
                getattr(self._mapping[button]['object'], self._mapping[button]['method'])()


class ApplicationController:
    """Handle application state changes."""

    def __init__(self, object_list, menu_list, application_state=0, num_states=3):
        """Initialise the controller."""
        self.application_state = application_state
        self._object_list = object_list
        self._num_states = num_states
        self._menu_list = menu_list

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
                thing.draw()
        elif self.application_state == 1:
            self._menu_list[1].check()
            self._object_list[0].update()
            self._object_list[0].draw()
        elif self.application_state == 2:
            self._menu_list[2].check()
            self._object_list[1].update()
            self._object_list[1].draw()

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

    servoD5 = ServoController(2)
    servoD7 = ServoController(pin=3, speed=60, vertical_offset=90, marker=down_arrow, marker_offset=-25)

    # For some reason, we need to draw everything once, or the methods error out in the loop. weird.
    display.set_pen(0, 0, 0)
    display.clear()
    servoD5.draw()
    servoD7.draw()
    display.update()

    application_mode = 0       # Default animation playback mode


    # Setting up callbacks for buttons and rotary encoder.
    # This is for the main screen: later modes will pass their own sets here.
    button_mapping_main = {
        display.BUTTON_A: {
            "object": servoD5, "method": "min_position_setting_toggle" },
        display.BUTTON_X: {
            "object": servoD5, "method": "max_position_setting_toggle" },
        display.BUTTON_B: {
            "object": servoD7, "method": "min_position_setting_toggle" },
        display.BUTTON_Y: {
            "object": servoD7, "method": "max_position_setting_toggle" }
    }

    button_mapping_servoD5 = {
        display.BUTTON_A: {
            "object": servoD5, "method": "position_and_min_setting_toggle" },
        display.BUTTON_X: {
            "object": servoD5, "method": "position_and_max_setting_toggle" },
        display.BUTTON_B: {
            "object": servoD5, "method": "speed_setting_toggle" },
        display.BUTTON_Y: {
            "object": servoD5, "method": "toggle_run" }
    }

    button_mapping_servoD7 = {
        display.BUTTON_A: {
            "object": servoD7, "method": "speed_setting_toggle" },
        display.BUTTON_X: {
            "object": servoD7, "method": "toggle_run" },
        display.BUTTON_B: {
            "object": servoD7, "method": "position_and_min_setting_toggle" },
        display.BUTTON_Y: {
            "object": servoD7, "method": "position_and_max_setting_toggle" }
    }

    buttons0 = ButtonController(button_mapping_main)
    buttons1 = ButtonController(button_mapping_servoD5)
    buttons2 = ButtonController(button_mapping_servoD7)

    app = ApplicationController((servoD5, servoD7), (buttons0, buttons1, buttons2), 0, 3)

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
        display.set_pen(0, 0, 0)
        display.clear()
        # servoD5.draw()
        # servoD7.draw()

        # servoD5.update()
        # servoD7.update()

        rotary.check()
        app_control_button_controller.check()
        app.update()
        display.update()

        # utime.sleep_ms(20)

