from machine import I2C, Pin
import time

_AHT20_ADDR = 0x38
_LTR303_ADDR = 0x29
_aht20_initialised = False


def _make_i2c():
    return I2C(1, scl=Pin(48), sda=Pin(47), freq=400000)


def _read_aht20(i2c) -> tuple:
    global _aht20_initialised
    try:
        if not _aht20_initialised:
            i2c.writeto(_AHT20_ADDR, bytes([0xBE, 0x08, 0x00]))
            time.sleep_ms(20)
            _aht20_initialised = True
        # Trigger measurement
        i2c.writeto(_AHT20_ADDR, bytes([0xAC, 0x33, 0x00]))
        time.sleep_ms(80)
        # Wait until not busy (bit 7 of status byte)
        for _ in range(10):
            data = i2c.readfrom(_AHT20_ADDR, 6)
            if not (data[0] & 0x80):
                break
            time.sleep_ms(10)
        humidity = ((data[1] << 12) | (data[2] << 4) | (data[3] >> 4)) / 1048576.0 * 100.0
        temp     = (((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5]) / 1048576.0 * 200.0 - 50.0
        return round(temp, 1), round(humidity, 1)
    except Exception as e:
        print(f"[sensors] aht20 error: {e}")
        _aht20_initialised = False
        return 0.0, 0.0


def _read_ltr303(i2c) -> float:
    try:
        # Activate (gain x1, integration 100ms)
        i2c.writeto(_LTR303_ADDR, bytes([0x80, 0x01]))
        time.sleep_ms(110)
        # Read 4 bytes from register 0x88 (CH1 low, CH1 high, CH0 low, CH0 high)
        d = i2c.readfrom_mem(_LTR303_ADDR, 0x88, 4)
        ch1 = d[0] | (d[1] << 8)
        ch0 = d[2] | (d[3] << 8)
        total = ch0 + ch1
        if total == 0:
            return 0.0
        ratio = ch1 / total
        if ratio < 0.45:
            lux = 1.7743 * ch0 + 1.1059 * ch1
        elif ratio < 0.64:
            lux = 4.2785 * ch0 - 1.9548 * ch1
        elif ratio < 0.85:
            lux = 0.5926 * ch0 + 0.1185 * ch1
        else:
            lux = 0.0
        return round(max(lux, 0.0), 1)
    except Exception as e:
        print(f"[sensors] ltr303 error: {e}")
        return 0.0


def read_sensors() -> dict:
    try:
        i2c = _make_i2c()
        temp, humidity = _read_aht20(i2c)
        lux = _read_ltr303(i2c)
        print(f"[sensors] temp={temp} hum={humidity} lux={lux}")
        return {"temp_c": temp, "humidity_pct": humidity, "light_lux": lux}
    except Exception as e:
        print(f"[sensors] read_sensors error: {e}")
        return {"temp_c": 0.0, "humidity_pct": 0.0, "light_lux": 0.0}
