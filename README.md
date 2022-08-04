# AdVent
This program mutes TV commercials by detecting ad jingles in the input audio stream.

Watch AdVent in action (make sure to turn the video sound on):

https://user-images.githubusercontent.com/22733222/174403887-37918d1e-da37-4cf5-9d7b-b04677ce8e2a.mp4

Here AdVent is running next to a TV stream in browser, watched by a user using headphones. When an ad kicks in, AdVent cuts the sound. A bit jerky video is a result of me capturing demo video on a ten years old laptop.

Once the ads are over, AdVent turns the sound back on (not part of this demo).

AdVent functions by comparing live sound with a database of known ad jingles using open source sound recognition software [Dejavu](https://github.com/denis-stepanov/dejavu). A database of jingles is available as a separate repository [AdVent Database](https://github.com/denis-stepanov/advent-db) and is open for contributions.

AdVent on a Raspberry Pi controlling a Sony BRAVIA TV-set:

![AdVent on Raspberry Pi](https://user-images.githubusercontent.com/22733222/180578361-5f08129c-bd5b-498e-8b03-324fc9c2b74d.jpg)

## How Stuff Works

Diagram below shows in blue a standard workflow for a person listening to a TV and muting TV sound with a remote.

![AdVent Workflow](https://user-images.githubusercontent.com/22733222/180874326-85a9d62a-3681-4ad0-b29a-7d356529fe8d.png)

AdVent is added in parallel (path in orange), using same or similar tools for mute. The main difference is the audio source. It should be different from the one that person hears, because AdVent needs to continue listening while the sound is muted. This is required to be able to unmute later on. This is why a microphone is generally not a good source; it is better to feed something not affected by the `Mute` button of a TV. S/PDIF digital output of the TV is one good candidate.

### Streaming Problem

The biggest problem with Dejavu is that it does not support continuous recognition from a stream. One has to define a recognition window. It kind of works when you have a four minutes song fingerprinted, and launch recognition anytime in the middle. It does not work well when your "song" is a three seconds jingle. So I opted for parallelized approach where there are overlapping threads listening for input in a sliding manner.

![Streaming Implementation](https://user-images.githubusercontent.com/22733222/181107790-0cb879a7-e7df-411c-b211-03a4ae8b40ea.png)

Question is how many threads are needed. To understand this better I took a random three seconds jingle and tested its recognition once being split in two parts. Results:

<table>
<tr>
<th>Part 1</th>
<th>Part 2 </th>
<th>Recognition Confidence</th>
</tr>
<tr>
<td>3 s</td>
<td>0 s</td>
<td>100%</td>
</tr>
<tr>
<td>2 s</td>
<td>1 s</td>
<td>22%</td>
</tr>
<tr>
<td>1.5 s</td>
<td>1.5 s</td>
<td>11%</td>
</tr>
<tr>
<td>1 s</td>
<td>2 s</td>
<td>28%</td>
</tr>
</table>

Unrelated track gives confidence of less than 10%.

From this we can draw some conclusions:

1. for good recognition, having 3 seconds fingerprinted is enough ([Dejavu's own estimate](https://github.com/denis-stepanov/dejavu#2-audio-over-laptop-microphone) is that 3 seconds fingerprinted gives 98% recognition confidence);
2. every contiguous 1.5 seconds (2 seconds better) shall be covered by at least one recognition attempt. Jingle minimal duration thus should not be inferior to 1.5 seconds;
3. 10% confidence looks like a good cut-off for a "hit".

So we can estimate that having three recognition threads running with one second interval over three seconds window (as on figure above) should give good enough coverage. These values have been recorded as parameters in AdVent source code. Due to imperfections of timing, I added one more thread. This gives four threads in total, actively working on recognition. This means that for AdVent to perform well, it should be run on at least four cores CPU, and on such a system it will create 100% system load (four threads occupying four cores). Most of modern systems satisfy this requirement, Raspberry Pi included.

Because recognition process is not deterministic, threads originally spaced in time might drift and get closer to each other. This would diminish coverage and decrease effectiveness of recognition. To avoid this effect, a mutex is used which would prevent any recognition operation firing too close to another one from a parallel thread.

Another side effect from threading is that two closely running threads both yielding a hit can try flipping TV, which would cause problems at TV controls unit, as well as unpleasant user experience. To prevent this, a dead time is used (30 seconds by default), during which all actions on TV are disabled.

Finally, an implicit requirement coming from threading approach is that hardware audio source shall support concurrent use from threads. This is not granted in general case (see [below](#testing)).

## Supported Environment
There are many different ways of watching TV these days. Currently supported audio inputs:

* video streaming in browser (via [PulseAudio](https://www.freedesktop.org/wiki/Software/PulseAudio/) monitor)
* [S/PDIF](https://en.wikipedia.org/wiki/S/PDIF) digital audio out from a TV-set: optical [TOSLINK](https://en.wikipedia.org/wiki/TOSLINK) or electrical [RCA](https://en.wikipedia.org/wiki/RCA_connector) (RCA untested but should work)
* (could be implemented if there's interest) microphone

Supported TV controls:

* PulseAudio (when watching TV on Linux)
* [Logitech Harmony Hub](https://support.myharmony.com/en-es/hub)
* (could be implemented if there's interest) IrDA TV control (vendor-specific)

Supported actions:

* sound on / off
* (could be implemented if there's interest) sound fade out / in
* (could be implemented if there's interest) changing a TV channel
* ...

Supported OS:

* recent Fedora (tested on Fedora 36)
* Raspbian 10
* (Windows is not supported but the majority of software is in Python; should work as is, with the exception of TV controls module which would need contributions and testing)

Not all combinations are supported; see below for the details.

It is possible to use unrelated inputs and outputs (e.g., to cut a sound on a real TV-set while running AdVent over a TV web cast); however, in this case one has to accept potential time de-sync, which could be quite important (dozens of seconds, depending on a TV feed provider).

## Usage

### AdVent (advent)

Runnig AdVent is as simple as:

```
(advent-pyenv) $ advent
```

The output should resemble to this:

```
TV starts unmuted
Started 4 listening thread(s)
.oooooooo.ooooooooooooo..oo
```

AdVent prints every second a character reflecting recognition progress. Meaning of characters:

* `.` - no match (usually when there's silence or no input connected at all)
* `o` - weak match (quite normal on any input)
* `O` - strong match, also called a "hit". When a hit happens, AdVent prints hit details and may take some action on a TV

There is no standard way of exiting the application, as it is designed to run forever. If you need to exit, press `Ctrl-C`; if that does not work, try harder with `Ctrl-\`.

The default TV control is `pulseaudio`; you can alter this with `-t` option; e.g. `-t harmonyhub` will select HarmonyHub control instead.

There is no option to select an audio source; AdVent takes a system default. See more details on audio inputs in a [dedicated section](#audio-inputs).

Refer to `advent -h` for full synopsys.

### Database Service Tool (db-djv-pg)

New jingles are fingerprinted following the regular Dejavu process (see [Fingerprinting](https://github.com/denis-stepanov/dejavu#fingerprinting)). Unfortunately, Dejavu does not provide a mechanism to share database content. To facilitate manipulations with the database, a service tool `db-djv-pg` is included with AdVent. It allows exporting / importing jingles as text files of [specific format](https://github.com/denis-stepanov/advent-db#jingle-hash-file-format-djv). Of the two databases supported by Dejavu only PostgreSQL is supported (hence the `-pg` in the name). AdVent does not alter Dejavu database schema; additional information needed for AdVent functioning is encoded in the jingle name.

The tool allows for the following operations on jingles (aka "tracks"):

- `list` - list tracks available in the database
- `export` - export tracks from database to files
- `import` - import tracks from files to database
- `delete` - delete tracks from database

Remaining parameters are jingle names, or masks using simple regular expression syntax (`*`, `?`). `import` takes file names as parameters; other commands operate on track names (without file extension). When using track name regular expressions in shell, remember to protect them from shell expansion using quotes.

The tool by default does not overwrite existing tracks in any direction; if this is desired, pass the `-o` option.

Examples of use:
```
# List database content
(advent-pyenv) $ db-djv-pg list

# Export TF1 channel jingles
(advent-pyenv) $ db-djv-pg export "FR_TF1*"

# Import all jingles in the current directory, overwriting existing ones
# Note that escaping shall not be used in this case
(advent-pyenv) $ db-djv-pg import -o *

# Delete one jingle
(advent-pyenv) $ db-djv-pg delete FR_TF1_220205_EVENING1_2
```

Refer to `db-djv-pg -h` for exact synopsis.

## Installation

The installation was tested on Fedora and Raspbian. The differences are marked below accordingly.

Dejavu supports MySQL and PostgreSQL, with default being MySQL. Unfortunately(?), I am much more fluent with PostgreSQL, so AdVent supports PostgreSQL only (sorry MySQL folks :-) ). Setup process is a bit long, mostly because PostgreSQL and Dejavu are not readily usable pieces of software. Some of these steps are covered in (a bit dated) [Dejavu original manual](https://github.com/denis-stepanov/dejavu/blob/master/INSTALLATION.md), but I reiterate here for completeness.

* `#` prompt means execution from root
* `$` prompt means execution from user
* `(advent-pyenv) $` prompt means execution from user in a [Python virtual environment](https://docs.python.org/3/library/venv.html)

### Step 1: Install non-Python Dejavu dependencies

Fedora:
```
# dnf install postgresql-server ffmpeg portaudio-devel
```

Raspbian:
```
$ sudo apt-get install postgresql-11 ffmpeg libatlas-base-dev
```

### Step 2: Configure services

If you happen to have PostgreSQL running already, skip this step.

Default PostgreSQL in Fedora has a ridiculously conservative setup, so you have some work to do to get it up and running. On Raspbian, this step is automatic; just skip it.

Initialize PostgreSQL:

```
# postgresql-setup --initdb
```

Allow localhost connections using password. As `root`, edit `/var/lib/pgsql/data/pg_hba.conf` to change `ident` method to `md5`:

```
< host    all             all             127.0.0.1/32            ident
---
> host    all             all             127.0.0.1/32            md5
```

Add PostgreSQL to auto-start and run it:

```
# systemctl enable postgresql
# systemctl start postgresql
```

One more word on services. Recent Fedoras bring up a particularly agressive OOMD (out-of-memory killer daemon). Despite the name, memory is not its only concern. It regularly tries shooting to death my busy Firefox in the midst of a morning coffee sip. Because AdVent is a CPU-intensive application, OOMD will try taking its life too. If you observe AdVent silently exiting after some time, you know the reason. Probably, there is a way to make an exception, but in absence of a better solution, I just disarm:

```
# systemctl stop systemd-oomd
# systemctl mask systemd-oomd
```

### Step 3: Set up a database for AdVent

Create a database user:

```
# sudo -u postgres createuser -P advent
Enter password for new role: (enter "advent")
Enter it again: (enter "advent")
#
```

Create an empty database with `advent` user owning it:

```
# sudo -u postgres createdb -O advent advent
```

Whoooah... so much for PostgreSQL.

On Raspbian, this step is the same, but you do not have to be `root` to run `sudo`.

### Step 4: Install Python virtual environment for Dejavu

The latest Dejavu mainstream does not run on Python 3.10 shipped with Fedora 36 (pull requests are welcome), so we need a virtual environment for Python 3.7:

Fedora:
```
# dnf install python3.7 python3-virtualenv
```

On Raspbian 10, Python is already - quite conveniently - 3.7, and support for virtual environment is installed by default.

Create virtual environment:
```
$ python3.7 -m venv --system-site-packages advent-pyenv
$ source advent-pyenv/bin/activate
(advent-pyenv) $
```

### Step 5: Install Dejavu and AdVent

[My clone of Dejavu](https://github.com/denis-stepanov/dejavu) includes several non-functional adjustments allowing better co-habitation with AdVent, so I recommend using it instead of the upstream copy:

```
(advent-pyenv) $ pip install https://github.com/denis-stepanov/dejavu/zipball/tags/0.1.3-ds1.1.2   # or any latest tag
(advent-pyenv) $ pip install https://github.com/denis-stepanov/advent/zipball/main  # or any stable tag
```

### Step 6: Populate AdVent database

At this moment the database is void of any schema, not to say data. One can trick Dejavu into creating a database schema by asking it to scan something. The error message is not important:

```
(advent-pyenv) $ dejavu -f .
Please specify an extension if you'd like to fingerprint a directory!
(advent-pyenv) $
```

Now it's data's turn. Pull and load the latest snapshot of ad fingerprints. See more details on this in [AdVent DB pages](https://github.com/denis-stepanov/advent-db#database-population-or-update-for-regular-users):

```
(advent-pyenv) $ git clone https://github.com/denis-stepanov/advent-db.git
(advent-pyenv) $ find advent-db -name "*.djv" | xargs db-djv-pg import
```

If you use PulseAudio for TV control (default), you are all set. If you would like to use extra hardware, such as S/PDIF digital input, or Logitech Harmony Hub for TV control, see below for additional instructions.

## Audio Inputs

AdVent takes a system-wide default audio source as input. On modern Linux it is usually PulseAudio who takes care of sound services. If the system-wide source is not a suitable one, it has to be configured externally to AdVent (e.g., via `pavucontrol`). You can quickly check the list of available sources with:

```
$ pactl list sources short
```

Sections below detail particular configurations.

### PulseAudio

(coming soon)

### S/PDIF Digital Input

Supported on Raspberry Pi using [HiFiBerry Digi+ I/O](https://www.hifiberry.com/shop/boards/hifiberry-digi-io/) sound card.

![HiFiBerry Digi+ I/O](https://user-images.githubusercontent.com/22733222/180579980-93eefddf-c048-4be8-a4f6-eb30380d9b17.jpg)

With this card, one can use optical TOSLINK or coaxial RCA cables. I use an optical one, but RCA should work the same.

Setup compiled on the basis of the [original installation instruction](https://www.hifiberry.com/docs/software/configuring-linux-3-18-x/):

#### TV Setup

This sound card does not support Dolby Digital, so if the channels of interest in your area broadcast in Dolby, you need to enforce PCM on TV side. You can find out the audio format by looking at the TV channel information (`Info`, `Details`, etc). Refer to the instruction for your TV-set. Example of channels in PCM and in Dolby Digital:

![PCM vs Dolby Digital](https://user-images.githubusercontent.com/22733222/182946026-e3688570-c037-44f1-bfb7-260e6e179834.png)

In the case of Sony BRAVIA, adjusting the format can be done in `Digital Setup` > `Audio Setup` > `Optical Out`: change `Auto` to `PCM`:

![Forcing PCM on TV](https://user-images.githubusercontent.com/22733222/182959454-7439e1f9-4df9-4bfd-aab7-4032192ca357.jpg)

#### Raspberry Pi Setup

Edit `/boot/config.txt` to enable HiFiBerry and disable all other sound devices:

```
57c57
< dtparam=audio=on
---
> #dtparam=audio=on
61c61
< dtoverlay=vc4-fkms-v3d
---
> dtoverlay=vc4-fkms-v3d,audio=off
65a66,67
>
> dtoverlay=hifiberry-digi
```
S/PDIF PCM comes sampled in 48 kHz, while PulseAudio defaults to 44.1 kHz. If the sampling rate is not matched, recorder will see garbage. In addition, Dejavu inherently works in 44.1 kHz (the frequency setting it is not just a matter of input sampling, but is also used internally during recognition process). So the easiest way is to configure PulseAudio to a primary frequency of 48 kHz and to activate software down-sampling to 44.1 kHz. Edit `/etc/pulse/daemon.conf` to uncomment and enable these lines:

```
79a80
> default-sample-rate = 48000
80a82
> alternate-sample-rate = 44100
```
Now reboot:

```
$ sudo reboot
```

#### Testing

Check that system can see your sound card:

```
$ arecord -l
**** List of CAPTURE Hardware Devices ****
card 0: sndrpihifiberry [snd_rpi_hifiberry_digi], device 0: HifiBerry Digi HiFi wm8804-spdif-0 [HifiBerry Digi HiFi wm8804-spdif-0]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
```

Record a test track using default settings:

```
$ parecord -v test.wav
Opening a recording stream with sample specification 's16le 2ch 44100Hz' and channel map 'front-left,front-right'.
Connection established.
Stream successfully created.
Buffer metrics: maxlength=4194304, fragsize=352800
Using sample spec 's16le 2ch 44100Hz', channel map 'front-left,front-right'.
Connected to device alsa_input.platform-soc_sound.iec958-stereo (index: 1, suspended: no).
Time: 2.602 sec; Latency: 6901 usec.          
...
(Ctrl-C)
$ 
```
The resulting file `test.wav` recorded in 44.1 kHz shall reproduce TV sound correctly.

Note 1: HiFiBerry manuals recommend disabling all other audio devices, so you won't be able to listen to the recorded file right on the Pi. I just copy the file to another machine where I can playback. If this behavior is undesirable, play around with options in `/boot/config.txt`. Pay attention that the default input device remains the sound card; otherwise AdVent will not work.

Note 2: HifiBerry manuals strongly recommend against using PulseAudio in general, and against software re-sampling in particular, citing performance concerns. From my experience, PulseAudio is easy to configure (much easier than ALSA) and works well, but indeed, would consume ~5% of the Pi CPU (20% [if used from four threads](#streaming-problem), the other 80% would be eaten up by Dejavu). And all that is for entire PulseAudio machinery, not just for down-sampling; I find this very affordable. For sure, for purists it should be possible to eliminate this margin by turning PulseAudio off and going down to ALSA level; however, I have not pursued these roads too far:

a) configure down-sampling on the level of ALSA (something I could not easily make, but should be possible), or

b) hack Dejavu to consume 48 kHz directly. I actually tested that it works, but the impact on recognition efficiency is unclear. Jingle fingerprints are taken at 44.1 kHz, so one might expect side effects.

Another advantage of PulseAudio is that it allows access to a sound source from multiple processes. By default, it is usually only one process which can use a sound card. This is certainly true and [documented](https://www.hifiberry.com/docs/software/check-if-the-sound-card-is-in-use/) for HiFiBerry. AdVent runs several threads reading sound input in parallel. While these threads remain all part of the same process, it is unclear it it would still work through ALSA.

#### Other Raspberry Pi Considerations

As mentioned above, AdVent is a CPU-intensive application. This directly translates to increase of the Pi CPU temperature. Adding a sound card shield on top does not help with ventilation. You can check CPU temperature as follows:

```
$ vcgencmd measure_temp
temp=52.1'C
$ 
```

Be sure to observe temperature of your setup. In my case it rises from 50 to 60℃ when AdVent is running. Anything between 70 and 80℃ is a danger zone. Consider the following tips:

* make sure you have a good power supply (at least 3 A for Pi 4B; 3.5 A recommended);
* use heat sinks for principal chips (sold separately). I do have some; they are really helpful;
* if you put the entire device in a case, foresee active cooling (a fan).

## TV Controls

### PulseAudio

(coming soon)

### Logitech Harmony Hub

(selected with `-t harmonyhub` option to AdVent)

I have been using this device for TV control from a smartphone since long time. Apart from the default cloud interface, it can also provide a local API, which is convenient for AdVent needs.

![Logitech Harmony Hub](https://user-images.githubusercontent.com/22733222/180626764-788fca83-ede6-46e2-9b7c-7db087c13a4b.jpg)

#### Harmony Setup

The local API is not enabled by default; you need to activate it in Harmony application as follows: `Menu` > `Harmony Setup` > `Add/Edit Devices & Activities` > `Hub` > `Enable XMPP`.

![Harmony Hub XMPP](https://user-images.githubusercontent.com/22733222/180651641-57a719a1-ac53-4170-969f-f8e92409dc24.jpg)

#### Linux Setup

To talk to the Hub we will be using a nice piece of software called [Harmony API](https://github.com/maddox/harmony-api). It is a NodeJS server with HTTP interface running on your Linux box (in this case, next to AdVent). Follow these steps to set it up on Fedora (on Raspbian, just replace `root` `# ...` commands with `$ sudo ...`):

Unfortunately, Linux installer is not yet included in any release of Harmony API, so we need to pull the latest master:

```
$ git clone https://github.com/maddox/harmony-api.git
```

Pre-configure Harmony API:

```
# npm install forever -g
$ ./harmony-api/script/bootstrap
```

Install it system-wide using `root` permissions:

```
# ./harmony-api/script/install-linux
```

Sadly, this installation uses a non-canonical location placing executables in `/var/lib`, so SELinux on Fedora will be unhappy about it. Label the executable file as follows (not required on Raspbian which has got no SELinux):

```
# semanage fcontext -a -t var_run_t /var/lib/harmony-api/script/server
# restorecon -v /var/lib/harmony-api/script/server
```

Another Fedora-specific issue is its firewall which would by default block attempts to discover Hubs. Enable discovery port as follows (not required on Raspbian which has got no firewall):

```
# firewall-cmd --permanent --add-port=61991/tcp
```

Finally, we can start our server:

```
# systemctl start harmony-api-server
```

#### Testing

Run this command to test TV control:

```
$ curl -s -S -d on -X POST http://localhost:8282/hubs/harmony/commands/mute
```

It shoud mute the TV. Run it again to unmute.

Note that AdVent relies on default Hub name which is `Harmony`. If your Hub name is different, the name needs to be corrected in the source code (and in the test command above). It there will be demand, it is possible to make a command line option for this.

## Privacy Statement (for paranoids)

TV video input is not connected nor used. Audio matching represents a completely in-memory operation (no audio recording of any kind is performed), and a local copy of the online database is used for matching (no active network connection needed), so the information on what a person is watching on TV does not leave the local controller, and is not logged in any form on its persistent storage medium.
