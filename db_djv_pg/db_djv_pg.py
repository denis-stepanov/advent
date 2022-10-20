#!/usr/bin/env python3

import os
import sys
import argparse
import psycopg2
import psycopg2.extras
import csv

FORMAT = "djv"
FORMAT_VERSION = 1
DB_HOST = "localhost"
DB_NAME = "advent"
DB_USER = "advent"
DB_PASSWORD = "advent"

def main():
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
            cur.execute("SELECT COUNT(song_id) AS n_tracks, SUM(total_hashes) AS n_hashes FROM songs")
            songs_agg = cur.fetchone()
            print(f"Tracks         : {songs_agg['n_tracks']}")

            cur.execute("SELECT COUNT(DISTINCT(song_id, \"offset\")) AS n_peak_groups FROM fingerprints")
            print(f"Peak groups    : {cur.fetchone()['n_peak_groups']}")
            print(f"Fingerprints   : {songs_agg['n_hashes']}")

            cur.execute("SELECT CASE WHEN COUNT(hash) <> 0 THEN ROUND((COUNT(hash) - COUNT(DISTINCT(hash))) * 100::NUMERIC / COUNT(hash), 2) ELSE 101 END AS col_rate FROM fingerprints")
            col_rate = float(cur.fetchone()['col_rate'])
            if col_rate <= 100:
                print(f"Hash collisions: {col_rate}%")
            else:
                print("Hash collisions: n/a")

            cur.execute("SELECT pg_size_pretty(pg_database_size(%s))", (DB_NAME,))
            print(f"Database size  : {cur.fetchone()['pg_size_pretty']}")

        cur.close()
        return 0

    return 1

if __name__ == '__main__':
    main()
