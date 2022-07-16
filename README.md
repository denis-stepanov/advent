# AdVent
This program mutes TV commercials by detecting ad jingles in the input audio stream.

Watch AdVent in action (make sure to turn the video sound on):

https://user-images.githubusercontent.com/22733222/174403887-37918d1e-da37-4cf5-9d7b-b04677ce8e2a.mp4

Here AdVent is running next to a TV stream in browser, watched by a user using headphones. When an ad kicks in, AdVent cuts the sound. A bit jerky video is a result of me capturing demo video on a ten years old laptop.

Once the ads are over, AdVent turns the sound back on (not part of this demo).

AdVent functions by comparing live sound with a database of known ad jingles using open source sound recognition software [Dejavu](https://github.com/denis-stepanov/dejavu). A database of jingles is available as a separate repository [AdVent Database](https://github.com/denis-stepanov/advent-db) and is open for contributions.

## Supported Hardware
There are many different ways of watching TV these days. Currently supported audio inputs:

* video streaming in browser
* (planned) optical audio out from a TV

Supported TV controls:

* [PulseAudio](https://www.freedesktop.org/wiki/Software/PulseAudio/) (when watching TV on Linux)
* [Logitech Harmony Hub](https://support.myharmony.com/en-es/hub)
* (could be implemented if there's interest) IrDA TV control (vendor-specific)

Supported actions:

* sound on / off
* (could be implemented if there's interest) sound fade out / in
* (could be implemented if there's interest) changing a TV channel
* ...

It is possible to use unrelated inputs and outputs (e.g., cut a sound on a real TV-set while running AdVent over a TV web cast); however, in this case one has to accept potential time de-sync, which could be quite important (dozens of seconds, depending on a TV feed provider).

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

The default TV control is `pulseaudio`; you can alter this with `-t` option; e.g. `-t harmonyhub` will select HarmonyHub control instead. See `advent -h` for full synopsys.

### Database Service Tool (db-djv-pg)

New jingles are fingerprinted following the regular Dejavu process (see [Fingerprinting](https://github.com/denis-stepanov/dejavu#fingerprinting)). To facilitate manipulations with jingles database, a service tool is provided. It allows exporting / importing jingles as text files using the format described above. Of the two databases supported by Dejavu only PostgreSQL is supported (hence the `-pg` in the name). AdVent does not alter Dejavu database schema; additional information needed for AdVent functioning is encoded in the jingle name.

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

See `db-djv-pg -h` for exact synopsis.

## Installation

### Installation on a Recent Fedora (F36)

Dejavu supports MySQL and PostgreSQL, with default being MySQL. Unfortunately(?), I am much more fluent with PostgreSQL, so AdVent supports PostgreSQL only (sorry MySQL folks :-) ). Setup process is a bit long, mostly because PostgreSQL and Dejavu are not readily usable pieces of software. Some of these steps are covered in (a bit dated) [Dejavu original manual](https://github.com/denis-stepanov/dejavu/blob/master/INSTALLATION.md), but I reiterate here for completeness.

* `#` prompt means execution from root
* `$` prompt means execution from user
* `(advent-pyenv) $` prompt means execution from user in a [Python virtual environment](https://docs.python.org/3/library/venv.html)

1) Install non-Python Dejavu dependencies:

```
# dnf install postgresql-server ffmpeg
```

2) Configure services. If you happen to have PostgreSQL running already, skip this step.

Default PostgreSQL in Fedora has a ridiculously conservative setup. So you have quite some work to get it up and running.

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

2a) One more word on services. Recent Fedoras bring up a particularly agressive OOMD (out-of-memory killer daemon). Despite the name, memory is not its only concern. It regularly tries shooting to death my busy Firefox in the midst of a morning coffee sip. Because AdVent is a CPU-intensive application, OOMD will try taking its life too. If you observe AdVent silently exiting after some time, you know the reason. Probably, there is a way to make an exception, but in absence of a better solution, I just disarm:

```
# systemctl stop systemd-oomd
# systemctl mask systemd-oomd
```

3) Set up a database for AdVent:

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

4) Install Python virtual environment for Dejavu. The latest Dejavu mainstream does not run on Python 3.10 shipped with Fedora 36 (pull requests are welcome), so we need a virtual environment for Python 3.7:

```
# dnf install python3.7 python3-virtualenv
$ python3.7 -m venv --system-site-packages advent-pyenv
$ source advent-pyenv/bin/activate
(advent-pyenv) $
```

5) Install Dejavu and AdVent:

[My clone of Dejavu](https://github.com/denis-stepanov/dejavu) includes several non-functional adjustments allowing better co-habitation with AdVent, so I recommend using it instead of the upstream copy:

```
(advent-pyenv) $ pip install https://github.com/denis-stepanov/dejavu/zipball/tags/0.1.3-ds1.1.1   # or any latest tag
(advent-pyenv) $ pip install https://github.com/denis-stepanov/advent/zipball/main  # or any stable tag
```

6) Populate AdVent database:

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

If you use PulseAudio for TV control (default), you are all set. If you would like to use HarmonyHub, you are still not done!

(HarmonyHub instruction coming soon)

### Installation on Raspbian

Coming soon.
