# TV interface (PulseAudio)
## TODO: switch to Python API?

from tv_control.TVControl import TVControl
import os
import subprocess

class TVControlPulseAudio(TVControl):

    def __init__(self):
        super().__init__()
        self.muted = subprocess.run(['pactl', 'get-sink-mute', '@DEFAULT_SINK@'], stdout=subprocess.PIPE).stdout.decode('utf-8') == "Mute: yes\n"

    def toggleMute(self):
        ret = os.system("pactl set-sink-mute @DEFAULT_SINK@ toggle")
        if os.WIFEXITED(ret) and os.WEXITSTATUS(ret) == 0:
            super().toggleMute()
        return self.isMuted()
