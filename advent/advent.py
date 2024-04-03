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
from sshkeyboard import listen_keyboard, stop_listening
from dejavu import Dejavu
from dejavu.logic.recognizer.microphone_recognizer import MicrophoneRecognizer
from advent import __version__
from tv_control.TVControl import TVControl
from tv_control.TVControlPulseAudio import TVControlPulseAudio
from tv_control.TVControlHarmonyHub import TVControlHarmonyHub
from tv_control.TVControlBroadLink import TVControlBroadLink

# Settings
VERSION=__version__
NUM_THREADS = 2           #     - number of threads to run
REC_INTERVAL = 2          # (s) - Dejavu listening interval
REC_DEADBAND = 0.25       # (s) - Dejavu processing time for an interval of 2 s with 2 threads. Measured experimentally on 4 x 1200 MHz machine with 84 jingles in DB
REC_CONFIDENCE = 10       # (%) - lowest still OK without false positives
TV_DEAD_TIME = 30         # (s) - action dead time after previous action taken on TV
MUTE_TIMEOUT = 600        # (s) - if TV is muted, unmute automatically after this time. Must be >= TV_DEAD_TIME
LOG_FILE = 'advent.log'

# Globals
DJV_CONFIG = None
TV_CODES = os.environ['HOME'] + '/' + 'tv-codes' # Folder where TV control codes are stored (used with BroadLink)
REC_OFFSET = (REC_INTERVAL + REC_DEADBAND) / NUM_THREADS
REC_OFFSET_TD = timedelta(seconds=REC_OFFSET)
TV_DEAD_TIME_TD = timedelta(seconds=TV_DEAD_TIME)
MUTE_TIMEOUT_TD = timedelta(seconds=MUTE_TIMEOUT)
LOGGER = logging.getLogger('advent')

# Generic TV
class TV:

    def __init__(self, tvc = TVControl(), action = 'mute', volume = ''):
        global TV_DEAD_TIME

        self.tvc = tvc
        self.setAction(action)
        self.volume = volume
        self.detection_lock = threading.Lock()
        self.action_lock = threading.Lock()
        self.last_detection_time = datetime.now()
        self.last_action_time = datetime.now() - timedelta(seconds=TV_DEAD_TIME)

    def getAction(self):
        return self.action

    def setAction(self, action):
        self.action = action
        self.in_action = self.tvc.lowVolume() if self.action == 'lower_volume' else self.tvc.isMuted()

    def isInAction(self):
        return self.in_action

    def startAction(self):
        if self.action == 'lower_volume':
            if self.volume:
                self.in_action = self.tvc.lowerVolume(self.volume)
            else:
                self.in_action = self.tvc.lowerVolume()    # use device default
        else:
            self.in_action = self.tvc.toggleMute()
        return self.in_action

    def stopAction(self):
        self.in_action = not(self.tvc.restoreVolume() if self.action == 'lower_volume' else self.tvc.toggleMute())
        return not(self.in_action)

    def getTimeSinceLastAction(self):
        return datetime.now() - self.last_action_time

    # Run next detection no earlier that REC_OFFSET seconds
    def OKToDetect(self):
        global REC_OFFSET_TD

        curr_time = datetime.now()
        ok = False
        self.detection_lock.acquire()
        if curr_time - self.last_detection_time >= REC_OFFSET_TD:
            self.last_detection_time = curr_time
            ok = True
        self.detection_lock.release()
        return ok

    # Disable TV actions for TV_DEAD_TIME seconds
    def OKToAct(self):
        global TV_DEAD_TIME_TD

        curr_time = datetime.now()
        ok = False
        self.action_lock.acquire()
        if curr_time - self.last_action_time >= TV_DEAD_TIME_TD:
            self.last_action_time = curr_time
            ok = True
        self.action_lock.release()
        return ok

    # Handle keyboard events
    def handleKeyboard(self, key):
        if key == 'q':
            stop_listening()
            print('')
            LOGGER.info('User: quit')
        elif key == 'space':
            self.action_lock.acquire()
            self.last_action_time = datetime.now()
            self.action_lock.release()
            self.tvc.toggleMute()
            self.setAction('mute')
            print('')
            LOGGER.info(f'User: toggle mute. TV is %s', "muted" if self.in_action else "unmuted")
        elif key == 'm':
            if self.tvc.isMuted():
                print('')
                LOGGER.info('User: mute. TV already muted')
            else:
                self.action_lock.acquire()
                self.last_action_time = datetime.now()
                self.action_lock.release()
                self.tvc.toggleMute()
                self.setAction('mute')
                print('')
                if self.isInAction():
                    LOGGER.info(f'User: mute. TV muted')
                else:
                    LOGGER.info(f'User: mute. TV failed to mute')
        elif key == 'M':
            if self.tvc.isMuted():
                self.action_lock.acquire()
                self.last_action_time = datetime.now()
                self.action_lock.release()
                self.tvc.toggleMute()
                self.setAction('mute')
                print('')
                if self.isInAction():
                    LOGGER.info(f'User: unmute. TV failed to unmute')
                else:
                    LOGGER.info(f'User: unmute. TV unmuted')
            else:
                print('')
                LOGGER.info('User: unmute. TV already unmuted')
        elif key == 'h':
            print('')
            print('h     - help')
            print('space - toggle mute')
            print('m / M - mute / unmute')
            print('v / V - volume down / up')
            print('c / C - decrease / increase confidence')
            print('q     - quit')

# Recognizer
class RecognizerThread(threading.Thread):

    def __init__(self, tv):
        threading.Thread.__init__(self)
        self.tv = tv
        self.djv = Dejavu(DJV_CONFIG)

    def run(self):
        while True:
            # Space the threads in time
            if self.tv.OKToDetect():
                start_time = datetime.now().strftime('%H:%M:%S,%f')[:-3]
                matches = self.djv.recognize(MicrophoneRecognizer, seconds=REC_INTERVAL)[0]
                end_time = datetime.now().strftime('%H:%M:%S,%f')[:-3]
                if len(matches):
                    best_match = matches[0]
                    LOGGER.debug(f'Recognition start={start_time}, end={end_time}, match {best_match["song_name"].decode("utf-8")}, {int(best_match["fingerprinted_confidence"] * 100)}% confidence')
                    if best_match["fingerprinted_confidence"] >= REC_CONFIDENCE / 100:
                        print('O', end='', flush=True)     # strong match
                        if self.tv.OKToAct():
                            print('')
                            LOGGER.info(f'Hit: {best_match["song_name"].decode("utf-8")}')
                            flags = int(best_match["song_name"].decode("utf-8").split('_')[4])
                            ad_start = bool(flags & 0b0001)
                            ad_end = bool(flags & 0b0010)

                            if self.tv.isInAction():
                                if ad_end:
                                    if self.tv.stopAction():
                                        LOGGER.info('TV volume restored' if self.tv.getAction() == 'lower_volume' else 'TV unmuted')
                                    else:
                                        LOGGER.warning('Warning: TV action failed')
                            else:
                                if ad_start:
                                    if self.tv.startAction():
                                        LOGGER.info('TV volume lowered' if self.tv.getAction() == 'lower_volume' else 'TV muted')
                                    else:
                                        LOGGER.warning('Warning: TV action failed')
                    else:
                      if best_match["fingerprinted_confidence"] > 0:
                          print('o', end='', flush=True) # weak match
                      else:
                          print(':', end='', flush=True) # no match
                else:
                   LOGGER.debug(f'Recognition start={start_time}, end={end_time}, no matches')
                   print('.', end='', flush=True)   # no signal
            else:
                time.sleep(0.1)


# Action watchdog
class ActionTimeoutThread(threading.Thread):

    def __init__(self, tv):
        threading.Thread.__init__(self)
        self.tv = tv

    def run(self):
        while True:
            if self.tv.isInAction() and self.tv.getTimeSinceLastAction() >= MUTE_TIMEOUT_TD and self.tv.OKToAct():
                print('')
                if self.tv.stopAction():
                    LOGGER.info('TV action ended due to timeout')
                else:
                    LOGGER.warning('TV action rollback on timeout failed')
            time.sleep(1)


# Main
def main():
    global DJV_CONFIG
    global NUM_THREADS
    global REC_INTERVAL
    global REC_CONFIDENCE
    global REC_OFFSET
    global REC_OFFSET_TD
    global MUTE_TIMEOUT
    global MUTE_TIMEOUT_TD
    global TV_CODES

    ## Command-line parser
    parser = argparse.ArgumentParser(description='Mute TV commercials by detecting ad jingles in the input audio stream',
        epilog='See https://github.com/denis-stepanov/advent for full manual. For database updates visit https://github.com/denis-stepanov/advent-db')
    parser.add_argument('-v', '--version', action='version', version=VERSION)
    parser.add_argument('-t', '--tv_control', help='use a given TV control mechanism (default: pulseaudio)', choices=['nil', 'pulseaudio', 'harmonyhub', 'broadlink'], default='pulseaudio')
    parser.add_argument('-a', '--action', help='action on hit (default: mute)', choices=['mute', 'lower_volume'], default='mute')
    parser.add_argument('-V', '--volume', help=f'target for volume lowering (defaults: PulseAudio: 50%%, HarmonyHub and BroadLink: -5)', type=str)
    parser.add_argument('-d', '--tv_codes', help='path to a folder with TV control codes (used with BroadLink; default: $HOME/tv-codes)', default=TV_CODES)
    parser.add_argument('-m', '--mute_timeout', help=f'undo hit action automatically after timeout (s) (default: {MUTE_TIMEOUT}; use 0 to disable)', type=int)
    parser.add_argument('-n', '--num_threads', help=f'run N recognition threads (default: {NUM_THREADS})', type=int)
    parser.add_argument('-i', '--rec_interval', help=f'audio recognition interval (s) (default: {REC_INTERVAL})', type=float)
    parser.add_argument('-c', '--rec_confidence', help=f'audio recognition confidence (%%) (default: {REC_CONFIDENCE})', type=int)
    parser.add_argument('-l', '--log', help='log events into a file (default: none)', choices=['none', 'events', 'debug'], default='none')
    args = parser.parse_args()

    # Logging
    LOGGER.setLevel(logging.INFO)
    lsh = logging.StreamHandler()
    lsh.setLevel(logging.INFO)
    LOGGER.addHandler(lsh)
    if args.log != 'none':
        if args.log == 'debug':
            LOGGER.setLevel(logging.DEBUG)
        lf = logging.Formatter('%(asctime)s %(threadName)s %(levelname)s: %(message)s')
        lfh = logging.FileHandler(LOG_FILE)
        lfh.setFormatter(lf)
        LOGGER.addHandler(lfh)
    LOGGER.info(f'AdVent v{VERSION}')

    # Dejavu config
    with open(resource_filename(Requirement.parse("PyDejavu"),"dejavu_py/dejavu.cnf")) as dejavu_cnf:
        DJV_CONFIG = json.load(dejavu_cnf)
        LOGGER.debug(f'Dejavu config {dejavu_cnf.name} loaded')

        # TV controls
        if args.mute_timeout != None:
            if args.mute_timeout < 0:
                LOGGER.error(f'Error: invalid timeout for action: {args.mute_timeout}; ignoring')
            elif args.mute_timeout > 0 and args.mute_timeout < TV_DEAD_TIME:
                LOGGER.warning(f'Warning: action timeout cannot be less than TV action dead time; setting to {TV_DEAD_TIME} s')
                MUTE_TIMEOUT = TV_DEAD_TIME
                MUTE_TIMEOUT_TD = timedelta(seconds=MUTE_TIMEOUT)
            else:
                MUTE_TIMEOUT = args.mute_timeout
                MUTE_TIMEOUT_TD = timedelta(seconds=MUTE_TIMEOUT)

        LOGGER.info(f'TV control is \'{args.tv_control}\' with action \'{args.action}\'' + (f' for {MUTE_TIMEOUT} s max' if MUTE_TIMEOUT != 0 else ''))

        if args.tv_control == 'pulseaudio':
            tvc = TVControlPulseAudio()
        elif args.tv_control == 'harmonyhub':
            tvc = TVControlHarmonyHub()
        elif args.tv_control == 'broadlink':
            if args.tv_codes:
                TV_CODES=args.tv_codes
            LOGGER.info(f'TV control codes folder: {TV_CODES}')
            tvc = TVControlBroadLink(TV_CODES)
        else:
            tvc = TVControl()
        tv = TV(tvc, args.action, args.volume if args.volume != None else '')

        if tv.isInAction():
            LOGGER.warning(f'Warning: TV starts with action in progress: \'{args.action}\'')

        # Recognition settings
        if args.rec_interval != None:
            if args.rec_interval <= 0:
                LOGGER.error(f'Error: invalid recognition interval: {args.rec_interval}; ignoring')
            else:
                if args.rec_interval < 1:
                    LOGGER.warning(f'Warning: recognition interval of {args.rec_interval} s will result in no matches')
                REC_INTERVAL = args.rec_interval
                REC_OFFSET = (REC_INTERVAL + REC_DEADBAND) / NUM_THREADS
                REC_OFFSET_TD = timedelta(seconds=REC_OFFSET)

        if args.rec_confidence != None:
            if args.rec_confidence < 0 or args.rec_confidence > 100:
                LOGGER.error(f'Error: invalid recognition confidence: {args.rec_confidence}; ignoring')
            else:
                if args.rec_confidence < 5:
                    LOGGER.warning(f'Warning: recognition confidence of {args.rec_confidence}% is not reliable')
                REC_CONFIDENCE = args.rec_confidence
        LOGGER.info(f'Recognition interval is {REC_INTERVAL} s with confidence of {REC_CONFIDENCE}%')

        # Thread control
        if args.num_threads != None:
            if args.num_threads < 1:
                LOGGER.error(f'Error: invalid number of threads: {args.num_threads}; ignoring')
            else:
                if args.num_threads > 2 * os.cpu_count():
                    LOGGER.warning(f'Warning: too high number of threads requested: {args.num_threads}; risk of system saturation')
                NUM_THREADS = args.num_threads
                REC_OFFSET = (REC_INTERVAL + REC_DEADBAND) / NUM_THREADS
                REC_OFFSET_TD = timedelta(seconds=REC_OFFSET)

        # Launch threads
        for n in range(0, NUM_THREADS):
            thread = RecognizerThread(tv)
            thread.daemon = True
            thread.start()
        LOGGER.info(f'Started {NUM_THREADS} listening thread(s)')
        LOGGER.debug(f'Thread offset is {REC_OFFSET} s')

        if MUTE_TIMEOUT != 0:
            thread = ActionTimeoutThread(tv)
            thread.name = "Thread-WD"
            thread.daemon = True
            thread.start()

        # Monitor user input
        LOGGER.info("Type 'h' for help")
        listen_keyboard(on_press = tv.handleKeyboard, lower = False)

        return 0

    return 1

if __name__ == '__main__':
    main()
