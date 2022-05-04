# AdVent
This program mutes TV commercials by detecting ad jingles in the input audio stream.

**!Work in progress!** Incomplete manual, no installation guide... not yet usable by external user, but you've got the idea.

## Jingle Naming Convention

```
11_2..2_333333_4..4_5..5.ext
FR_TF1_220214_EVENING1_0.djv
```

1. [ISO 3166](https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes) two letter country code
2. TV channel name
3. Jingle capture date YYMMDD (approximate if unsure)
4. Jingle name (free format, alphanumeric)
5. Binary flags in hex
   1. 0x1 - Jingle starts the ads (0 if unknown)
   2. 0x2 - Jingle ends the ads (0 if unknown)
   3. ...
6. File extension indicates recognizer provider
   1. djv - [Dejavu](https://github.com/denis-stepanov/dejavu)

## Jingle Hash File Format (.djv)

Variable CSV (comma-separated) format is used.

The first line describes the format:
```
<format>,<format_version>
```
The only supported format is `djv`. Current format version is `1`. Backward compatibility (reading files of older formats) is supported; forward compatibility (reading files of newer formats) is not supported.

The second line describes the jingle:
```
<name>,<fingerprinted>,<file_hash>,<num_fingerprints>
```
`name` is the full name of the jingle, as [defined above](https://github.com/denis-stepanov/advent/edit/main/README.md#jingle-naming-convention) (omitting file extension). It is expected (but not required) that the name as stored in the file corresponds to the file name. `fingerprinted` is a flag `0`/`1` from the Dejavu database; it should read `1` in all regular AdVent usage scenarios. `file_hash` is a SHA1 hash of the audio file once submitted to Dejavu. `num_fingerprints` is a number of fingerprints generated for the jingle.

The remaining lines are individual fingerprints. Their number should correspond to the number of fingerprints defined.
```
<offset>,<hash>
```
`offset` is a fingerprint offset inside the jingle. `hash` is a fingerprint itself. It is normal to have several fingerprints for the same offset. The order of the fingerprint lines in the file is not important; for reproducibility of export they are ordered on save.

Example of a file `FR_TF1_220205_EVENING1_2.djv`:
```
djv,1
FR_TF1_220205_EVENING1_2,1,8cf22931d2f8cbfb9439fc0eb6a123bb679b6b16,227
6,138160992563d4b07bb7
6,541d5e0da358554a10da
(.. 225 more lines ..)
```
## Database Service Tool (db-djv-pg.py)

New jingles are fingerprinted following the regular Dejavu process (see [Fingerprinting](https://github.com/denis-stepanov/dejavu#fingerprinting)). To facilitate manipulations with jingles database, a service tool is provided. It allows exporting / importing jingles as text files using the format described above. Of the two databases supported by Dejavu (PostgreSQL and MySQL) only PostgreSQL is supported (hence the `-pg` in the name). AdVent does not alter Dejavu database schema; additional information needed for AdVent functioning is encoded in the jingle name (see [Naming Convention](https://github.com/denis-stepanov/advent/edit/main/README.md#jingle-naming-convention) above).

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

# Import all jingles in the current directory, overwriting existing ones. Note that escaping shall not be used in this case
$ db-djv-pg.py import -o *

# Delete one jingle
$ db-djv-pg.py delete FR_TF1_220205_EVENING1_2
```

See `db-djv-pg.py -h` for exact synopsis.
