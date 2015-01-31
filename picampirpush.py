
#!/usr/bin/python
# picampirpush
# Detects Persons in the room via PIR and takes a photo and sends it via pushbullet
#
# Authors:      nildt, some parts taken from https://github.com/espunny/raspberrypi-Alarm/blob/master/alarma.py
# Dependencies: http://picamera.readthedocs.org/en/release-1.9/#, https://github.com/randomchars/pushbullet.py, python3, https://pypi.python.org/pypi/RPi.GPIO, http://www.imagemagick.org/
# Date:         29/01/15
# Rev:          0.3

# GPIO support
import RPi.GPIO as GPIO
# Camera support
import picamera
# File Handling
import io
# Exception handling
import sys
import os
from shutil import rmtree
from subprocess import call
from time import sleep
#from datetime import datetime
from pushbullet import PushBullet
from threading import Thread
from ConfigParser import SafeConfigParser

def takePhoto():
        global cam
        path = "captures/"
        os.mkdir(path)
        cam.start_preview()
        sleep(1)
        # Take 16 photos to capture the movement
        for x in range(1,16):
                filename = "detected-%02d.jpg" % x
                cam.capture(path + filename, use_video_port=True)
        cam.stop_preview()
        montage_file ='temp.jpg'
        call("montage -border 0 -background none -geometry 240x180 " + path + "* " +  montage_file, shell=True)
        print("[+]      Phtos taken and put together!")
        return (montage_file)

def threaded_PushAlarm():
        global cooldown, pushprocess, pb,cam
        montage_file = takePhoto()
        with open(montage_file, "rb") as pic:
                success, file_data = pb.upload_file(pic, montage_file)
        success, push = pb.push_file(**file_data)
        #success, push = pb.push_note("[-] Alaaaaarm:","Motion detected" + " at  " + datetime.now().strftime("%Y-%m-%d %H:%M"))
        print ("[+]     Push sent!")
        cooldown = 1

def MOTION(GPIO_PIR):
        global pushprocess
        #PIR is triggered
        #Tiger push notification. Wait for the push-thread!
        if pushprocess==0:
                pushprocess=1
                thread = Thread(target = threaded_PushAlarm)
                thread.start()
                thread.join()

def remove_pushes():
        global pb
        success, pushes = pb.get_pushes()
        latest = pushes[0]
        # We already read it, so let's dismiss it
        success, error_message = pb.dismiss_push(latest.get("iden"))
        # Now delete it
        success, error_message = pb.delete_push(latest.get("iden"))
        print("[+]      Last push successful removed!")
        try:
                rmtree("currentdirectory/captures")
                os.remove("temp.jpg")
        except OSError:
                pass

        print("[+]      Old Pictures removed!")

def main():
        global pb,pushprocess,cooldown,cam
        print('[+}      Initializing')
        try:
                GPIO.setmode(GPIO.BCM)
                # Define GPIO Port (BCM Table)
                GPIO_PIR = 24

                # Set pin as input
                GPIO.setup(GPIO_PIR,GPIO.IN) # Echo
                # Init camera
                cam = picamera.PiCamera()
                cam.led = False
                cam.rotation=180

                # Parse Config
                parser = SafeConfigParser()
                parser.read('currentdirectory/config.ini')
                api_key = parser.get('pushbullet_config', 'api_key')
                cooldown_time = int(parser.get('pushbullet_config','cooldown_time'))

                # init PushBullet
                pb = PushBullet(api_key)
        except:
                print('[-]      Error during initialisation:', sys.exc_info()[0])
                raise SystemExit # Bye

        # 0 ready, 1 sending
        pushprocess = 0

        # Send cooldown signal with 1
        cooldown = 0

        try:
                print ("[+]     Waiting for event")
                GPIO.add_event_detect(GPIO_PIR, GPIO.RISING, callback=MOTION)
                while 1:
                        # Wait for 10 milliseconds
                        sleep(.1)
                        if cooldown==1:
                                pushprocess=0
                                cooldown=0
                                GPIO.remove_event_detect(GPIO_PIR)
                                print ("[+]     Cooling down " + str(cooldown_time) + " seconds.")
                                sleep(cooldown_time)
                                # Now delete old pushes as thread
                                thread = Thread(target = remove_pushes)
                                thread.start()
                                thread.join()
                                # Again on air:
                                GPIO.add_event_detect(GPIO_PIR, GPIO.RISING, callback=MOTION)

        except KeyboardInterrupt:
                print ("[+]     Alarm disabled")

        except Exception, e:
                print ("[-]     Unknown error:")
                print (str(e))
        finally:
                GPIO.cleanup()
                cam.close()
                remove_pushes()

if __name__ == "__main__":
        main()
