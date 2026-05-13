_np = None

_MOOD_COLORS = {
    "happy":    (0, 255, 0),
    "neutral":  (0, 0, 255),
    "tired":    (255, 150, 0),
    "stressed": (255, 0, 0),
    "sleeping": (20, 20, 20),
}

_current_mood = None


def _get_np():
    global _np
    if _np is None:
        from unihiker_k10 import rgb
        _np = rgb.my_rgb
        # k10_base starts a timer that fires every ~100ms and causes ETIMEDOUT
        # on TCP sockets. Kill it immediately after grabbing the NeoPixel ref.
        try:
            from machine import Timer
            for i in range(4):
                try:
                    Timer(i).deinit()
                except Exception:
                    pass
        except Exception:
            pass
    return _np


def _fill(color):
    np = _get_np()
    np[0] = color
    np[1] = color
    np[2] = color
    np.write()


def set_mood(mood: str):
    global _current_mood
    color = _MOOD_COLORS.get(mood, _MOOD_COLORS["neutral"])
    if mood != _current_mood:
        _current_mood = mood
        _beep()
    _fill(color)


def _beep():
    try:
        from machine import PWM, Pin
        buzzer = PWM(Pin(2), freq=880, duty=512)
        import time
        time.sleep_ms(80)
        buzzer.deinit()
    except Exception:
        pass
