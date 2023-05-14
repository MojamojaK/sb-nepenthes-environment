import datetime
from typing import Tuple


desired_temperature_map = {
    "N. Meter 2": sorted([
        (datetime.time( 2, 0 , 0), 12.5),
        (datetime.time( 4, 30, 0), 12.0),
        (datetime.time( 5, 0 , 0), 12.0),
        (datetime.time( 6, 0 , 0), 17.0),
        (datetime.time( 9, 0 , 0), 23.0),
        (datetime.time(10, 0 , 0), 23.0),
        (datetime.time(11, 0 , 0), 23.0),
        (datetime.time(12, 0 , 0), 24.0),
        (datetime.time(13, 0 , 0), 24.0),
        (datetime.time(14, 0 , 0), 22.0),
        (datetime.time(16, 0 , 0), 17.0),
        (datetime.time(23, 0 , 0), 13.5)
        ], key=lambda x: x[0]),
    "N. Meter 1": sorted([
        (datetime.time( 3, 30, 0), 15.0),
        (datetime.time( 6,  0, 0), 18.0),
        (datetime.time( 9,  0, 0), 25.0),
        (datetime.time(10,  0, 0), 25.0),
        (datetime.time(14,  0, 0), 25.0),
        (datetime.time(20 , 0, 0), 18.0),
        (datetime.time(23 , 0, 0), 15.0),
        ], key=lambda x: x[0]),
}

cooler_active_diff_thresholds = {
    "N. Peltier Upper": -0.5,
    "N. Peltier Lower": 0.0,
}

heater_active_diff_thresholds = {
    "N. UV": 0.8,
    "N. Heater": 0.7,
}

ext_fan_diff_thresholds = {
    "N. ExtFan": {
        "Temperature": -1.0,
        "Humidity": -10
    }
}

desired_min_humidity_map = sorted([
    (datetime.time( 0,  0, 0),  94.0),
    (datetime.time( 6, 59, 0),  94.0),
    (datetime.time( 7,  0, 0), 100.0),
    (datetime.time( 7, 30, 0), 100.0),
    (datetime.time( 7, 31, 0),  75.0),
    (datetime.time( 7, 59, 0),  75.0),
    (datetime.time( 8,  0, 0), 100.0),
    (datetime.time( 8, 30, 0), 100.0),
    (datetime.time( 8, 31, 0),  75.0),
    (datetime.time(13, 59, 0),  70.0),
    (datetime.time(14,  0, 0), 100.0),
    (datetime.time(14, 29, 0), 100.0),
    (datetime.time(14, 30, 0),  70.0),
    (datetime.time(14, 59, 0),  70.0),
    (datetime.time(15,  0, 0), 100.0),
    (datetime.time(15, 29, 0), 100.0),
    (datetime.time(15, 30, 0),  70.0),
    (datetime.time(16, 59, 0),  80.0),
    (datetime.time(17,  0, 0), 100.0),
    (datetime.time(17, 14, 0), 100.0),
    (datetime.time(17, 15, 0),  80.0),
    (datetime.time(17, 59, 0),  85.0),
    (datetime.time(18, 00, 0), 100.0),
    (datetime.time(18, 29, 0), 100.0),
    (datetime.time(18, 30, 0),  85.0),
    (datetime.time(18, 59, 0),  85.0),
    (datetime.time(19,  0, 0), 100.0),
    (datetime.time(19, 29, 0), 100.0),
    (datetime.time(19, 30, 0),  85.0),
    (datetime.time(21, 59, 0),  85.0),
    (datetime.time(22, 00, 0), 100.0),
    (datetime.time(22, 29, 0), 100.0),
    (datetime.time(22, 30, 0),  85.0),
    (datetime.time(23, 59, 0),  85.0),
    ], key=lambda x: x[0])

def desired_min_humidity(current_datetime: datetime.datetime):
    current_time = current_datetime.time()
    start, end = get_between_time(desired_min_humidity_map, current_time)
    base_diff = stamp_diff(start[0], end[0])
    curr_diff = stamp_diff(start[0], current_time)
    tmp_diff = end[1] - start[1]
    if tmp_diff == 0:
        return start[1]
    tmp_diff = tmp_diff * (curr_diff / base_diff)
    return start[1] + tmp_diff

def time_in_range(start, end, x):
    """Return true if x is in the range [start, end]"""
    if start <= end:
        return start <= x <= end
    else:
        return start <= x or x <= end

def get_between_time(input_list, x) -> Tuple[Tuple[datetime.time, float], Tuple[datetime.time, float]]:
    size = len(input_list)
    for i in range(size):
        j = i-size+1
        # print("Comparing: " + str(input_list[i][0]) + ", " + str(input_list[j][0]) + ", " + str(x))
        if time_in_range(input_list[i][0], input_list[j][0], x):
            # print("Found!")
            return input_list[i], input_list[j]
    raise ValueError("Invalid Time Input")

def to_second_stamp(time: datetime.time) -> int:
    return time.hour * 3600 + time.minute * 60 + time.second

def stamp_diff(a, b) -> int:
    diff = to_second_stamp(b) - to_second_stamp(a)
    diff = (diff + 24 * 3600) % (24 * 3600)
    return diff

def desired_temperature(alias, current_datetime):
    meter_dedicated_list = desired_temperature_map[alias]
    current_time = current_datetime.time()
    start, end = get_between_time(meter_dedicated_list, current_time)
    base_diff = stamp_diff(start[0], end[0])
    curr_diff = stamp_diff(start[0], current_time)
    tmp_diff = end[1] - start[1]
    if tmp_diff == 0:
        return start[1]
    tmp_diff = tmp_diff * (curr_diff / base_diff)
    return start[1] + tmp_diff

PLUG_TASK_PRIORITY = [
    "N. Pump",
    "N. Fogger",
    "N. Peltier Upper",
    "N. Peltier Lower",
    "N. UV",
    "N. Heater",
    "N. ExtFan",
]

PLUG_DEFAULT_DESIRED_STATES = {
    "N. Pump": False,
    "N. Fogger": True,
    "N. Peltier Upper": False,
    "N. Peltier Lower": False,
    "N. UV": False,
    "N. Heater": False,
    "N. ExtFan": False,
}

