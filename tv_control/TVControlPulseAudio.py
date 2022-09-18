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
        self.current_volume = "0%" if self.muted else self.nominal_volume

    def toggleMute(self):
        ret = os.system("pactl set-sink-mute @DEFAULT_SINK@ toggle")
        return os.WIFEXITED(ret) and os.WEXITSTATUS(ret) == 0 and super().toggleMute()

    def lowerVolume(self, new_volume = '50%'):
        ret = os.system("pactl set-sink-volume @DEFAULT_SINK@ " + new_volume)
        return os.WIFEXITED(ret) and os.WEXITSTATUS(ret) == 0 and super().lowerVolume(new_volume)

    def restoreVolume(self):
        ret = os.system("pactl set-sink-volume @DEFAULT_SINK@ " + self.nominal_volume)
        return os.WIFEXITED(ret) and os.WEXITSTATUS(ret) == 0 and super().restoreVolume()
