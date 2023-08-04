# This project requires the Plant_io module which handles
# - Interfacing with electronics (pump, moisture sensor)
# - Datalogging to a file
#
# This code will run simple automatic irrigation based on soil moisture

import math
import network
import secrets
import time
from time import sleep_ms

import ntptime
import urequests

from Plant_io import Plant_io, DataLogger

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(secrets.SSID, secrets.PASSWORD)

MOISTURE_THRESHOLD = 32
PERIOD_MINS = 20

while True:
    while wlan.isconnected() == False:
        print('Waiting for connection...')
        wlan.active(False)
        sleep_ms(1000)
        wlan.active(True)
        wlan.connect(secrets.SSID, secrets.PASSWORD)

    print(wlan.ifconfig())

    current_time = 0
    if wlan.isconnected():
        ntptime.settime()
        current_time = time.time()

    print(f"Current time: {current_time}")
    ### Step 1: Initialise the Plant
    plant = Plant_io()
    plant.moisture_setpoint = MOISTURE_THRESHOLD # change this to tune how moist the growing media should be. Use the results from test_moisture_sensor.py
    
    # Attach sensors. Comment-out any sensors you are not using.
    print("Initialising PiicoDev modules")
    plant.attach('BME280')              # Atmospheric Sensor
    plant.attach('ENS160')              # Air-Quality Sensor
#     plant.attach('VEML6040')          # Colour Sensor
    plant.attach('VEML6030')            # Ambient Light Sensor
    plant.attach('VL53L1X')             # Laser Distance Sensor
#     plant.attach('LIS3DH')            # 3-Axis Accelerometer
#     plant.attach('QMC6310')           # 3-Axis Magnetometer

    print("")
    
    ### Step 2: Collect some data to log
    soil_moisture = plant.measure_soil()
    voltage = plant.measure_system_voltage()

    ### Step 3: Run the pump if plant requires water. This function uses soil moisture to decide whether to run the pump or not.
    pump_running_seconds = plant.run_pump_control()

    # Print some debugging information
    print(f'Moisture {soil_moisture:5.2f}%    Pump Time {pump_running_seconds:5.2f}s')


#     Ambient Light Sensor VEML6030
    lux = plant.VEML6030_light()
# 
#     Atmospheric Sensor BME280
    temperature_C, pressure_Pa, humidity_RH = plant.BME280_weather()
# 
#     Air-Quality Sensor ENS160
    ENS160_status, AQI, TVOC, eCO2 = plant.ENS160_air_quality()
# 
#     Colour Sensor VEML6040
#     hsv = plant.VEML6040_HSV()
#     rgb = plant.VEML6040_RGB()
# 
#     Laser Distance Sensor VL53L1X
    distance_mm = plant.VL53L1X_distance()
    if math.isnan(distance_mm):
        distance_mm = 0

# 
#     3-Axis Accelerometer LIS3DH
#     acceleration = plant.LIS3DH_acceleration()
# 
#     Magnetometer QMC6310
#     plant.QMC6310_calibrate() # should only need to run once. Comment out once calibration is complete.
#     flux = plant.QMC6310_flux()
#     polar = plant.QMC6310_polar()

    ### Step 4: Log the data to a file
    period_minutes = PERIOD_MINS # The chosen interval time on the Makerverse Nano Power Timer
    file_name = 'log.txt'

    # These are the labels that appear at the top of each data column in the log.txt file
    heading_time = 'Time [minutes]'
    heading_moisture = 'Moisture [%]'
    heading_pump = 'Pump Run [seconds]'
    heading_voltage = 'Supply Voltage [V]'
    heading_light = 'Light [lux]'
    heading_temp = 'Temperature [deg C]'
    heading_pres = 'Pressure [Pa]'
    heading_humi = 'Humidity [RH]'
    heading_aqi = 'Air Quality [AQI]'
    heading_tvoc = 'TVOC'
    heading_eco2 = 'eCO2'
    heading_dist = 'distance [mm]'
    data_heading = [heading_time,heading_moisture, heading_pump, heading_voltage, heading_light, heading_temp, heading_pres, heading_humi, heading_aqi, heading_tvoc, heading_dist,] # The heading that will appear at the top of the log file

    logfile = DataLogger(file_name, data_heading, period_minutes) # Open the log file, and write the data_heading if the file was just created.
    timestamp = logfile.last_timestamp + period_minutes # get the most recent timestamp

    # Construct a data dictionary - dictionary keys match the data headings eg. {heading string : data to log}
    data = {heading_time        : timestamp,
            heading_moisture    : soil_moisture,
            heading_pump        : pump_running_seconds,
            heading_voltage     : voltage,
            heading_light       : lux,
            heading_temp        : temperature_C,
            heading_pres        : pressure_Pa,
            heading_humi        : humidity_RH,
            heading_aqi         : AQI,
            heading_tvoc        : TVOC,
            heading_eco2        : eCO2,
            heading_dist        : distance_mm,
        }

    logfile.log_data(data)
    print(f'Data saved: {data}')
    upload_data = f"plant,sensor_id=RPI2W moisture={soil_moisture},pump={pump_running_seconds},voltage={voltage},lux={lux},temp={temperature_C},pressure={pressure_Pa},humidity={humidity_RH},aqi={AQI.value},tvoc={TVOC},eco2={eCO2.value},dist={distance_mm} {current_time}000000000"
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': f'Token {secrets.INFLUXDB_API_KEY}'}
    print(f"Uploading data: {upload_data}")
    
    try:
        response = urequests.post(secrets.INFLUXDB_URL, headers=headers, data=upload_data.encode())
        # need to close connection otherwise get memory leaks
        response.close()
    except Exception as e:
        print("Error sending data to InfluxDB: ", e)
    print(f'Data uploaded')
    
    print(f"Sleeping for {PERIOD_MINS} mins")
    ### Step 5: Signal to the Makerverse Nano Power Timer that we are DONE!
    # This removes power from the project until the next timer interval
    plant.sleep()
    
    ### Step 6: If we are running from USB power then power will never be removed by the Nano Power Timer.
    # Instead we can just insert a delay. When powered only by batteries, this code will never run.
    sleep_ms(round(1000*60*period_minutes))

