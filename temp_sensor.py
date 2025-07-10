import time
import glob


TEMP_SENSOR_BASE_DIR = '/sys/bus/w1/devices/'
TEMP_SENSOR_DEVICE_FOLDER = glob.glob(TEMP_SENSOR_BASE_DIR + '28*')[0]
TEMP_SENSOR_DEVICE_FILE = TEMP_SENSOR_DEVICE_FOLDER + '/w1_slave'


def read_temp_raw():
    with open(TEMP_SENSOR_DEVICE_FILE, 'r') as f:
        lines = f.readlines()
    return lines

def read_temp():
    lines = read_temp_raw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos + 2:]
        temp_c = float(temp_string) / 1000.0
        temp_f = temp_c * 9.0 / 5.0 + 32.0
        return temp_c, temp_f
    return None, None
