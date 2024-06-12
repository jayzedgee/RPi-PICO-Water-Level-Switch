# Automated Water Pump Control with OLED Display
# Copyright (c) 2024 Joshua Ginges
#
# This code is licensed under the MIT License.
# For more information, please refer to the LICENSE file.

from machine import Pin, ADC, I2C
import time
from lib import ssd1306  # Ensure this path is correct and the library is present

# Initialize I2C on GPIO pins 16 (SDA) and 17 (SCL)
i2c = I2C(0, scl=Pin(17), sda=Pin(16), freq=400000)

# Scan for I2C devices
def scan_i2c():
    devices = i2c.scan()
    
    if devices:
        print('I2C devices found:')
        for device in devices:
            print(hex(device))
    else:
        print('No I2C devices found')

# Run the scan
scan_i2c()

# Initialize the OLED display with the detected address 0x3C
oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

# Define pins (from main)
adc_pin = ADC(Pin(26))  # ADC input for voltage measurement
pump_control = Pin(15, Pin.OUT)  # Digital output for pump control
pump_status_pin = Pin(27, Pin.IN, Pin.PULL_DOWN)  # Digital input for pump status with pull-down resistor
water_level = Pin(18, Pin.IN, Pin.PULL_UP)  # Ensure GP18 is in input mode with pull-up

# Constants
PUMP_RATE_LITRES_PER_MIN = 6.4  # Pump rate in litres per minute
MAX_PUMP_DURATION = 10 * 60  # Maximum pump duration in seconds (10 minutes)
REST_DURATION = 60  # Rest duration in seconds (1 minute)
MIN_RUN_TIME = 10  # Minimum pump run time in seconds
PAUSE_BETWEEN_RUNS = 10  # Pause between pump runs in seconds

def read_voltage(adc):
    # Read raw ADC value (0-65535) and convert to voltage (0-3.3V)
    raw_value = adc.read_u16()
    voltage = (raw_value / 65535) * 3.3
    return voltage

def read_pump_status(pin):
    # Read digital input to determine pump status
    return "ON" if pin.value() == 1 else "OFF"

# Variables to track pump state
litres_pumped = 0.0
pump_cycles = 0
pump_active_time = 0.0
pump_start_time = None
rest_start_time = None
is_resting = False
last_pump_stop_time = None  # Added to track the last pump stop time
start_time = time.time()

def format_hours(seconds):
    hours = seconds / 3600
    return f"{hours:.3f}"

def format_minutes(seconds):
    minutes = seconds / 60
    return f"{minutes:.2f}"

def display_info(current_active_time, current_litres_pumped):
    global pump_cycles, start_time
    
    current_time = time.time()
    elapsed_time = current_time - start_time if start_time else 1
    pump_duty_cycle = (current_active_time / elapsed_time) * 100 if elapsed_time > 0 else 0
    
    # Prepare display strings
    elapsed_time_str = format_hours(elapsed_time)
    pump_on_time_str = format_minutes(current_active_time)
    pump_duty_cycle_str = f"{pump_duty_cycle:.2f} %"
    pump_cycles_str = f"{pump_cycles}"
    volume_pumped_str = f"{current_litres_pumped:.2f} L"
    voltage_str = f"{voltage:.2f} V"

    # Display information
    oled.fill(0)
    oled.text(f" Elap: {elapsed_time_str}h", 0, 0)
    oled.text(f"PmpON: {pump_on_time_str} m", 0, 11)
    oled.text(f" Duty: {pump_duty_cycle_str}", 0, 22)
    oled.text(f"Cycls: {pump_cycles_str}", 0, 33)
    oled.text(f"  Vol: {volume_pumped_str}", 0, 44)
    oled.text(f"Volts: {voltage_str}", 0, 55)
    oled.show()

while True:
    current_time = time.time()
    
    if is_resting:
        if current_time - rest_start_time >= REST_DURATION:
            print("Rest period over. Resuming normal operation.")
            is_resting = False
        else:
            print("Resting...")
            display_info(pump_active_time, litres_pumped)  # Ensure the display updates during rest
            time.sleep(1)
            continue
    
    voltage = read_voltage(adc_pin)
    pump_status = read_pump_status(pump_control)
    
    # Print the diagnostic information
    print(f"Voltage at GPIO 26: {voltage:.2f} V")
    print(f"Pump Status: {pump_status}")
    
    # Calculate real-time pump active time and volume pumped
    if pump_control.value() == 1 and pump_start_time is not None:  # Pump is on
        real_time_pump_duration = time.time() - pump_start_time
        current_active_time = pump_active_time + real_time_pump_duration
        current_litres_pumped = litres_pumped + (PUMP_RATE_LITRES_PER_MIN * (real_time_pump_duration / 60))
    else:
        current_active_time = pump_active_time
        current_litres_pumped = litres_pumped

    # Control the pump based on the voltage
    if voltage < 2.1 and not is_resting:
        # Ensure the pump has been off for at least the pause duration
        if last_pump_stop_time is None or current_time - last_pump_stop_time >= PAUSE_BETWEEN_RUNS:
            if pump_control.value() == 0:  # Pump is off, turn it on
                print("Turning pump ON")
                pump_control.on()
                pump_start_time = time.time()
                pump_cycles += 1
            print("Pump is turned ON due to low voltage.")
    else:
        if pump_control.value() == 1:  # Pump is on, turn it off
            # Ensure the pump has run for at least the minimum run time
            if pump_start_time is not None and current_time - pump_start_time >= MIN_RUN_TIME:
                print("Turning pump OFF")
                pump_control.off()
                pump_duration = time.time() - pump_start_time
                pump_active_time += pump_duration
                litres_pumped += PUMP_RATE_LITRES_PER_MIN * (pump_duration / 60)
                pump_start_time = None
                last_pump_stop_time = time.time()  # Track the time the pump was last stopped
    
    # Update the display with the latest information
    display_info(current_active_time, current_litres_pumped)
    
    time.sleep(0.1)  # Reduce sleep duration to update the display more frequently
