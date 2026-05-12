_aht   = None
_light = None


def _init():
    global _aht, _light
    if _aht is not None:
        return True
    try:
        import k10_base
        _aht   = k10_base.aht20
        _light = k10_base.Light()
        return True
    except Exception:
        return False


def read_sensors() -> dict:
    if not _init():
        return {"temp_c": 0.0, "humidity_pct": 0.0, "light_lux": 0.0}
    try:
        temp     = round(_aht.temperature(), 1)
        humidity = round(_aht.humidity(), 1)
    except Exception:
        temp, humidity = 0.0, 0.0
    try:
        lux = float(_light.get_illuminance())
    except Exception:
        lux = 0.0
    return {"temp_c": temp, "humidity_pct": humidity, "light_lux": lux}
