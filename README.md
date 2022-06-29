# AdVent
This program mutes TV commercials by detecting ad jingles in the input audio stream.

Watch AdVent in action (make sure to turn the video sound on):

https://user-images.githubusercontent.com/22733222/174403887-37918d1e-da37-4cf5-9d7b-b04677ce8e2a.mp4

Here AdVent is running next to a TV stream in browser, watched by a user using headphones. When an ad kicks in, AdVent cuts the sound. A bit jerky video is a result of me capturing demo video on a ten years old laptop.

Once the ads are over, AdVent turns the sound back on (not part of this demo).

**!Work in progress!** Incomplete manual, no installation guide... not yet usable by external user, but you've got the idea.

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

## Jingle Database

AdVent functions by comparing live sound with a database of known ad jingles using open source sound recognition software [DejaVu](https://github.com/denis-stepanov/dejavu). A database of jingles is available as a separate repository [AdVent Database](https://github.com/denis-stepanov/advent-db) and is open for contributions. See its [README](https://github.com/denis-stepanov/advent-db/blob/main/README.md) for installation instructions.

### Database Service Tool (db-djv-pg.py)

New jingles are fingerprinted following the regular Dejavu process (see [Fingerprinting](https://github.com/denis-stepanov/dejavu#fingerprinting)). To facilitate manipulations with jingles database, a service tool is provided. It allows exporting / importing jingles as text files using the format described above. Of the two databases supported by Dejavu (PostgreSQL and MySQL) only PostgreSQL is supported (hence the `-pg` in the name). AdVent does not alter Dejavu database schema; additional information needed for AdVent functioning is encoded in the jingle name.

The tool allows the following operations on jingles (aka "tracks"):

- `list` - list tracks available in the database
- `export` - export tracks from database to files
- `import` - import tracks from files to database
- `delete` - delete tracks from database

Remaining parameters are jingle names, or masks using simple regular expression syntax (`*`, `?`). `import` takes file names as parameters; other commands operate on track names (without file extension). When using track name regular expressions in shell, remember to protect them from shell expansion using quotes.

The tool by default does not overwrite existing tracks in any direction; if this is desired, pass the `-o` option.

Examples of use:
```
# List database content
$ db-djv-pg.py list

# Export TF1 channel jingles
$ db-djv-pg.py export "FR_TF1*"

# Import all jingles in the current directory, overwriting existing ones
# Note that escaping shall not be used in this case
$ db-djv-pg.py import -o *

# Delete one jingle
$ db-djv-pg.py delete FR_TF1_220205_EVENING1_2
```

See `db-djv-pg.py -h` for exact synopsis.
