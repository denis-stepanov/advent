# TV interface (PulseAudio)
## TODO: switch to Python API?

from tv_control.TVControl import TVControl
import os
import subprocess

class TVControlPulseAudio(TVControl):

    def __init__(self):
        super().__init__()
        self.muted = subprocess.run(['pactl', 'get-sink-mute', '@DEFAULT_SINK@'], stdout=subprocess.PIPE).stdout.decode('utf-8') == "Mute: yes\n"
        self.nominal_volume = subprocess.run(['pactl', 'get-sink-volume', '@DEFAULT_SINK@'], stdout=subprocess.PIPE).stdout.decode('utf-8').split('/')[1].strip()

    def toggleMute(self):
        ret = os.system("pactl set-sink-mute @DEFAULT_SINK@ toggle")
        if os.WIFEXITED(ret) and os.WEXITSTATUS(ret) == 0:
            super().toggleMute()
        return self.isMuted()

    def lowerVolume(self, new_volume):
        ret = os.system("pactl set-sink-volume @DEFAULT_SINK@ " + new_volume)
        return os.WIFEXITED(ret) and os.WEXITSTATUS(ret) == 0

    def restoreVolume(self):
        ret = os.system("pactl set-sink-volume @DEFAULT_SINK@ " + self.nominal_volume)
        return os.WIFEXITED(ret) and os.WEXITSTATUS(ret) == 0
