# TV interface (BroadLink)

from tv_control.TVControl import TVControl
import broadlink
import time

class TVControlBroadLink(TVControl):

    def __init__(self):
        super().__init__()
        self.nominal_volume = "+5"
        self.current_volume = self.nominal_volume

    def toggleMute(self):
        return super().toggleMute()

    def lowerVolume(self, new_volume = '-5'):
        return super().lowerVolume(new_volume)

    def restoreVolume(self):
        return super().restoreVolume()
