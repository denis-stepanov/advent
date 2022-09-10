# AdVent
This program combats TV commercials on the fly by detecting ad jingles in the input audio stream and sending mute orders to a TV.

Watch AdVent in action (make sure to turn the video sound on):

https://user-images.githubusercontent.com/22733222/174403887-37918d1e-da37-4cf5-9d7b-b04677ce8e2a.mp4

Here AdVent is running next to a TV stream in browser, watched by a user using headphones. When an ad kicks in, AdVent cuts the sound. A bit jerky video is a result of me capturing demo video on a ten years old laptop.

Once the ads are over, AdVent turns the sound back on (not part of this demo).

AdVent functions by comparing live sound with a database of known ad jingles using open source sound recognition software [Dejavu](https://github.com/denis-stepanov/dejavu). Because of Dejavu doing all the heavy lifting, AdVent code is ridiculously small - the core consists of circa 50 lines of code; the rest being nice-to-have sugar. A database of jingles is available as a separate repository [AdVent Database](https://github.com/denis-stepanov/advent-db) and is open for contributions. There is no need to inform AdVent of which exact channel you are watching - it will probe for all known channels simultaneously.

AdVent on a Raspberry Pi controlling a Sony BRAVIA TV-set:

![AdVent on Raspberry Pi](https://user-images.githubusercontent.com/22733222/180578361-5f08129c-bd5b-498e-8b03-324fc9c2b74d.jpg)

## How Stuff Works

Diagram below shows in blue a standard workflow for a person listening to a TV and muting TV sound with a remote.

![AdVent Workflow](https://user-images.githubusercontent.com/22733222/180874326-85a9d62a-3681-4ad0-b29a-7d356529fe8d.png)

AdVent is added in parallel (path in orange), using the same or similar tools for mute. The main difference is the audio source. The source should be different from the one that person hears, because AdVent needs to continue listening while the sound is muted. Obviously, this is required to be able to unmute later on. This is why a microphone is generally not a good source; it is better to feed something not affected by the `Mute` button of a TV. S/PDIF digital output of the TV is one good candidate.

### Limitations

Clearly, the approach of looking for ad jingles has inherent limitations:

* TV channels not using entry / exit jingles would not work (I do not have these in my reach);
* complex ad breaks (such as lasting for 20 mins and employing multiple jingles in between) would likely not work well (there are means to combat these too);
* very short jingles (< 1.5s) might have recognition issues (not seen in practice).

However, most TV channels I watch here in France do fall in line. So the mission was, taking into account these external limitations, make the rest working  - and working well. The particular use case of interest is the evening movie watching, where ad breaks are sparsed and of simple structure.

There is also a corner case if you decide to change channel during the commercial break muted by AdVent. It has no means to detect that the channel has been changed, so you would need to unmute manually, or via some sort of timeout (like in feature [#10](https://github.com/denis-stepanov/advent/issues/10)).

### Streaming Problem

The biggest problem with Dejavu is that it does not support continuous recognition from a stream. One has to define a recognition window. It kind of works when you have a four minutes song fingerprinted, and launch recognition anytime in the middle. It does not work well when your "song" is a three seconds jingle. So I opted for parallelized approach where there are overlapping threads listening for input in a sliding manner.

![Streaming Implementation](https://user-images.githubusercontent.com/22733222/181107790-0cb879a7-e7df-411c-b211-03a4ae8b40ea.png)

Question is how many threads would be needed. To understand this better I took a random three seconds jingle and tested its recognition once being split in two parts. Results:

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
<tr>
<td>0 s</td>
<td>3 s</td>
<td>100%</td>
</tr>
</table>

Unrelated track gives confidence of less than 10%.

From this we can draw some conclusions:

1. for good recognition, having 3 seconds fingerprinted is enough ([Dejavu's own estimate](https://github.com/denis-stepanov/dejavu#2-audio-over-laptop-microphone) is that 3 seconds fingerprinted gives 98% recognition confidence);
2. every contiguous 1.5 seconds (2 seconds better) shall be covered by at least one recognition attempt. Jingle minimal duration thus should not be inferior to 1.5 seconds;
3. 10% confidence looks like a good cut-off for a "hit".

So we can estimate that having three recognition threads running with one second interval over three seconds window (as on figure above) should give good enough coverage. These values have been recorded as default parameters in AdVent source code (there are command line options to alter them if needed). Due to inevitable imperfections of timing, I added one more thread just in case (see more details on this below). This gives four threads in total, actively working on recognition. This means that for AdVent to perform well, it should be run on at least four cores CPU, and on such a system it would create 100% system load (four threads occupying four cores). Most of modern systems would satisfy this requirement, Raspberry Pi included.

Because recognition process is not deterministic, threads originally spaced in time might drift and come closer to each other. This would diminish coverage and decrease effectiveness of recognition. To avoid this effect, a mutex is used which would prevent any recognition operation firing too close to another one from a parallel thread.

Another side effect from threading is that two closely running threads both yielding a hit can try flipping TV, which would cause problems at TV controls unit, as well as unpleasant user experience. To prevent this, a dead time is used (30 seconds by default), during which all actions on TV are disabled.

Finally, an implicit requirement coming from threading approach is that hardware audio source shall support concurrent use from threads. This is not granted in general case (see [below](#testing)).

Once the threading engine was ready, in order to confirm the number of threads needed, I undertook a specific test profiling recognition process of a jingle of 3.2 seconds long. Dejavu listening interval was 3 seconds, thread spacing was 1 second, and recognition confidence was 10%. The results are shown below:

![AdVent running 4 threads](https://user-images.githubusercontent.com/22733222/185672902-cde37f43-4aa4-4b34-8867-519ab6c3929d.png)

Here a green bar is the jingle; the red line is the time when the first hit was reported.

Observations:

1. there is a non-negligible "deadband" in Dejavu processing (marked with blue "tips" on the graph). For every 3 seconds recognition period, the actual recognition would take anytime between 3.2 and 3.5 seconds (on a 4 x 1200 MHz machine). Apparently, the engine just listens for 3 seconds and then does its jobs in the remaining time. So this deadband (currently recorded as a 0.4 seconds constant in the code - see issue [#24](https://github.com/denis-stepanov/advent/issues/24)) should be taken into account in calculations;
2. threads are respecting the minimal distance of 1 second between each other (mutex is working). Due to this the duty cycle of a thread is not 100% but close to 80%. This is not bad for a default setup, as it keeps machine loaded close to 100% but still leaves some time for OS to do other tasks;
3. new recognition starts not exactly at 1 second interval, but anytime between 1 and 1.1 seconds (because of `sleep(0.1)` when mutex cannot be taken). This error accumulates with time; but it is not very important for the purpose of the app.

Because of the above, the need for extra listening thread looks evident now. There are indeed periods of time where all four threads are active.

Another observation here is that in spite of good coverage of jingle interval, Dejavu recognition result turned out not to be as good as expected. My first thought was that Dejavu input might suffer from distortions due to concurrent access to the audio source. This has been studied in detail and multi-threading was found not to be at fault. So, maybe it was a good time to take a closer look at Dejavu itself.

### Dejavu Tuning

Dejavu has a configuration file `config/settings.py` which includes a few parameters to play with. They are well documented in the file, but still, changing them requires some knowledge of Dejavu internal process. Intuitively, if we want to improve recognition quality, we need to increase fingerprinting density (number of fingerprints per second of a track). And because we are working with very short tracks, the number must be significant. The density was measured on a sample track an was found to be about 85 fingerprints per second. So the parameters were adjusted as follows:

<pre>
CONNECTIVITY_MASK = 2
DEFAULT_FS = 44100
<b>DEFAULT_WINDOW_SIZE = 1024      # was 4096</b>
<b>DEFAULT_OVERLAP_RATIO = 0.75    # was 0.5</b>
<b>DEFAULT_FAN_VALUE = 15          # was 5</b>
DEFAULT_AMP_MIN = 10
PEAK_NEIGHBORHOOD_SIZE = 10
MIN_HASH_TIME_DELTA = 0
MAX_HASH_TIME_DELTA = 200
PEAK_SORT = True
FINGERPRINT_REDUCTION = 20
<b>TOPN = 1                        # was 2</b>
</pre>

`WINDOW_SIZE` is a sort of a "bucket" for frequencies in Fourier transform; making it smaller allows finer granularity when telling apart different frequences. Here we make the window four time smaller. Increasing `OVERLAP_RATIO` will take finer slices in time (we are interested in this) and, hence, return finer offsets (this bit is not interesting - AdVent does not use offset information). Here we raise overlap from 50% to 75%. Finally, `FAN_VALUE` reflects a space boundary for fingerprint neighborhood; increasing it allows for more potential combinations and, hence, more fingerprints. Here, we increase the distance by a factor of three. Applying all these settings together results in 485 fingerprints per seconds, i.e. about a factor five increase in density.

Now, does this improve efficiency? I made a small synthetic test by playing a jingle in the loop with pauses not aligned to 0.1 second (this is to make sure that threads do not run fully synchronously with playback). With confidence level of 5% the difference between old and new settings is not very visible, as both demonstrate close to 100% success in matching. However, things change when we request matching confidence of, say, 50%. In this case the old set gives only 45% success rate, while the new set gives 85% success rate - almost twofold difference.

`TOPN` is not related to fingerprinting; it defines how many nearest matches will be returned. This is two by default, but because AdVent only uses one, it makes sense to limit it on Dejavu level and save a bit of CPU cycles.

An obvious disadvantage of having more fingerprints is that database size will grow accordingly (in this case, by a factor of five), and the matching time ("Dejavu deadband") might increase. I tested it and did not observe a noticeable change (it remains in the order of 0.4 seconds for a three seconds track). Machine load was observed to be slightly higher, but not to the extent that could be realiably measured.

Note that changing Dejavu parameters has impact on fingerprint database. It is thus better to fix and not to change them in the process, or else the entire set of jingles might need re-processing. If you plan to play with these parameters, make sure to keep around copies of your original audio files.

## Supported Environment

There are many different ways of watching TV these days. Currently supported audio inputs:

* microphone;
* video streaming in browser (via [PulseAudio](https://www.freedesktop.org/wiki/Software/PulseAudio/) monitor). This is a default;
* [S/PDIF](https://en.wikipedia.org/wiki/S/PDIF) digital audio out from a TV-set: optical [TOSLINK](https://en.wikipedia.org/wiki/TOSLINK) or electrical [RCA](https://en.wikipedia.org/wiki/RCA_connector) (RCA untested but should work).


Supported TV controls:

* PulseAudio (when watching TV on Linux). This is a default;
* [Logitech Harmony Hub](https://support.myharmony.com/en-es/hub);
* (could be implemented if there's interest) IrDA TV control (vendor-specific).

Supported actions:

* sound on / off. This is a default;
* (could be implemented if there's interest - see issue [#14](https://github.com/denis-stepanov/advent/issues/14)) sound fade out / in;
* (could be implemented if there's interest - see issue [#15](https://github.com/denis-stepanov/advent/issues/15)) changing a TV channel;
* ...

Supported OS:

* recent Fedora (tested on Fedora 36). This is a default;
* Raspbian 10. Actually, it is less laborious to support than Fedora, as many problematic points are either non-existing on Raspbian, or implemented in more user-friendly way;
* (Windows is not supported but the majority of software is in Python; should work as is, with the exception of TV controls module which would need contributions and testing - see issue [#16](https://github.com/denis-stepanov/advent/issues/16)).

Not all combinations are supported; see below for the details.

It is even possible to use unrelated inputs and outputs (e.g., to cut a sound on a real TV-set while running AdVent over a TV web cast of the same channel); however, in this case one has to accept potential time de-sync, which could be quite important (dozens of seconds, depending on a TV feed provider).

## Usage

### AdVent (advent)

Runnig AdVent is as simple as:

```
(advent-pyenv) $ advent
```

(support to run as a daemon planned - see issue [#7](https://github.com/denis-stepanov/advent/issues/7)). Default settings are usually fine.

The output should resemble to this:

```
AdVent v1.3.0
TV control is pulseaudio
TV starts unmuted
Recognition interval is 3 s with confidence of 5%
Started 4 listening thread(s)
...:o::o::::::o::::::::::o::ooo
```

AdVent prints every second a character reflecting recognition progress. Meaning of characters:

* `.` - no signal (usually when there's silence or no input connected at all)
* `:` - signal but no match
* `o` - weak match
* `O` - strong match, also called a "hit". When a hit happens, AdVent prints hit details and may take some action on a TV

There is no standard way of exiting the application, as it is designed to run forever (this should be somewhat alleviated with issue [#8](https://github.com/denis-stepanov/advent/issues/8)). If you need to exit, press `Ctrl-C`; if that does not work, try harder with `Ctrl-\`.

The default TV control is `pulseaudio`; you can alter this with `-t` option; e.g. `-t harmonyhub` will select HarmonyHub control instead. `-t nil` will emulate TV control, i.e., make no real action. This is useful during [jingle fingerprinting process](https://github.com/denis-stepanov/advent-db#step-2-single-out-a-jingle-of-interest) and when testing AdVent itself.

There is no option to select an audio source; AdVent takes a system default. See more details on audio inputs in a [dedicated section](#audio-inputs).

`-n NUM_THREADS` option allows selecting a number of recognition threads to run. The offset between threads will be adjusted automatically. Default is the number of CPU cores available (which on end user computers - Raspberry Pi included - is very often 4). Increasing this number would improve coverage of jingles in the input stream, potentially improving recognition. However, making it significantly higher than the number of CPU cores available would likely not attain the desired result because of system starvation. Decreasing this number will decrease the system load but also decrease jingle coverage, increasing a chance to miss one. `-n 1` will result in single-thread execution, which would result in small fractions of input not submitted to recognition due to inevitable Dejavu deadband. 

`-i REC_INTERVAL` option allows adjusting the recognition window. It is recommended to keep it close to a typical duration of jingles of the TV channels of interest. The default is 3 seconds, which is more or less common duration; it should also work fairly well for jingles longer that that. Increasing this interval would increase Dejavu effectiveness (because it listens for longer) in expense of decreased effectiveness of AdVent (because threads would have a lower duty cycle), and vice versa. So the change would likely not have much impact, except for some specific cases, like working with very short or very long jingles. Going significantly above 5 seconds would likely diminish the overall efficiency, as majority of jingles are less than 5 seconds long. Going below 2 seconds runs at risk of breaking down Dejavu recognition process and generating many false positives or false negatives.

`-c REC_CONFIDENCE` option allows adjusting recognition confidence for a hit in the range of 0-100%. The default, selected experimentally, is 5%. Increasing this parameter will make AdVent less sensitive but more certain; decreasing it will make AdVent more sensitive but also increase a chance of having false positives. Selecting confidence of 0% would mean that anything non-silence will be taken as a hit.

`-l LOG_LEVEL` option will log recognition process into a file `advent.log`. Supported levels of logging are `none` (default), `events` and `debug`.

Refer to `advent -h` for full synopsys.

### Database Service Tool (db-djv-pg)

New jingles are fingerprinted following the regular Dejavu process (see ["Generate a Hash"](https://github.com/denis-stepanov/advent-db#step-3-generate-a-hash) in AdVent-DB). After the process they end up in an SQL database. Unfortunately, Dejavu does not provide a mechanism to share database content. To facilitate manipulations with the database, a service tool `db-djv-pg` is included with AdVent. It allows exporting / importing jingles as text files of [specific format](https://github.com/denis-stepanov/advent-db#jingle-hash-file-format-djv). Dejavu supports MySQL and PostgreSQL as databases, with default being MySQL. Unluckily(?), I am much more fluent with PostgreSQL, so AdVent supports PostgreSQL only (sorry MySQL folks :-); hence the `-pg` in the tool name. AdVent does not alter Dejavu database schema; additional information needed for AdVent functioning is encoded in the jingle name.

The tool allows for the following operations on jingles (aka "tracks"):

- `list` - list tracks available in the database
- `export` - export tracks from database to files
- `import` - import tracks from files to database
- `delete` - delete tracks from database
- (planned - issue [#3](https://github.com/denis-stepanov/advent/issues/3)) `rename` - rename tracks in the database

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

Installation was tested on Fedora and Raspbian. The differences are marked below accordingly. Setup process is a bit long, mostly because Dejavu and its database need some dependencies and configuration. Some of these steps are covered in (a bit dated) [Dejavu original manual](https://github.com/denis-stepanov/dejavu/blob/master/INSTALLATION.md), but I reiterate here for completeness.

* `#` prompt means execution from root
* `$` prompt means execution from user
* `(advent-pyenv) $` prompt means execution from user in a [Python virtual environment](https://docs.python.org/3/library/venv.html)

Differences in files are presented using `diff` notation, with `<` meaning old content and `>` meaning new content.

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

One more word on services. Recent Fedoras bring up a particularly agressive OOMD (out-of-memory killer daemon). Despite the name, memory is not its only concern. It regularly tries shooting to death my busy Firefox in the midst of a morning coffee sip. Because AdVent is a CPU-intensive application, OOMD will try taking its life too. If you observe AdVent silently exiting after some time, you know the reason. Probably, there is a way to make an exception, but because I do not like it anyway, I just disarm:

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

[My clone of Dejavu](https://github.com/denis-stepanov/dejavu) includes several non-functional adjustments allowing better co-habitation with AdVent, so I recommend using it instead of Dejavu upstream:

```
(advent-pyenv) $ pip install https://github.com/denis-stepanov/dejavu/zipball/tags/0.1.3-ds1.3.0   # or any latest tag
(advent-pyenv) $ pip install https://github.com/denis-stepanov/advent/zipball/main  # or any stable tag
```

### Step 6: Populate AdVent database

At this moment the database is void of any schema, not to say data. One can trick Dejavu into creating database schema by asking it to scan something. The error message is not important:

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
(the need to use `find` should go away with resolution of issue [#4](https://github.com/denis-stepanov/advent/issues/4))

This is all what concers AdVent per se. However, depending on your audio capturing options and on preferred way to control TV you might have additional work to do. See below for instructions.

## Audio Inputs

AdVent takes a system-wide default audio source as input. On modern Linux it is usually PulseAudio who takes care of sound services (yeah... Fedora has switched to PipeWire, but its [PulseAudio emulation layer](https://gitlab.freedesktop.org/pipewire/pipewire/-/wikis/Migrate-PulseAudio) is good enough for our purpose). You can check the default source as follows:

Fedora:

```
$ pactl get-default-source
alsa_input.pci-0000_00_1b.0.analog-stereo
$
```

Erf... not very descriptive. You can get more details by studying a lenghty output of:

```
$ pactl list sources
```

You can also use graphical tools like `pavucontrol` presenting audio configuration in a more user friendly way.

To check the default source on Raspbian:

```
$ pacmd list-sources | grep -B1 name:
    index: 0
        name: <alsa_output.platform-soc_sound.iec958-stereo.monitor>
--
  * index: 1
        name: <alsa_input.platform-soc_sound.iec958-stereo>
$
```

The source marked with an asterisk `*` is the default. Omit `grep` to see more details.

Sections below detail supported inputs.

### Capturing from a Microphone

This input has an inherent limitation in the sense that AdVent will mute but never unmute, as by muting it would silence its own input. This renders AdVent semi-functional, but it could be still useful in some scenarios. Another disadvantage of using a microphone is noisy sound decreasing recognition efficiency. On the other side, this input requires no wired connection to a TV-set. Also, on systems equipped with a mike it is usually set as default audio input, so no special setup is required to use it.

#### Testing

Turn on TV and test recording:

```
$ parecord -v test.wav
Opening a recording stream with sample specification 's16le 2ch 44100Hz' and channel map 'front-left,front-right'.
Connection established.
Stream successfully created.
Buffer metrics: maxlength=4194304, fragsize=352800
Using sample spec 's16le 2ch 44100Hz', channel map 'front-left,front-right'.
Connected to device alsa_input.pci-0000_00_1b.0.analog-stereo (index: 46, suspended: no).
Time: 5.888 sec; Latency: 1888172 usec.        
...
(Ctrl-C)
$
```

The resulting file should reproduce TV sound reasonably well. If not, try putting the microphone closer to the source, or use a better quality external microphone instead of a built-in one.

### Capturing a TV Web Cast

Instructions below are for Fedora. I do not have an equivalent for Raspbian, because I use Raspberry Pi to capture from a real TV rather than from Web.

Note that depending on your TV feed provider, live sound capturing might be considered as violation of provider's ToS. As a matter of fact, AdVent is not recording anything, but just listens to a live feed the same way a person would listen. To do this, we make use of PulseAudio "monitor" function, which allows using an audio output ("sink") as a source for another application.

#### PulseAudio Setup

Check the list of available audio sources:

```
$ pactl list short sources
45      alsa_output.pci-0000_00_1b.0.analog-stereo.monitor      PipeWire        s32le 2ch 48000Hz       IDLE
46      alsa_input.pci-0000_00_1b.0.analog-stereo       PipeWire        s32le 2ch 48000Hz       SUSPENDED
$
```

On laptops and alike, by default, the sound source used is a built-in mike (hiding behind `alsa_input.pci-0000_00_1b.0.analog-stereo` here). We need to switch the default to the speaker monitor (the exact label in your case may be different, but the `.monitor` part is important):

```
$ pactl set-default-source alsa_output.pci-0000_00_1b.0.analog-stereo.monitor
```

Big advantage of a "monitor" is that it samples sound before it goes to a sink. So muting a PulseAudio sink (see [TV Controls with PulseAudio](#tv-web-cast)) would let AdVent continue listening to the cast, [exactly as needed](#how-stuff-works). And, of course, the chain is fully digital, so no sound loss or distortion occurs.

#### Testing

Start your web cast and test recording:

```
$ parecord -v test.wav
Opening a recording stream with sample specification 's16le 2ch 44100Hz' and channel map 'front-left,front-right'.
Connection established.
Stream successfully created.
Buffer metrics: maxlength=4194304, fragsize=352800
Using sample spec 's16le 2ch 44100Hz', channel map 'front-left,front-right'.
Connected to device alsa_output.pci-0000_00_1b.0.analog-stereo.monitor (index: 45, suspended: no).
Time: 4.608 sec; Latency: 608164 usec.
...
(Ctrl-C)
$
```
The resulting file should reproduce TV sound correctly.

Note that PulseAudio tries to remember which sources applications use, so if you happened to run AdVent before, it might still not use the new default. The easiest way to confirm the source is to launch `pavucontrol` while AdVent is running and check in the "Recording" tab that it uses the "monitor" input:

![AdVent as seen in PAVUcontrol](https://user-images.githubusercontent.com/22733222/183268533-bafc2190-bc89-47ee-a4c8-a77a716ef04b.png)

Here, by the way, we can observe [three parallel threads](#streaming-problem) at work. The fourth one has a low duty cycle, so it comes and goes, causing some flickering in apps like `pavucontrol`.

### S/PDIF Digital Input

Supported on Raspberry Pi using [HiFiBerry Digi+ I/O](https://www.hifiberry.com/shop/boards/hifiberry-digi-io/) sound card.

![HiFiBerry Digi+ I/O](https://user-images.githubusercontent.com/22733222/180579980-93eefddf-c048-4be8-a4f6-eb30380d9b17.jpg)

With this card, one can use optical TOSLINK or coaxial RCA cables. I use an optical one, but RCA should work the same. On the following example of Sony BRAVIA the cable from the Pi needs to be connected to the port `F` (Digital Audio Out, Optical):

![TV Connection Diagram](https://user-images.githubusercontent.com/22733222/183753640-c41bbdb1-812e-40c4-a154-59e59c217610.png)

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
...
> default-sample-rate = 48000
...
> alternate-sample-rate = 44100
...
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
$
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

Note 1: HiFiBerry manuals recommend disabling all other audio devices, so you won't be able to listen to the recorded file right on the Pi (unless you hook up something PCM-enabled - like a home theater - to the output connector of HiFiBerry). I just copy the file to another machine where I can playback. If this behavior is undesirable, play around with options in `/boot/config.txt`. Pay attention that the default input device remains the sound card; otherwise AdVent will not work.

Note 2: HifiBerry manuals strongly recommend against using PulseAudio in general, and against software re-sampling in particular, citing performance concerns. From my experience, PulseAudio is easy to configure (much easier than ALSA) and works well, but indeed, would consume ~5% of the Pi CPU (20% [if used from four threads](#streaming-problem), the other 80% would be eaten up by Dejavu). And all that is for entire PulseAudio machinery, not just for down-sampling; I find this very affordable. For sure, for purists it should be possible to eliminate this margin by turning PulseAudio off and going down to ALSA level; however, I have not pursued these roads too far:

a) configure down-sampling on the level of ALSA (something I could not easily make, but should be possible), or

b) hack Dejavu to consume 48 kHz directly. I actually tested that it works, but the impact on recognition efficiency is unclear. Jingle fingerprints are taken at 44.1 kHz, so one might expect side effects. Dejavu has known bugs standing to date when working with sample rates different from 44.1 kHz.

Another advantage of PulseAudio is that it allows access to a sound source from multiple processes. By default, it is usually only one process which can use a sound card. This is certainly true and [documented](https://www.hifiberry.com/docs/software/check-if-the-sound-card-is-in-use/) for HiFiBerry. AdVent runs several threads reading sound input in parallel. While these threads remain all part of the same process, it is unclear if it would still work through ALSA.

#### Other Raspberry Pi Considerations

As mentioned above, AdVent is a CPU-intensive application. This directly translates to increase of the Pi CPU temperature. Adding a sound card shield on top does not help with ventilation either. You can check CPU temperature as follows:

```
$ vcgencmd measure_temp
temp=52.1'C
$ 
```

Be sure to observe temperature of your setup. In my case it rises from 50 to 60℃ when AdVent is running. Anything between 70 and 80℃ is a danger zone. Consider the following tips:

* make sure you have a good power supply (at least 3 A for Pi 4B; 3.5 A recommended);
* use heat sinks for principal chips (sold separately). I do have some; they are really helpful;
* if you put the entire device in a case, foresee active cooling (a fan).

![Raspberry Pi with Heat Sinks](https://user-images.githubusercontent.com/22733222/183757743-6d48f5ed-6b26-4fee-bde2-2d72fb8c3cfa.png)

## TV Controls

### TV Web Cast

(selected with `-t pulseaudio` option to AdVent; default)

"TV" control when watching a TV web cast on a computer consists of muting the currently active speaker. With PulseAudio it is as simple as:

```
$ pactl set-sink-mute @DEFAULT_SINK@ toggle
```

AdVent does just that. Another advantage with PulseAudio is that the application can query the status of speaker on startup and thus start in sync. There is often no way to do that with other TV controls, which are mostly unidirectional.

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

Alas, this installation uses a non-canonical location placing executables in `/var/lib`, so SELinux on Fedora would be unhappy about it. Label the executable file as follows (not required on Raspbian which has got no SELinux):

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

In a browser, open address `localhost:8282` (if you run the browser on a different machine, use the Harmony API machine's IP-address instead of `localhost`). In the section "Your Hubs" you should see your hub listed:

![Harmony API Web](https://user-images.githubusercontent.com/22733222/185488924-ac15fd43-52e3-45aa-bdc9-f301b86b6ec9.png)

_Caveat_: if you are coming out of cold boot like a power cycle, Pi might initialize itself faster than Harmony. In this case the hub would not be listed. The solution is to restart the `harmony-api-server`.

In a shell, run this command to test TV control:

```
$ curl -s -S -d on -X POST http://localhost:8282/hubs/harmony/commands/mute
```

It shoud mute the TV. Run it again to unmute.

_Caveat2_: this simplistic command will try muting all devices known to Harmony. Usually, there's only a TV, so it is not an issue. If you have got other devices hooked to Harmony, you might need to opt for a more precise path. Please open a ticket if you need support for this.

Note that AdVent relies on default Hub name which is `Harmony`. If your Hub name is different, the name needs to be corrected in the source code (and in the test command above). It there would be demand, it is possible to make a command line option for this (issue [#17](https://github.com/denis-stepanov/advent/issues/17)).

## Privacy Statement (for paranoids)

TV video input is not connected nor used. Audio matching represents a completely in-memory operation (no audio recording of any kind is performed), and a local copy of the online database is used for matching (no active network connection needed), so the information on what a person is watching on TV does not leave the local controller, and is not logged in any form on its persistent storage medium.
