#!/usr/bin/env python3

import json
import os
import threading
import time
import subprocess
from datetime import datetime
from datetime import timedelta
from dejavu import Dejavu
from dejavu.logic.recognizer.microphone_recognizer import MicrophoneRecognizer

# Settings
DEFAULT_CONFIG_FILE = "dejavu.cnf.SAMPLE"
OFFSET = 1
SECONDS = 3
MATCH_CONFIDENCE = 0.2
DEAD_TIME = 30

# Globals
OFFSET_TD = timedelta(seconds=OFFSET)
DEAD_TIME_TD = timedelta(seconds=DEAD_TIME)
detection_lock = threading.Lock()
mute_lock = threading.Lock()
last_detection_time = datetime.now()
last_mute_time = datetime.now() - timedelta(seconds=DEAD_TIME)
tv_muted = False

# Run next detection no earlier that OFFSET seconds
def ok_to_detect():
    global last_detection_time
    curr_time = datetime.now()
    ok = False
    detection_lock.acquire()
    if curr_time - last_detection_time >= OFFSET_TD:
        last_detection_time = curr_time
        ok = True
    detection_lock.release()
    return ok

# Disable actions for DEAD_TIME seconds
def ok_to_mute():
    global last_mute_time
    curr_time = datetime.now()
    ok = False
    mute_lock.acquire()
    if curr_time - last_mute_time >= DEAD_TIME_TD:
        last_mute_time = curr_time
        ok = True
    mute_lock.release()
    return ok

# (c) dejavu
def init(configpath):
    """
    Load config from a JSON file
    """
    try:
        with open(configpath) as f:
            config = json.load(f)
    except IOError as err:
        print(f"Cannot open configuration: {str(err)}. Exiting")
        sys.exit(1)

    # create a Dejavu instance
    return Dejavu(config)

# TV mute interface (Harmony)
# TODO: make a base class
import requests
harmony_api_server = "http://localhost:8282/hubs/harmony/commands/mute"
mute_command = {'on': 'on'}
def mute_tv_harmony():
    try:
        requests.post(harmony_api_server, data = mute_command)
    except requests.exceptions.RequestException as e:
        print(e)

# TV mute interface (PulseAudio)
def mute_tv():
    os.system("pactl set-sink-mute @DEFAULT_SINK@ toggle")

# Recognizer
class RecognizerThread(threading.Thread):
    def __init__(self, tid):
        threading.Thread.__init__(self)
        self.tid = tid
        self.djv = init(DEFAULT_CONFIG_FILE)
    def run(self):
        global tv_muted
        while True:
            # Space the threads in time
            if ok_to_detect():
                matches = self.djv.recognize(MicrophoneRecognizer, seconds=SECONDS)[0]
                if len(matches):
                    best_match = matches[0]
                    if best_match["fingerprinted_confidence"] >= MATCH_CONFIDENCE:
                        print('O', end='', flush=True)     # strong match
                        if ok_to_mute():
                            print(f'\nHit: [{best_match["song_id"]}] {best_match["song_name"].decode("utf-8")}')
                            flags = int(best_match["song_name"].decode("utf-8").split('_')[4])
                            ad_start = flags & 0b0001
                            ad_end = flags & 0b0010
                            if not (ad_start or ad_end) or tv_muted and ad_end or not tv_muted and ad_start:
                                mute_tv()
                                tv_muted = not tv_muted
                                if tv_muted:
                                    print('TV muted')
                                else:
                                    print('TV unmuted')
                    else:
                      print('o', end='', flush=True) # weak match
                else:
                   print('.', end='', flush=True)   # no match
            else:
                time.sleep(0.1)


if __name__ == '__main__':

    # Launch enough threads to cover SECONDS listening period with offset of OFFSET plus one more to cover for imprecise timing. Number threads from 1
    for n in range(1, SECONDS // OFFSET + 1 + 1):
        thread = RecognizerThread(n)
        thread.start()
    print(f'Started {SECONDS // OFFSET + 1} listening thread(s)')

    tv_muted = subprocess.run(['pactl', 'get-sink-mute', '@DEFAULT_SINK@'], stdout=subprocess.PIPE).stdout.decode('utf-8') == "Mute: yes\n"
    if tv_muted:
        print('TV starts muted')
    else:
        print('TV starts unmuted')
