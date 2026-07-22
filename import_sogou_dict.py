# -*- coding: utf-8 -*-
"""Sogou .scel dictionary importer for AI IME

Usage:
    python import_sogou_dict.py <scel_file_or_directory>

Parses Sogou .scel binary dictionary files and converts them to
AI IME's base_dict.txt format (pinyin<TAB>word<TAB>freq).

If a directory is given, all .scel files in it are imported.
Output is appended to ai_ime/data/sogou_imported.txt and merged
into base_dict.txt (deduped, keeping highest freq).

.scel format reference (reverse-engineered):
- Header: 0x130 bytes
- Pinyin table: starts at offset in header, each entry is a pinyin string
- Word entries: grouped by pinyin, each has word + frequency hint
"""
import os
import sys
import struct
import glob


def parse_scel(filepath):
    """Parse a Sogou .scel file and return [(pinyin, word, freq), ...]

    Returns list of (pinyin_str, word_str, freq_int) tuples.
    pinyin_str is space-separated like "ni hao".
    """
    with open(filepath, 'rb') as f:
        data = f.read()

    if len(data) < 0x130:
        print("  Error: file too small, not a valid .scel")
        return []

    # Check magic number
    # Sogou .scel files don't have a strong magic, but we can check some markers
    try:
        name = data[0x130:0x338].decode('utf-16-le').rstrip('\x00')
    except Exception:
        name = ""
    try:
        dtype = data[0x338:0x540].decode('utf-16-le').rstrip('\x00')
    except Exception:
        dtype = ""

    if not name and not dtype:
        print("  Warning: may not be a valid .scel file")

    print("  Name: {}".format(name))
    print("  Type: {}".format(dtype))

    # Pinyin table offset
    pinyin_offset = struct.unpack_from('<I', data, 0x6C)[0]
    # Still not sure about exact layout, use the proven algorithm

    results = []

    try:
        results = _parse_scel_v2(data)
    except Exception as e:
        print("  Error parsing: {}".format(e))
        return []

    return results


def _parse_scel_v2(data):
    """Parse .scel using the well-known algorithm.

    The .scel format:
    1. Pinyin table starts at offset stored at 0x6C
    2. Pinyin table: each entry is (pinyin_index, pinyin_string)
    3. After pinyin table: word entries grouped by pinyin combination
    """
    # Read pinyin table
    pinyin_start = struct.unpack_from('<I', data, 0x6C)[0]

    # Pinyin table structure:
    # First 4 bytes: number of pinyin entries
    # Then for each entry: 2 bytes (index) + 2 bytes (length) + pinyin_string (length bytes, UTF-16-LE)
    py_count = struct.unpack_from('<H', data, pinyin_start)[0]

    pinyin_table = {}
    pos = pinyin_start + 4  # skip count

    for _ in range(py_count):
        if pos + 4 > len(data):
            break
        idx = struct.unpack_from('<H', data, pos)[0]
        py_len = struct.unpack_from('<H', data, pos + 2)[0]
        pos += 4
        if pos + py_len * 2 > len(data):
            break
        py_str = data[pos:pos + py_len * 2].decode('utf-16-le')
        pos += py_len * 2
        pinyin_table[idx] = py_str

    # Word entries start after pinyin table
    # The format: groups of entries, each group has a pinyin list + words
    word_start = pos

    # Read word data section
    # Structure: repeated blocks of
    #   4 bytes: pinyin count for this block
    #   For each pinyin: 2 bytes (pinyin index into table)
    #   4 bytes: word count in this block
    #   For each word:
    #     2 bytes: word length (in characters)
    #     2 bytes: ??? (usually same as word length or 0)
    #     word string (word_length * 2 bytes, UTF-16-LE)
    #     2 bytes: extended info length
    #     extended info bytes (skip)

    results = []
    pos = word_start

    while pos < len(data) - 12:
        # Read pinyin indices for this group
        same_pinyin_count = struct.unpack_from('<I', data, pos)[0]
        pos += 4

        if same_pinyin_count == 0 or same_pinyin_count > 100:
            break

        # Read pinyin indices
        pinyin_indices = []
        for _ in range(same_pinyin_count):
            if pos + 2 > len(data):
                break
            py_idx = struct.unpack_from('<H', data, pos)[0]
            pos += 2
            pinyin_indices.append(py_idx)

        # Build pinyin string
        pinyin_parts = []
        for idx in pinyin_indices:
            if idx in pinyin_table:
                pinyin_parts.append(pinyin_table[idx])
            else:
                pinyin_parts.append("?")
        pinyin_str = " ".join(pinyin_parts)

        # Read word count
        if pos + 4 > len(data):
            break
        word_count = struct.unpack_from('<I', data, pos)[0]
        pos += 4

        if word_count > 1000:
            break

        # Read words
        for _ in range(word_count):
            if pos + 4 > len(data):
                break
            word_len = struct.unpack_from('<H', data, pos)[0]
            pos += 2
            # Skip 2 bytes (flags/length)
            pos += 2

            if pos + word_len * 2 > len(data):
                break
            word = data[pos:pos + word_len * 2].decode('utf-16-le')
            pos += word_len * 2

            # Extended info
            if pos + 2 > len(data):
                break
            ext_len = struct.unpack_from('<H', data, pos)[0]
            pos += 2
            pos += ext_len

            if word and pinyin_str:
                # Freq: Sogou doesn't store explicit freq, use a default
                # Words earlier in the list are more common
                freq = 100
                results.append((pinyin_str, word, freq))

    return results


def import_scel_file(scel_path, output_path):
    """Import a single .scel file and append to output dict file."""
    print("Parsing: {}".format(scel_path))
    entries = parse_scel(scel_path)

    if not entries:
        print("  No entries found, skipping.")
        return 0

    # Deduplicate: same (pinyin, word) → keep highest freq
    deduped = {}
    for py, word, freq in entries:
        key = (py, word)
        if key not in deduped or freq > deduped[key]:
            deduped[key] = freq

    # Sort by pinyin then freq desc
    sorted_entries = sorted(deduped.items(), key=lambda x: (-x[1], x[0][0]))
    count = len(sorted_entries)

    # Append to output file
    with open(output_path, 'a', encoding='utf-8') as f:
        f.write("\n# Imported from: {}\n".format(os.path.basename(scel_path)))
        for (py, word), freq in sorted_entries:
            f.write("{}\t{}\t{}\n".format(py, word, freq))

    print("  Imported {} entries -> {}".format(count, output_path))
    return count


def merge_into_base(sogou_path, base_path):
    """Merge sogou_imported.txt into base_dict.txt (dedup)."""
    # Read existing base dict
    existing = {}
    comments = []
    if os.path.isfile(base_path):
        with open(base_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                if line.startswith('#') or not line.strip():
                    comments.append(line)
                    continue
                parts = line.split('\t')
                if len(parts) >= 3:
                    key = (parts[0], parts[1])
                    try:
                        freq = int(parts[2])
                    except ValueError:
                        freq = 100
                    existing[key] = freq
                elif len(parts) == 2:
                    key = (parts[0], parts[1])
                    existing[key] = 100

    # Read sogou imported
    new_count = 0
    if os.path.isfile(sogou_path):
        with open(sogou_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.split('\t')
                if len(parts) >= 3:
                    key = (parts[0], parts[1])
                    try:
                        freq = int(parts[2])
                    except ValueError:
                        freq = 100
                    if key not in existing or freq > existing.get(key, 0):
                        existing[key] = freq
                        new_count += 1

    if new_count == 0:
        print("No new entries to merge.")
        return

    # Write merged base dict
    # Sort: by pinyin, then freq desc
    sorted_entries = sorted(existing.items(), key=lambda x: (x[0][0], -x[1]))

    with open(base_path, 'w', encoding='utf-8') as f:
        for line in comments:
            f.write(line + '\n')
        for (py, word), freq in sorted_entries:
            f.write('{}\t{}\t{}\n'.format(py, word, freq))

    print("Merged {} new entries into {} (total: {})".format(
        new_count, os.path.basename(base_path), len(existing)))


def main():
    if len(sys.argv) < 2:
        print("Sogou Dictionary Importer for AI IME")
        print("")
        print("Usage:")
        print("  python import_sogou_dict.py <scel_file>")
        print("  python import_sogou_dict.py <directory>")
        print("  python import_sogou_dict.py --merge")
        print("")
        print("Steps:")
        print("  1. Download .scel files from:")
        print("     https://pinyin.sogou.com/dict/")
        print("  2. Run: python import_sogou_dict.py <scel_file_or_dir>")
        print("  3. Run: python import_sogou_dict.py --merge")
        print("     (merges into base_dict.txt, reload input method to activate)")
        print("")
        sys.exit(0)

    arg = sys.argv[1]

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "ai_ime", "data")
    sogou_path = os.path.join(data_dir, "sogou_imported.txt")
    base_path = os.path.join(data_dir, "base_dict.txt")

    if arg == "--merge":
        print("Merging sogou_imported.txt into base_dict.txt...")
        merge_into_base(sogou_path, base_path)
        return

    # Collect .scel files
    scel_files = []
    if os.path.isfile(arg):
        scel_files.append(arg)
    elif os.path.isdir(arg):
        scel_files = sorted(glob.glob(os.path.join(arg, "*.scel")))
    else:
        print("Error: {} not found".format(arg))
        sys.exit(1)

    if not scel_files:
        print("No .scel files found.")
        sys.exit(1)

    print("Found {} .scel file(s)".format(len(scel_files)))
    print("Output: {}".format(sogou_path))
    print("")

    total = 0
    for scel in scel_files:
        count = import_scel_file(scel, sogou_path)
        total += count

    print("")
    print("Total: {} entries imported".format(total))
    print("")
    print("Next step: merge into base dictionary:")
    print("  python import_sogou_dict.py --merge")


if __name__ == '__main__':
    main()
