# TV interface
class TVControl:

    def __init__(self):
        self.muted = False
        self.nominal_volume = "100%"
        self.current_volume = "50%"

    # This method can be called as frequently as once per second, so do not override it with something querying network or real hardware
    # This should have been marked "final" but Python 3.7 does not support it yet
    def isMuted(self):
        return self.muted

    def toggleMute(self):
        self.muted = not self.muted
        return True

    def lowVolume(self):
        return self.current_volume == self.nominal_volume

    def lowerVolume(self, new_volume):
        self.current_volume = new_volume
        return True

    def restoreVolume(self):
        self.current_volume = self.nominal_volume
        return True
