# TV interface
## A generic interface which also serves as TV emulator
class TVControl:

    def __init__(self):
        self.VOLUME_STEP = 1       # A value uset to change volume in steps
        self.muted = False
        self.nominal_volume = 100
        self.current_volume = 100

    # False if we cannot read back TV status
    def isUnidirectional(self):
        return False

    def isMuted(self, cached = True):
        return self.muted

    def toggleMute(self):
        self.muted = not self.muted
        return True

    def getVolume(self, cached = True):
        return self.current_volume

    def isChangedVolume(self):
        return self.current_volume != self.nominal_volume

    def changeVolume(self, delta = -50):
        self.current_volume += delta
        return True

    def restoreVolume(self):
        self.current_volume = self.nominal_volume
        return True
