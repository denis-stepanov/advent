# TV interface (Harmony Hub)

from tv_control.TVControl import TVControl
import requests
import time

class TVControlHarmonyHub(TVControl):

    def __init__(self):
        super().__init__()

        # No way to read volume from device
        self.nominal_volume = 0
        self.current_volume = self.nominal_volume

        self.api_server = "http://localhost:8282/hubs/harmony/commands/"
        self.command_data = {'on': 'on'}

    def toggleMute(self):
        try:
            requests.post(self.api_server + "mute", data = self.command_data)
            return super().toggleMute()
        except requests.exceptions.RequestException as e:
            print(e)
        return False

    def changeVolume(self, delta = -5):
        try:
            vol = int(delta)
        except ValueError:
            print(f"Invalid volume parameter \'{delta}\' for 'lower_volume'")
            return False
        command = "volume-down" if vol < 0 else "volume-up"
        try:
            for i in range(vol // self.VOLUME_STEP if vol >= 0 else -vol // self.VOLUME_STEP):
                requests.post(self.api_server + command, data = self.command_data)
                time.sleep(0.25)
            return super().changeVolume(delta)
        except requests.exceptions.RequestException as e:
            print(e)
        return False

    def restoreVolume(self):
        vol = self.nominal_volume - self.current_volume
        command = "volume-down" if vol < 0 else "volume-up"
        try:
            for i in range(vol // self.VOLUME_STEP if vol >= 0 else -vol // self.VOLUME_STEP):
                requests.post(self.api_server + command, data = self.command_data)
                time.sleep(0.25)
            return super().restoreVolume()
        except requests.exceptions.RequestException as e:
            print(e)
        return False
