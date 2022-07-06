# TV interface
class TVControl:

    def __init__(self):
        self.muted = False

    def isMuted(self):
        return self.muted

    def toggleMute(self):
        self.muted = not self.muted
        return self.muted
