# TV interface (Harmony Hub)

from tv_control.TVControl import TVControl
import requests

class TVControlHarmonyHub(TVControl):

    def __init__(self):
        super().__init__()
        self.nominal_volume = "+4"
        self.current_volume = "+4"
        self.api_server = "http://localhost:8282/hubs/harmony/commands/"
        self.command_data = {'on': 'on'}

    def toggleMute(self):
        try:
            requests.post(self.api_server + "mute", data = self.command_data)
            return super().toggleMute()
        except requests.exceptions.RequestException as e:
            print(e)
        return False

    def lowerVolume(self, new_volume = '-4'):
        try:
            vol = int(new_volume)
        except ValueError:
            print(f"Invalid volume parameter \'{new_volume}\' for 'lower_volume'")
            return False
        self.nominal_volume = str(-vol)
        command = "volume-down" if vol < 0 else "volume-up"
        try:
            for i in range(vol if vol >= 0 else -vol):
                requests.post(self.api_server + command, data = self.command_data)
	    return super().lowerVolume(new_volume)
        except requests.exceptions.RequestException as e:
            print(e)
        return False

    def restoreVolume(self):
        vol = int(self.nominal_volume)
        command = "volume-down" if vol < 0 else "volume-up"
        try:
            for i in range(vol if vol >= 0 else -vol):
                requests.post(self.api_server + command, data = self.command_data)
	    return super().restoreVolume()
        except requests.exceptions.RequestException as e:
            print(e)
        return False
