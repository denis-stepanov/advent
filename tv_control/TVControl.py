# TV interface
class TVControl:

    def __init__(self):
        self.muted = False

    # This method can be called as frequently as once per second, so do not override it with something querying network or real hardware
    # This should have been marked "final" but Python 3.7 does not support it yet
    def isMuted(self):
        return self.muted

    def toggleMute(self):
        self.muted = not self.muted
        return self.muted
