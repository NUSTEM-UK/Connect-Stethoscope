"""Servo controller module for Connect-Stethoscope project."""

import utime
from animation import EasedServo
import easingfunctions as easing


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

# Borrowed from Tony Goodhew's PicoDisplay example code
# TODO: We're doing this to show arrows. Could probably re-implement with sprites?

up_arrow = [0,4,14,21,4,4,0,0]
down_arrow = [0,4,4,21,14,4,0,0]
bits = [128,64,32,16,8,4,2,1]  # Powers of 2

def draw_char(xpos, ypos, pattern, display):
    """Print defined character from set above.

    If we were using sprites, this wouldn't be necessary.
    """

    for line in range(8):  # 5x8 characters
        for ii in range(5):  # Low value bits only
            i = ii + 3
            dot = pattern[line] & bits[i]  # Extract bit
            if dot:  # print white dots
                display.pixel(xpos+i*2, ypos+line*2)
                display.pixel(xpos+i*2, ypos+line*2+1)
                display.pixel(xpos+i*2+1, ypos+line*2)
                display.pixel(xpos+i*2+1, ypos+line*2+1)


class ServoController:
    """Visual and serial interface for servo control.
    """

    def __init__(self, pin, angle=90, speed=20, vertical_offset=25, marker=up_arrow, marker_offset=0, interpolation=easing.linear):
        """Initialise the controller, with vaguely sane defaults."""
        # Convert initial angle to servo space (-90 to +90)
        servo_angle = angle - 90
        self._servo = EasedServo(pin, servo_angle)
        # Initialize the servo as not moving until we give it a command
        self._servo.isMoving = False
        self.angle = angle
        self.speed = speed
        self.vertical_offset = vertical_offset
        self.marker = marker
        self.marker_offset = marker_offset
        self.interpolation = interpolation

        # TODO: I don't think @property/getter/setter decorators work
        #       in Micropython, so it's a pain to do input validation.
        #       But equally, I can't find any documentation on this. Sigh.
        # TODO: Turns out @property and @x.setter decorators do work, now. Should probably use them, with validation.

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

    def draw(self, display, colors):
        """Draw the servo on the display.

        Also, write position to servo.

        Args:
            display: The display object to draw on
            colors: Dict containing color definitions (white, black, red, green, yellow, dark_grey)
        """
        # FIXME: should mostly 'just work' if we establish the display object correctly.

        # Are we selected? if so, draw a background
        if self.is_selected:
            # display.set_pen(70, 70, 70)
            display.set_pen(colors['dark_grey'])
            display.rectangle(0, self.vertical_offset - 20, 240, self.vertical_offset + 20)

        # Display minimum angle
        # Set pen colour to green if being updated, else yellow
        display.set_pen(colors['green']) if self.min_position_being_updated else display.set_pen(colors['yellow'])
        display.text(zfl(str(self.min_angle), 3), 10, self.vertical_offset, 200, 2)
        # printstring(zfl(str(self.min_angle), 3), 10, self.vertical_offset, 1, False, False)

        # Display maximum angle
        display.set_pen(colors['green']) if self.max_position_being_updated else display.set_pen(colors['yellow'])
        display.text(zfl(str(self.max_angle), 3), 200, self.vertical_offset, 200, 2)

        # Draw scale line
        display.set_pen(colors['white'])
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
        display.set_pen(colors['red'])
        # I don't know why this print is necessary, but without it the code blows up after a very short time.
        # print(self._marker_pos, self.vertical_offset + 13 + self.marker_offset)
        if self.marker:
            draw_char(self._marker_pos, self.vertical_offset + 13 + self.marker_offset, self.marker, display)
        # Update physical servo position, correcting for angle range
        # self._servo.value((self.angle + 90) % 180)
        # self._servo.value(rescale(self.angle, -90, 90, 0, 180))

        if self.display_mode == 1:
            # Display speed data
            if self.vertical_offset == 90:
                # Display speed by other button
                display.set_pen(colors['green']) if self.speed_being_updated else display.set_pen(colors['yellow'])
                display.text(zfl(str(self.speed), 3) + " SPD", 10, 20, 200, 2)
                # DIsplay current angle in centre space
                display.set_pen(colors['green']) if self.position_being_updated else display.set_pen(colors['yellow'])
                display.text(zfl(str(int(self.angle)), 3), 95, 45, 200, 4)
                # Display RUN/STOP text
                if self.is_running:
                    display.set_pen(colors['red'])
                    display.text("STOP", 190, 25, 200, 2)
                else:
                    display.set_pen(colors['green'])
                    display.text(" RUN", 190, 25, 200, 2)
            else:
                # Display speed setting by lower-left button
                display.set_pen(colors['green']) if self.speed_being_updated else display.set_pen(colors['yellow'])
                display.text(zfl(str(self.speed), 3) + " SPD", 10, self.vertical_offset + 75, 200, 2)
                # Display current angle in centre space
                display.set_pen(colors['green']) if self.position_being_updated else display.set_pen(colors['yellow'])
                display.text(zfl(str(int(self.angle)), 3), 95, self.vertical_offset + 35, 200, 4)
                # Display RUN/STOP legend by lower right button
                if self.is_running:
                    display.set_pen(colors['red'])
                    display.text("STOP", 190, self.vertical_offset + 75, 200, 2)
                else:
                    display.set_pen(colors['green'])
                    display.text(" RUN", 190, self.vertical_offset + 75, 200, 2)

    def move(self):
        """Move the servo to the current position."""
        # Convert from 0-180 range to -90/+90 range for servo
        servo_angle = int(self.angle - 90)
        print(f"Moving servo: display_angle={self.angle}, servo_angle={servo_angle}")

        # Use EasedServo's value method directly for immediate positioning
        self._servo.value(servo_angle)
        # Also update the EasedServo's angle property to keep it in sync (in servo space)
        self._servo.angle = servo_angle

    def min_position_setting_toggle(self):
        self.min_position_being_updated = not self.min_position_being_updated
        # Deselect the other thing if appropriate
        if self.min_position_being_updated:
            self.max_position_being_updated = False
            self.speed_being_updated = False
            self.is_running = False

    def max_position_setting_toggle(self):
        self.max_position_being_updated = not self.max_position_being_updated
        # Deselect the other thing if appropriate
        if self.max_position_being_updated:
            self.min_position_being_updated = False
            self.speed_being_updated = False
            self.is_running = False

    def position_and_min_setting_toggle(self):
        self.min_position_being_updated = not self.min_position_being_updated
        self.position_being_updated = self.min_position_being_updated
        self.angle = self.min_angle
        if self.min_position_being_updated:
            self.max_position_being_updated = False
            self.speed_being_updated = False
            self.move()  # Update the EasedServo position immediately

    def position_and_max_setting_toggle(self):
        self.max_position_being_updated = not self.max_position_being_updated
        self.position_being_updated = self.max_position_being_updated
        self.angle = self.max_angle
        if self.max_position_being_updated:
            self.min_position_being_updated = False
            self.speed_being_updated = False
            self.move()  # Update the EasedServo position immediately

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

        # Stop the EasedServo if we're stopping
        if not self.is_running:
            self._servo.isMoving = False

    def run(self):
        """Start, or keep going."""
        self.is_running = True

    def stop(self):
        """Stop, or stay stopped."""
        self.is_running = False
        # Stop the EasedServo
        self._servo.isMoving = False

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
            self.move()  # Update the EasedServo position immediately

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
            self.move()  # Update the EasedServo position immediately

    def update(self):
        """Update the servo position."""

        # Only update the EasedServo if it's currently moving and has been initialized with timing info
        if self._servo.isMoving and hasattr(self._servo, '_base_time'):
            self._servo.update()
            # Get the current angle from the EasedServo and convert back to display angle (0-180)
            servo_angle = self._servo.get_current_angle()
            self.angle = servo_angle + 90
            print(f"Updated from servo: servo_angle={servo_angle}, display_angle={self.angle}")

        # Handle reversing when running
        if self.is_running:
            # If servo is not currently moving, start a new move
            if not self._servo.isMoving:
                print(f"Current angle: {self.angle}, min: {self.min_angle}, max: {self.max_angle}, reversing: {self._reversing}")
                if self._reversing:
                    # Move to minimum angle
                    angle_diff = abs(self.angle - self.min_angle)
                    if angle_diff > 0:  # Only move if there's a difference
                        duration = angle_diff / self.speed * 1000  # Convert to milliseconds
                        print(f"Moving to min_angle {self.min_angle} (servo: {self.min_angle - 90}) in {duration}ms")
                        # Convert to servo angle space (-90 to +90) for EasedServo
                        self._servo.ease_to(self.min_angle - 90, max(int(duration), 1), self.interpolation)
                    self._reversing = False
                else:
                    # Move to maximum angle
                    angle_diff = abs(self.angle - self.max_angle)
                    if angle_diff > 0:  # Only move if there's a difference
                        duration = angle_diff / self.speed * 1000  # Convert to milliseconds
                        print(f"Moving to max_angle {self.max_angle} (servo: {self.max_angle - 90}) in {duration}ms")
                        # Convert to servo angle space (-90 to +90) for EasedServo
                        self._servo.ease_to(self.max_angle - 90, max(int(duration), 1), self.interpolation)
                    self._reversing = True
