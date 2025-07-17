# Python Easing Functions
# https://gist.github.com/robweychert/7efa6a5f762207245646b16f29dd6671

# A fairly complete set of easing functions in Python. By passing
# a time value between 0 and 1 to any of these functions, you will
# get a value between 0 and 1 back.
# In principle, you could write your own transformation function,
# and pass that into any eased movement call. Which we think means
# you can write custom animation styles. Which may or may not be
# useful at some point in the future.

# In the meantime, all the standard easing interpolations are here.


import math


def linear(t):
    return t


def easeInSine(t):
    return -math.cos(t * math.pi / 2) + 1


def easeOutSine(t):
    return math.sin(t * math.pi / 2)


def easeInOutSine(t):
    return -(math.cos(math.pi * t) - 1) / 2


def easeInQuad(t):
    return t * t


def easeOutQuad(t):
    return -t * (t - 2)


def easeInOutQuad(t):
    t *= 2
    if t < 1:
        return t * t / 2
    else:
        t -= 1
        return -(t * (t - 2) - 1) / 2


def easeInCubic(t):
    return t * t * t


def easeOutCubic(t):
    t -= 1
    return t * t * t + 1


def easeInOutCubic(t):
    t *= 2
    if t < 1:
        return t * t * t / 2
    else:
        t -= 2
        return (t * t * t + 2) / 2


def easeInQuart(t):
    return t * t * t * t


def easeOutQuart(t):
    t -= 1
    return -(t * t * t * t - 1)


def easeInOutQuart(t):
    t *= 2
    if t < 1:
        return t * t * t * t / 2
    else:
        t -= 2
        return -(t * t * t * t - 2) / 2


def easeInQuint(t):
    return t * t * t * t * t


def easeOutQuint(t):
    t -= 1
    return t * t * t * t * t + 1


def easeInOutQuint(t):
    t *= 2
    if t < 1:
        return t * t * t * t * t / 2
    else:
        t -= 2
        return (t * t * t * t * t + 2) / 2


def easeInExpo(t):
    return math.pow(2, 10 * (t - 1))


def easeOutExpo(t):
    return -math.pow(2, -10 * t) + 1


def easeInOutExpo(t):
    t *= 2
    if t < 1:
        return math.pow(2, 10 * (t - 1)) / 2
    else:
        t -= 1
        return -math.pow(2, -10 * t) - 1


def easeInCirc(t):
    return 1 - math.sqrt(1 - t * t)


def easeOutCirc(t):
    t -= 1
    return math.sqrt(1 - t * t)


def easeInOutCirc(t):
    t *= 2
    if t < 1:
        return -(math.sqrt(1 - t * t) - 1) / 2
    else:
        t -= 2
        return (math.sqrt(1 - t * t) + 1) / 2
