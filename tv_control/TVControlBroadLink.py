# TV interface (BroadLink)

from tv_control.TVControl import TVControl
import broadlink
import time

class TVControlBroadLink(TVControl):

    def __init__(self, tv_codes):
        super().__init__()

        # Discover the control device
        self.device = ""
        for device in broadlink.xdiscover():
            if self.device != "":
                print("Warning: more than one BroadLink device discovered. Using the first one found")
                break
            self.device = device
            self.device.auth()
            print(f"TV controller: {self.device}")
            break
        if self.device == "":
           print("Warning: no BroadLink devices discovered. TV action will be disabled")

        # Fetch TV control codes
        self.FILE_CODE_MUTE_TOGGLE = "mute-toggle.code"
        self.FILE_CODE_VOLUME_DOWN = "volume-down.code"
        self.FILE_CODE_VOLUME_UP = "volume-up.code"

        self.CODE_MUTE_TOGGLE = ""
        self.CODE_VOLUME_DOWN = ""
        self.CODE_VOLUME_UP = ""

        try:
            with open(tv_codes + '/' + self.FILE_CODE_MUTE_TOGGLE, 'r') as code:
                self.CODE_MUTE_TOGGLE = bytearray.fromhex(code.read())
        except FileNotFoundError as e:
            print(f"Warning: file {e.filename} not found. Action 'mute' will be disabled")
        try:
            with open(tv_codes + '/' + self.FILE_CODE_VOLUME_DOWN, 'r') as code:
                self.CODE_VOLUME_DOWN = bytearray.fromhex(code.read())
            with open(tv_codes + '/' + self.FILE_CODE_VOLUME_UP, 'r') as code:
                self.CODE_VOLUME_UP = bytearray.fromhex(code.read())
        except FileNotFoundError as e:
            print(f"Warning: file {e.filename} not found. Action 'lower_volume' will be disabled")

        self.nominal_volume = "+5"
        self.current_volume = self.nominal_volume

    def toggleMute(self):
        if self.CODE_MUTE_TOGGLE != "":
            self.device.send_data(self.CODE_MUTE_TOGGLE)
            return super().toggleMute()
        else:
            return False

    def lowerVolume(self, new_volume = '-5'):
        if self.CODE_VOLUME_DOWN != "" and self.CODE_VOLUME_UP != "":
            try:
                vol = int(new_volume)
            except ValueError:
                print(f"Invalid volume parameter \'{new_volume}\' for 'lower_volume'")
                return False
            self.nominal_volume = str(-vol)
            command = self.CODE_VOLUME_DOWN if vol < 0 else self.CODE_VOLUME_UP
            for i in range(vol if vol >= 0 else -vol):
                self.device.send_data(command)
                time.sleep(0.25)
            return super().lowerVolume(new_volume)
        else:
            return False

    def restoreVolume(self):
        if self.CODE_VOLUME_DOWN != "" and self.CODE_VOLUME_UP != "":
            vol = int(self.nominal_volume)
            command = self.CODE_VOLUME_DOWN if vol < 0 else self.CODE_VOLUME_UP
            for i in range(vol if vol >= 0 else -vol):
                self.device.send_data(command)
                time.sleep(0.25)
            return super().restoreVolume()
        else:
            return False
