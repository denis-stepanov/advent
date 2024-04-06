# TV interface (PulseAudio)
# Volume is interpreted as percent
## TODO: switch to Python API?

from tv_control.TVControl import TVControl
import os
import subprocess

class TVControlPulseAudio(TVControl):

    def __init__(self):
        super().__init__()
        self.VOLUME_STEP = 5
        self.muted = subprocess.run(['pactl', 'get-sink-mute', '@DEFAULT_SINK@'], stdout=subprocess.PIPE).stdout.decode('utf-8') == "Mute: yes\n"
        self.nominal_volume = int(subprocess.run(['pactl', 'get-sink-volume', '@DEFAULT_SINK@'], stdout=subprocess.PIPE).stdout.decode('utf-8').split('/')[1].strip().strip('%'))
        self.current_volume = self.nominal_volume

    def toggleMute(self):
        ret = os.system("pactl set-sink-mute @DEFAULT_SINK@ toggle")
        return os.WIFEXITED(ret) and os.WEXITSTATUS(ret) == 0 and super().toggleMute()

    def changeVolume(self, delta = -50):
        new_volume = self.current_volume + delta
        ret = os.system("pactl set-sink-volume @DEFAULT_SINK@ " + str(new_volume) + "%")
        return os.WIFEXITED(ret) and os.WEXITSTATUS(ret) == 0 and super().changeVolume(delta)

    def restoreVolume(self):
        ret = os.system("pactl set-sink-volume @DEFAULT_SINK@ " + str(self.nominal_volume) + "%")
        return os.WIFEXITED(ret) and os.WEXITSTATUS(ret) == 0 and super().restoreVolume()
