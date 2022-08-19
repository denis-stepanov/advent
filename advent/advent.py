#!/usr/bin/env python3

import os
import sys
import json
import threading
import time
import argparse
import logging
from pkg_resources import Requirement, resource_filename
from datetime import datetime
from datetime import timedelta
from dejavu import Dejavu
from dejavu.logic.recognizer.microphone_recognizer import MicrophoneRecognizer
from advent import __version__
from tv_control.TVControl import TVControl
from tv_control.TVControlPulseAudio import TVControlPulseAudio
from tv_control.TVControlHarmonyHub import TVControlHarmonyHub

# Settings
VERSION=__version__
REC_INTERVAL = 3
REC_DEADBAND = 0.4
MATCH_CONFIDENCE = 0.1
DEAD_TIME = 30
LOG_FILE = 'advent.log'

# Globals
DJV_CONFIG = None
NUM_THREADS = os.cpu_count()
REC_OFFSET = (REC_INTERVAL + REC_DEADBAND) / NUM_THREADS
REC_OFFSET_TD = timedelta(seconds=REC_OFFSET)
DEAD_TIME_TD = timedelta(seconds=DEAD_TIME)
detection_lock = threading.Lock()
mute_lock = threading.Lock()
last_detection_time = datetime.now()
last_mute_time = datetime.now() - timedelta(seconds=DEAD_TIME)
logger = logging.getLogger('advent')

# Run next detection no earlier that REC_OFFSET seconds
def ok_to_detect():
    global last_detection_time
    curr_time = datetime.now()
    ok = False
    detection_lock.acquire()
    if curr_time - last_detection_time >= REC_OFFSET_TD:
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

# Recognizer
class RecognizerThread(threading.Thread):

    def __init__(self, tvc):
        threading.Thread.__init__(self)
        self.tvc = tvc
        self.djv = Dejavu(DJV_CONFIG)

    def run(self):
        while True:
            # Space the threads in time
            if ok_to_detect():
                start_time = datetime.now().strftime('%H:%M:%S,%f')[:-3]
                matches = self.djv.recognize(MicrophoneRecognizer, seconds=REC_INTERVAL)[0]
                end_time = datetime.now().strftime('%H:%M:%S,%f')[:-3]
                if len(matches):
                    best_match = matches[0]
                    logger.debug(f'Recognition start={start_time}, end={end_time}, {len(matches)} match(es), {best_match["song_name"].decode("utf-8")} best, {int(best_match["fingerprinted_confidence"] * 100)}% confidence')
                    if best_match["fingerprinted_confidence"] >= MATCH_CONFIDENCE:
                        print('O', end='', flush=True)     # strong match
                        if ok_to_mute():
                            print('')
                            logger.info(f'Hit: {best_match["song_name"].decode("utf-8")}')
                            flags = int(best_match["song_name"].decode("utf-8").split('_')[4])
                            ad_start = flags & 0b0001
                            ad_end = flags & 0b0010
                            tv_muted = self.tvc.isMuted()
                            if not (ad_start or ad_end) or tv_muted and ad_end or not tv_muted and ad_start:
                                if self.tvc.toggleMute() != tv_muted:
                                    if tv_muted:
                                        logger.info('TV unmuted')
                                    else:
                                        logger.info('TV muted')
                                else:
                                    logger.info('TV mute failed')
                    else:
                      print('o', end='', flush=True) # weak match
                else:
                   logger.debug(f'Recognition start={start_time}, end={end_time}, 0 match(es)')
                   print('.', end='', flush=True)   # no match
            else:
                time.sleep(0.1)

def main():
    global DJV_CONFIG
    global NUM_THREADS
    global REC_OFFSET
    global REC_OFFSET_TD

    ## Command-line parser
    parser = argparse.ArgumentParser(description='Mute TV commercials by detecting ad jingles in the input audio stream',
        epilog='See https://github.com/denis-stepanov/advent for full manual. For database updates visit https://github.com/denis-stepanov/advent-db')
    parser.add_argument('-v', '--version', action='version', version=VERSION)
    parser.add_argument('-t', '--tv_control', help='use a given TV control mechanism (default: pulseaudio)', choices=['nil', 'pulseaudio', 'harmonyhub'], default='pulseaudio')
    parser.add_argument('-n', '--num_threads', help='run N recognition threads (default: = of CPU cores available)', type=int)
    parser.add_argument('-l', '--log', help='log events into a file (default: none)', choices=['none', 'events', 'debug'], default='none')
    args = parser.parse_args()

    # Logging
    logger.setLevel(logging.INFO)
    lsh = logging.StreamHandler()
    lsh.setLevel(logging.INFO)
    logger.addHandler(lsh)
    if args.log != 'none':
        if args.log == 'debug':
            logger.setLevel(logging.DEBUG)
        lf = logging.Formatter('%(asctime)s %(threadName)s %(levelname)s: %(message)s')
        lfh = logging.FileHandler(LOG_FILE)
        lfh.setFormatter(lf)
        logger.addHandler(lfh)
    logger.info(f'AdVent v{VERSION}')

    # Dejavu config
    with open(resource_filename(Requirement.parse("PyDejavu"),"dejavu_py/dejavu.cnf")) as dejavu_cnf:
        DJV_CONFIG = json.load(dejavu_cnf)
        logger.debug(f'Dejavu config {dejavu_cnf.name} loaded')

        # TV controls
        if args.tv_control == 'nil':
            tvc = TVControl()
        elif args.tv_control == 'harmonyhub':
            tvc = TVControlHarmonyHub()
        else:
            tvc = TVControlPulseAudio()
        logger.info(f'TV control is {args.tv_control}')
        if tvc.isMuted():
            logger.info('TV starts muted')
        else:
            logger.info('TV starts unmuted')

        # Thread control
        if args.num_threads != None:
            if args.num_threads < 1:
                logger.error(f'Error: Invalid number of threads: {args.num_threads}; ignoring')
            else:
                if args.num_threads > 2 * os.cpu_count():
                    logger.warning(f'Warning: Too high number of threads requested: {args.num_threads}; risk of system saturation')
                NUM_THREADS = args.num_threads
                REC_OFFSET = (REC_INTERVAL + REC_DEADBAND) / NUM_THREADS
                REC_OFFSET_TD = timedelta(seconds=REC_OFFSET)

        # Launch threads
        for n in range(0, NUM_THREADS):
            thread = RecognizerThread(tvc)
            thread.start()
        logger.info(f'Started {NUM_THREADS} listening thread(s)')
        logger.debug(f'Thread offset is {REC_OFFSET} s')
        return 0

    return 1

if __name__ == '__main__':
    main()
