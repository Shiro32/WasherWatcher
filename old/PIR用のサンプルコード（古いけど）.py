PIR用のサンプルコード（古いけど）

pi.set_mode( HUMAN_SENSOR_PIN, pigpio.INPUT)
pi.set_mode( HUMAN_SENSOR_SW_PIN, pigpio.INPUT)
pi.set_pull_up_down( HUMAN_SENSOR_SW_PIN, pigpio.PUD_DOWN)


def human_sensor_count():
    global human_sensor_check_count
    global human_sensor_on_count

    human_sensor_check_count += 1
    human_sensor_on_count += pi.read( HUMAN_SENSOR_PIN )

def human_sensor_check():
    global human_sensor_check_count
    global human_sensor_on_count
    global human_sensor_output

    print( "[HUMAN SENSOR] {:d}/{:d} = ".format(human_sensor_on_count,human_sensor_check_count), end="" )

#    print( "[HUMAN]:"+str(human_sensor_on_count)+"/"+str(human_sensor_check_count)+":", end="" )

    if( human_sensor_on_count / human_sensor_check_count > HUMAN_SENSOR_THRESHOLD ):
        human_sensor_output = 1
        pi.write(RUN_LED_PIN, pigpio.HIGH)
        print("someone here")
    else:
        human_sensor_output = 0
        pi.write(RUN_LED_PIN, pigpio.LOW)
        print("nobody here")

    human_sensor_check_count = 0
    human_sensor_on_count = 0

human_sensor_check_count = 10
human_sensor_on_count = 10
human_sensor_output = 1
human_sensor_check() # とりあえずオン