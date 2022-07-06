# TV interface (Harmony Hub)

from tv_control.TVControl import TVControl
import requests

class TVControlHarmonyHub(TVControl):

    def __init__(self):
        super().__init__()
        self.api_server = "http://localhost:8282/hubs/harmony/commands/mute"
        self.mute_command = {'on': 'on'}

    def toggleMute(self):
        try:
            requests.post(self.api_server, data = self.mute_command)
            super().toggleMute()
        except requests.exceptions.RequestException as e:
            print(e)
        return self.isMuted()
