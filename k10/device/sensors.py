from machine import I2C, Pin
import time

# Verify these pin numbers against UNIHIKER K10 pinout before running on device
_i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=100_000)

_AHT20_ADDR  = 0x38
_LTR303_ADDR = 0x29


def _aht20_init():
    try:
        time.sleep_ms(40)  # power-on stabilization
        status = _i2c.readfrom(_AHT20_ADDR, 1)[0]
        if not (status & 0x08):  # calibration bit not set
            _i2c.writeto(_AHT20_ADDR, bytes([0xBE, 0x08, 0x00]))
            time.sleep_ms(10)
    except Exception:
        pass


def _aht20_read():
    _i2c.writeto(_AHT20_ADDR, bytes([0xAC, 0x33, 0x00]))
    time.sleep_ms(80)
    data = _i2c.readfrom(_AHT20_ADDR, 6)
    raw_hum  = ((data[1] << 12) | (data[2] << 4) | (data[3] >> 4))
    raw_temp = (((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5])
    humidity = (raw_hum  / 0x100000) * 100
    temp     = (raw_temp / 0x100000) * 200 - 50
    return round(temp, 1), round(humidity, 1)


def _ltr303_init():
    try:
        _i2c.writeto(_LTR303_ADDR, bytes([0x80, 0x01]))  # active mode
        time.sleep_ms(100)
    except Exception:
        pass


def _ltr303_read():
    try:
        data = _i2c.readfrom_mem(_LTR303_ADDR, 0x88, 4)
        ch1 = (data[1] << 8) | data[0]
        ch0 = (data[3] << 8) | data[2]
        lux = ch0 if ch0 > 0 else 0
        return float(lux)
    except Exception:
        return 0.0


_aht20_init()
_ltr303_init()


def read_sensors() -> dict:
    try:
        temp, humidity = _aht20_read()
    except Exception:
        temp, humidity = 0.0, 0.0
    lux = _ltr303_read()
    return {"temp_c": temp, "humidity_pct": humidity, "light_lux": lux}
