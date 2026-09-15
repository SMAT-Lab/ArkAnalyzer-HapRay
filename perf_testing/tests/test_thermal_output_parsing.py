"""parse_thermal_output 对 hidumper ThermalService 真机输出的解析回归测试。

原始样本采集自真机（hdc shell "hidumper -s ThermalService -a '-t'"），
输出为两行一组：`Type: <name>` / `Temperature: <value>`，字段名首字母大写。
单位归一化：绝对值 >= 1000 视为毫摄氏度（26000 -> 26.0°C），否则为摄氏度（modem: 27 -> 27.0°C）。
"""

from __future__ import annotations

from hapray.core.collection.data_collector import DataCollector

# 真机原始输出样本（设备 4UR9K25113000554）
REAL_DEVICE_OUTPUT = """
-------------------------------[ability]-------------------------------


----------------------------------ThermalService----------------------------------
Type: Battery
Temperature: 26000
Type: ambient
Temperature: 21422
Type: charger
Temperature: 27142
Type: modem
Temperature: 27
Type: rfboard
Temperature: 25409
Type: shell_back
Temperature: 26508
Type: shell_frame
Temperature: 25708
Type: shell_front
Temperature: 27008
Type: system_h
Temperature: 26714
"""


def test_parse_real_device_output() -> None:
    sensors = DataCollector.parse_thermal_output(REAL_DEVICE_OUTPUT)
    assert sensors == {
        'Battery': 26.0,
        'ambient': 21.42,
        'charger': 27.14,
        'modem': 27.0,
        'rfboard': 25.41,
        'shell_back': 26.51,
        'shell_frame': 25.71,
        'shell_front': 27.01,
        'system_h': 26.71,
    }


def test_parse_milli_celsius_conversion() -> None:
    assert DataCollector.parse_thermal_output('Type: battery\nTemperature: 26000\n') == {'battery': 26.0}


def test_parse_raw_celsius_not_converted() -> None:
    assert DataCollector.parse_thermal_output('Type: modem\nTemperature: 28\n') == {'modem': 28.0}


def test_parse_empty_and_invalid_output() -> None:
    assert DataCollector.parse_thermal_output('') == {}
    assert DataCollector.parse_thermal_output('Type: battery\nTemperature: not-a-number\n') == {}
    assert DataCollector.parse_thermal_output('Temperature: 26000\n') == {}
