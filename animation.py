from servo import Servo, servo2040
import easingfunctions as easing
import time

class EasedServo(Servo):
    """Subclass of Servo object to support easing functions."""

    # TODO: @property and @setter decorators work in Micropython now, I think?


    def __init__(self, pin, angle=90):
        """Basic constructor. Creates a Servo object and sets the angle to the given value, defaulting to 0.

        We're assuming that servos go -90/+90 in micropython land.
        TODO: Check this assumption
        """
        super().__init__(pin)
        self.enable()

        # Register ourselves with the ServoController singleton
        self.controller = AnimationController.get_instance()
        self.controller.register_servo(self)

        self.angle = angle
        self.value(angle)
        # Are we using underscores to indicate private variables?
        self._easing_function = easing.linear
        self.isMoving=True


    def ease_to(self, angle, duration, easing_function=easing.linear):
        """Sets the target angle and duration, and receives a function to use for easing."""
        self._start_angle = self.angle
        self._target_angle = angle
        self._easing_function = easing_function
        # Start a millisecond timer
        self._base_time = time.ticks_ms()
        self._duration = duration
        self.isMoving = True
        print(f'>>> Starting move from: {self._start_angle} to: {angle} in {duration} ms using {easing_function.__name__} easing.')


    def value(self, angle):
        """Set the servo angle.

        Need to override the superclass method to update the angle property.
        We could access the superclass' value property, but wrapping
        it in a method seems neater, oddly. Comments welcome.

        We need to capture the angle here, because otherwise the EasedServo
        object loses track of where it is. Which matters for the next move.
        """

        self.angle = angle

        # Uncomment this line to spew diagnostics to the console
        # print (">>> Setting angle to: " + str(angle))

        # Call the superclass method to actually set the servo angle
        super().value(angle)


    def get_current_angle(self):
        """Get the current angular position of the servo."""
        return self.angle


    def update(self):
        """Handle servo angle updates."""
        # How far through the movement duration are we?
        proportion_complete = (time.ticks_ms() - self._base_time) / self._duration

        # Calculate the new angle
        self.angle = (
            self._easing_function(proportion_complete)
            * (self._target_angle - self._start_angle)
            + self._start_angle
        )

        # Set the servo position
        self.value(self.angle)

        # Are we done?
        if proportion_complete > 1:
            # Set the angle to the target angle, so we haven't overshot for the
            # start of the next movement.
            self.angle = self._target_angle
            # We're done!
            self.isMoving = False


class AnimationController():
    """Class to manage a collection of EasedServo objects.

    Employed as a Singleton."""

    _instance = None

    def __init__(self):
        """Basic constructor. Creates an empty list of servos.

        Also checks to see if we've already created an instance of this class."""

        if AnimationController._instance is not None:
            raise Exception("You can't create more than one instance of AnimationController.")
        else:
            AnimationController._instance = self
        self.servos = []

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = AnimationController()
        return cls._instance

    def register_servo(self, servo):
        """Add a servo to the list."""
        self.servos.append(servo)


    def update(self):
        """Update all the servos."""
        for servo in self.servos:
            servo.update()


    def all_done(self):
        """Check if all the servos are done."""
        for servo in self.servos:
            if servo.isMoving:
                return False
        return True


    def wait(self):
        """Wait for all the servos to finish."""

        # TODO: we probably don't need this, as it's blocking.
        while not self.all_done():
            self.update()
            time.sleep(0.01)


    def go_home(self):
        """Send all the servos home."""

        # TODO: This is terrible boilerplate. Fix.
        for servo in self.servos:
            servo.ease_to(90, 4000, easing.linear)
        self.wait()


    def detach_servos(self):
        """Detach all the servos."""
        for servo in self.servos:
            servo.detach_servo()


    def queue_wait_for(self, other_servo):
        """Wait for another servo to finish."""
        pass  # TODO: Implement synchronization with another servo


    def queue_angle(self, angle, duration, easing_function):
        """Queue up angles to move sequentially."""

        # TODO: This doesn't look right.
        for servo in self.servos:
            servo.queue_angle(angle, duration, easing_function)

