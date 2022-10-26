#!/usr/bin/env python3

import os
import sys
import argparse
import psycopg2
import psycopg2.extras
import csv

FORMAT = "djv"
FORMAT_VERSION = 1

# Must match Dejavu presets; see https://github.com/denis-stepanov/advent#dejavu-tuning
DEFAULT_WINDOW_SIZE = 1024
DEFAULT_OVERLAP_RATIO = 0.75
DEFAULT_FS = 44100

# TODO: load this from config file
DB_HOST = "localhost"
DB_NAME = "advent"
DB_USER = "advent"
DB_PASSWORD = "advent"

TERM_WIDTH = 50

def res_str(res = False):
    return 'FAILED' if res else 'OK'

def print_check_result(msg = "UNKNOWN", res = False, offset = 2):
    for i in range(offset):
        print(" ", end = '')
    print(msg, end = '')
    for i in range(TERM_WIDTH - len(msg)):
        print(" ", end = '')
    print(f": {res_str(res)}")

# Return False or 0 if no issue
def db_check(cursor, query, msg):
    cursor.execute(query)
    res = cursor.fetchone()[0]
    print_check_result(msg, res)
    return res

def main():
    RETURN_CODE = 0

    parser = argparse.ArgumentParser(description='Process Dejavu tracks in PGSQL database',
        epilog='Use "COMMAND -h" to get command-specific help')
    subparsers = parser.add_subparsers(dest='cmd', required=True, metavar='COMMAND')
    parser_list   = subparsers.add_parser('list', help='list tracks')
    parser_export = subparsers.add_parser('export', help='export tracks')
    parser_import = subparsers.add_parser('import', help='import tracks')
    parser_delete = subparsers.add_parser('delete', help='delete tracks')
    parser_dbinfo = subparsers.add_parser('dbinfo', help='show database info')

    parser_list.add_argument  ('filter', help='filter name using simple pattern matching (*, ?; default: * == all)', nargs='?', default='*')
    parser_export.add_argument('filter', help='filter name using simple pattern matching (*, ?; default: * == all)', nargs='?', default='*')
    parser_export.add_argument('-o', '--overwrite', action='store_true', help='overwrite existing tracks');
    parser_import.add_argument('filter', metavar='FILE', help='.' + FORMAT + ' file to import', nargs='+')
    parser_import.add_argument('-o', '--overwrite', action='store_true', help='overwrite existing tracks');
    # NB: technically, "?" does not mean "none" but all tracks with one char name, but normally we should not have any
    parser_delete.add_argument('filter', help='filter name using simple pattern matching (*, ?; default: ? == none)', nargs='?', default='?')
    parser_dbinfo.add_argument('-c', '--check', action='store_true', help='check database consistency');
    args = parser.parse_args()

    conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")

    with conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        if args.cmd == 'export' or args.cmd == 'list':

            # Fetch tracks
            cur.execute("SELECT * FROM songs WHERE song_name LIKE %s ORDER BY song_name", (args.filter.translate({42: 37, 63: 95}),))
            if cur.rowcount:
                for song in cur:
                    print(f"{song['song_name']}", end="")
                    if args.cmd == 'list':
                        print()
                        continue

                    fname = song['song_name'] + "." + FORMAT
                    if not args.overwrite and os.path.exists(fname):
                        print(" (exists; skipped)")
                        continue

                    with open(fname, mode='w') as djv_file:
                        djv_writer = csv.writer(djv_file)
                        djv_writer.writerow([FORMAT, FORMAT_VERSION])
                        djv_writer.writerow([song['song_name'], song['fingerprinted'], bytes(song['file_sha1']).hex(), song['total_hashes']])
                        song_id = song['song_id']

                        # Fetch fingerprints
                        cur2 = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                        cur2.execute("SELECT * FROM fingerprints WHERE song_id = %s ORDER BY fingerprints.offset, hash", (song_id,))
                        for fingerprint in cur2:
                            djv_writer.writerow([fingerprint['offset'], bytes(fingerprint['hash']).hex()])
                        cur2.close()
                    print()
            else:
                print("No records found")

        if args.cmd == 'import':
            for fname in args.filter:
                print(f"{fname}: ", end="")
                if os.path.exists(fname):
                    with open(fname, newline='') as djv_file:
                        djv_reader = csv.reader(djv_file)
                        row = next(djv_reader)
                        if row[0] != FORMAT:
                            print(f"(unknown format: '{row[0]}'; skipped)");
                            continue
                        if int(row[1]) > FORMAT_VERSION:
                            print(f"(unsupported version: {row[1]}; skipped)");
                            continue
                        # TODO: more checks

                        song = next(djv_reader)
                        song_name     = song[0]
                        fingerprinted = song[1]
                        file_sha1     = song[2]
                        total_hashes  = song[3]
                        print(song_name, end="")

                        cur.execute("SELECT COUNT(*) FROM songs WHERE song_name = %s", (song_name,))
                        if int(cur.fetchone()[0]) > 0:
                            if args.overwrite:
                                cur.execute("DELETE FROM songs WHERE song_name = %s", (song_name,))
                            else:
                                print(" (exists; skipped)")
                                continue

                        cur.execute("INSERT INTO songs (song_name, fingerprinted, file_sha1, total_hashes) VALUES (%s, %s, %s, %s) RETURNING song_id",
                            (song_name, int(fingerprinted), bytes.fromhex(file_sha1), int(total_hashes)))
                        song_id = int(cur.fetchone()[0])

                        for fingerprint in djv_reader:
                            offset = fingerprint[0]
                            hash = fingerprint[1]

                            cur.execute("INSERT INTO fingerprints (song_id, \"offset\", hash) VALUES (%s, %s, %s)",
                                (song_id, int(offset), bytes.fromhex(hash)))

                        conn.commit()

                    print()
                else:
                    print("(file not found)")

        if args.cmd == 'delete':
            cur.execute("DELETE FROM songs WHERE song_name LIKE %s RETURNING song_name", (args.filter.translate({42: 37, 63: 95}),))
            conn.commit()
            if cur.rowcount:
                for song in cur:
                    print(song['song_name'])
            else:
                print("No records found")

        if args.cmd == 'dbinfo':
            print("Dejavu database info:")

            cur.execute("SELECT COUNT(song_id) AS n_tracks, SUM(fingerprinted) AS n_ftracks, SUM(total_hashes) AS n_hashes FROM songs")
            songs = cur.fetchone()
            print(f"  Fingerprinted / total tracks = {songs['n_ftracks']} / {songs['n_tracks']}")

            cur.execute("SELECT COUNT(DISTINCT(song_id, \"offset\")) FROM fingerprints")
            peak_groups = cur.fetchone()[0]
            print(f"  Peak groups                  = {peak_groups}", end='')
            if songs['n_ftracks'] != 0:
                print(f" (avg. ~= {round(peak_groups / songs['n_ftracks'])} per track)")
            else:
                print()
            print(f"  Fingerprints                 = {songs['n_hashes']}", end='')
            if songs['n_ftracks'] != 0:
                print(f" (avg. ~= {round(songs['n_hashes'] / songs['n_ftracks'])} per track)")
            else:
                print()

            cur.execute("SELECT ROUND(SUM(max_offset) * %s * (1 - %s) / %s) FROM (SELECT MAX(\"offset\") AS max_offset FROM fingerprints GROUP BY song_id) AS offsets", (DEFAULT_WINDOW_SIZE, DEFAULT_OVERLAP_RATIO, DEFAULT_FS))
            times = cur.fetchone()[0]
            print(f"  Total fingerprinted time    ~= {times} s", end='')
            if songs['n_ftracks'] != 0:
                print(f" (avg. ~= {round(times / songs['n_ftracks'], 1)} s per track)")
            else:
                print()

            cur.execute("SELECT pg_database_size(%s) AS size, pg_size_pretty(pg_database_size(%s)) AS size_pretty", (DB_NAME, DB_NAME))
            db_size = cur.fetchone()
            print(f"  Database size               ~= {db_size['size_pretty']}", end='')
            if songs['n_ftracks'] != 0:
                print(f" (avg. ~= {round(db_size['size'] / 1024 / 1024 / songs['n_ftracks'], 2)} MB per track)")
            else:
                print()

            if times != 0:
                print(f"  Fingerprinting frequency    ~= {round(songs['n_hashes'] / times)} Hz (~= {round(100 * songs['n_hashes'] / times / DEFAULT_FS, 2)}% of sampling frequency {DEFAULT_FS} Hz)")
            else:
                print("  Fingerprinting frequency      = n/a")

            cur.execute("SELECT MIN(LENGTH(hash)), MAX(LENGTH(hash)) FROM fingerprints")
            hashes = cur.fetchone()
            min_size = int(hashes['min'])
            max_size = int(hashes['max'])
            if max_size != min_size:
                print(f"  Hash size                    = {min_size}-{max_size} B")
            else:
                print(f"  Hash size                    = {min_size} B")

            cur.execute("SELECT CASE WHEN COUNT(hash) <> 0 THEN ROUND((COUNT(hash) - COUNT(DISTINCT(hash))) * 100::NUMERIC / COUNT(hash), 2) ELSE 101 END FROM fingerprints")
            col_rate = float(cur.fetchone()[0])
            if col_rate <= 100:
                print(f"  Hash collisions             ~= {col_rate}%")
            else:
                print("  Hash collisions               = n/a")

            cur.execute("SELECT date_trunc('second', LEAST(MIN(s.date_created), MIN(s.date_modified), MIN(f.date_created), MIN(f.date_modified))) FROM songs s, fingerprints f WHERE f.song_id = s.song_id")
            print(f"  First update                ~= {cur.fetchone()[0]}")
            cur.execute("SELECT date_trunc('second', GREATEST(MAX(s.date_created), MAX(s.date_modified), MAX(f.date_created), MAX(f.date_modified))) FROM songs s, fingerprints f WHERE f.song_id = s.song_id")
            print(f"  Last update                 ~= {cur.fetchone()[0]}")

            cur.execute("SELECT date_trunc('second', GREATEST(last_vacuum, last_autovacuum)::TIMESTAMP) FROM pg_stat_user_tables WHERE relname = 'fingerprints'")
            print(f"  Last vacuum                 ~= {cur.fetchone()[0]}")

            ## AdVent-specific info
            if DB_USER == 'advent':
                print("\nAdVent database info:")

                cur.execute("SELECT COUNT(DISTINCT(split_part(song_name, '_', 1))) FROM songs")
                countries = cur.fetchone()[0]
                print(f"  Countries                    = {countries}")

                cur.execute("SELECT COUNT(DISTINCT(split_part(song_name, '_', 1) || '_' || split_part(song_name, '_', 2))) FROM songs")
                channels = cur.fetchone()[0]
                print(f"  TV channels                  = {channels}", end="")
                if countries != 0:
                    print(f" (avg. ~= {round(channels / countries)} per country)")
                else:
                    print()

                print(f"  Jingles                      = {songs['n_ftracks']}", end="")
                if channels != 0:
                    print(f" (avg. ~= {round(songs['n_ftracks'] / channels)} per TV channel)")
                else:
                    print()

                cur.execute("SELECT SUM(CASE WHEN split_part(song_name, '_', 5) = '1' THEN 1 ELSE 0 END) FROM songs")
                pure_entry = cur.fetchone()[0]
                cur.execute("SELECT SUM(split_part(song_name, '_', 5)::INTEGER & 1) FROM songs")
                print(f"  Pure entry / entry jingles   = {pure_entry} / {cur.fetchone()[0]}")

                cur.execute("SELECT SUM(CASE WHEN split_part(song_name, '_', 5) = '2' THEN 1 ELSE 0 END) FROM songs")
                pure_exit = cur.fetchone()[0]
                cur.execute("SELECT SUM(split_part(song_name, '_', 5)::INTEGER & 2 >> 1) FROM songs")
                print(f"  Pure exit / exit jingles     = {pure_exit} / {cur.fetchone()[0]}")

                cur.execute("SELECT SUM(CASE WHEN split_part(song_name, '_', 5)::INTEGER & 3 = 0 THEN 1 ELSE 0 END) FROM songs")
                print(f"  No action jingles            = {cur.fetchone()[0]}")

                cur.execute("WITH song_dates AS (SELECT MIN(split_part(song_name, '_', 3)) AS min_date FROM songs) SELECT '20' || substring(min_date FOR 2) || '-' || substring(min_date FROM 3 FOR 2) || '-' || substring(min_date FROM 5 FOR 2) FROM song_dates")
                if cur.rowcount != 0:
                    print(f"  Time coverage from           = {cur.fetchone()[0]}")
                else:
                    print(f"  Time coverage from           = n/a")

                cur.execute("WITH song_dates AS (SELECT MAX(split_part(song_name, '_', 3)) AS min_date FROM songs) SELECT '20' || substring(min_date FOR 2) || '-' || substring(min_date FROM 3 FOR 2) || '-' || substring(min_date FROM 5 FOR 2) FROM song_dates")
                if cur.rowcount != 0:
                    print(f"  Time coverage till           = {cur.fetchone()[0]}")
                else:
                    print(f"  Time coverage till           = n/a")

            # DB checks
            ## By convention, a query shall return 0 or false() if no problem detected
            if args.check:
                print("\nDatabase health checks:")
                db_problem = False

                res = db_check(cur,
                    "SELECT COUNT(*) FROM songs s, fingerprints f WHERE f.song_id = s.song_id and GREATEST(s.date_created, s.date_modified, f.date_created, f.date_modified) > now()",
                    "D0010: timestamps in future")
                db_problem = db_problem or res

                res = db_check(cur,
                    "SELECT count(*) FROM (SELECT date_created FROM songs WHERE date_created > date_modified UNION SELECT date_created FROM fingerprints WHERE date_created > date_modified) AS dates",
                    "D0011: created > modified")
                db_problem = db_problem or res

                res = db_check(cur,
                    "SELECT COUNT(*) FROM songs s1, songs s2 WHERE s1.song_name = s2.song_name AND s1.file_sha1 <> s2.file_sha1",
                    "D0020: same song name, different SHA1")
                db_problem = db_problem or res

                res = db_check(cur,
                    "SELECT COUNT(*) FROM songs s1, songs s2 WHERE s1.file_sha1 = s2.file_sha1 AND s1.song_name <> s2.song_name",
                    "D0021: same SHA1, different song name")
                db_problem = db_problem or res

                res = db_check(cur,
                    "SELECT COUNT(*) FROM songs WHERE fingerprinted <> 0 AND total_hashes = 0",
                    "D0030: fingerprinted without fingerprints")
                db_problem = db_problem or res

                res = db_check(cur,
                    "SELECT (SELECT SUM(total_hashes) FROM songs) <> (SELECT COUNT(*) FROM fingerprints)",
                    "D0035: fingerprint counts mismatch")
                db_problem = db_problem or res

                res = db_check(cur,
                    "SELECT (SELECT MIN(LENGTH(hash)) FROM fingerprints) <> (SELECT MAX(LENGTH(hash)) FROM fingerprints)",
                    "D0040: fingerprint hashes of variable size")
                db_problem = db_problem or res

                res = db_check(cur,
                    "SELECT n_ins_since_vacuum + n_dead_tup FROM pg_stat_user_tables WHERE relname = 'fingerprints'",
                    "D0100: vacuum needed")
                db_problem = db_problem or res

                ## AdVent-specific checks
                if DB_USER == 'advent':

                    res = db_check(cur,
                        "SELECT COUNT(*) FROM songs WHERE fingerprinted = 0",
                        "A0010: non-fingerprinted tracks")
                    db_problem = db_problem or res

                    res = db_check(cur,
                        "SELECT COUNT(*) FROM songs WHERE total_hashes < 500",
                        "A0020: low confidence tracks")
                    db_problem = db_problem or res

                    res = db_check(cur,
                        "SELECT COUNT(*) FROM songs WHERE LENGTH(song_name) - LENGTH(translate(song_name, '_', '')) <> 4",
                        "A0050: bad track name format")
                    db_problem = db_problem or res

                    # Rudimentary check, because difficult to make it natively with Postgres
                    res = db_check(cur,
                        "SELECT COUNT(*) FROM songs WHERE split_part(song_name, '_', 3) !~ '^\d{2}(([0][1-9])|([1][0-2]))(([0-2][0-9])|([3][0-1]))$'",
                        "A0051: bad track date format")
                    db_problem = db_problem or res

                    res = db_check(cur,
                        "SELECT COUNT(*) FROM songs WHERE NOT(split_part(song_name, '_', 5)::INTEGER BETWEEN 0 AND 3)",
                        "A0080: bad flags")
                    db_problem = db_problem or res

                print("  ", end = '')
                for i in range(TERM_WIDTH):
                    print("-", end = '')
                print("+-------")
                print_check_result("TOTAL CHECKS", db_problem)
                RETURN_CODE = 2 if db_problem else 0

        cur.close()
        return RETURN_CODE

    return 1

if __name__ == '__main__':
    main()
