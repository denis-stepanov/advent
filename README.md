# advent
This program mutes TV commercials by detecting ad jingles in the input audio stream.

**!Work in progress!** No manual, no installation guide... not yet usable by external user, but you've got the idea.

Jingle naming convention:

```
11_2..2_333333_4..4_5..5.ext
FR_TF1_220214_EVENING1_0.djv
```

1. [ISO 3166](https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes) two letter country code
2. TV channel name
3. Jingle capture date YYMMDD
4. Jingle name (free format, alphanumeric)
5. Binary flags in hex
   1. 0x1 - Jingle starts the ads (if unknown, do not put any)
   2. 0x2 - Jingle ends the ads (if unknown, do not put any)
   3. ...
6. File extension indicates recognizer provider
   1. djv - [Dejavu](https://github.com/denis-stepanov/dejavu)

`.djv` content is hashes from database; will be detailed later.
