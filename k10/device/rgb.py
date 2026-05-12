from neopixel import NeoPixel
from machine import Pin
import time

# Verify pin number against UNIHIKER K10 pinout
_PIN_NUM  = 48
_NUM_LEDS = 3
_np = NeoPixel(Pin(_PIN_NUM), _NUM_LEDS)

_MOOD_COLORS = {
    "happy":    (0, 180, 0),
    "neutral":  (0, 0, 180),
    "tired":    (180, 140, 0),
    "stressed": (180, 0, 0),
    "sleeping": (120, 120, 120),
}

_PULSE_MOODS   = {"happy", "stressed"}
_BREATHE_MOODS = {"sleeping"}

_current_mood = "sleeping"


def _fill(color):
    for i in range(_NUM_LEDS):
        _np[i] = color
    _np.write()


def set_mood(mood: str):
    global _current_mood
    color = _MOOD_COLORS.get(mood, _MOOD_COLORS["neutral"])
    if mood != _current_mood:
        _beep()
        _current_mood = mood
    _fill(color)


def _breathe_once(color):
    for step in list(range(0, 100, 5)) + list(range(100, 0, -5)):
        factor = step / 100
        _fill(tuple(int(c * factor) for c in color))
        time.sleep_ms(30)


def _pulse_once(color):
    for _ in range(3):
        _fill(color)
        time.sleep_ms(150)
        _fill((0, 0, 0))
        time.sleep_ms(150)
    _fill(color)


def _beep():
    try:
        from machine import PWM
        # Verify speaker pin against UNIHIKER K10 pinout
        buzzer = PWM(Pin(2), freq=880, duty=512)
        time.sleep_ms(80)
        buzzer.deinit()
    except Exception:
        pass
