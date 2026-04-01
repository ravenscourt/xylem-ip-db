#!/usr/bin/env python3
"""Orchestrator — fetch IP ranges per country, apply overrides, and write
plain-text lists, RouterOS scripts, and sing-box rule sets.
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from fetch_cn import fetch as fetch_cn
from fetch_ir import fetch as fetch_ir
from fetch_ru import fetch as fetch_ru
from utils import (
    apply_overrides,
    build_routeros_lines,
    build_singbox_ruleset,
    compact_ranges,
    content_hash,
    parse_cidr_text,
)

ROOT = Path(__file__).resolve().parent.parent
OVERRIDES_DIR = ROOT / "overrides"
LISTS_DIR = ROOT / "lists"
ROUTEROS_DIR = ROOT / "routeros"
SINGBOX_DIR = ROOT / "sing-box"

COUNTRIES = [
    {"code": "ir", "name": "Iran", "list_v4": "IRv4", "list_v6": "IRv6", "fetch": fetch_ir},
    {"code": "ru", "name": "Russia", "list_v4": "RUv4", "fetch": fetch_ru},
    {"code": "cn", "name": "China", "list_v4": "CNv4", "fetch": fetch_cn},
]


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------


def read_file_hash(path):
    """Read the sha256 hash from an existing file's header, or None."""
    if not path.exists():
        return None
    with open(path) as f:
        for line in f:
            m = re.match(r"^# Hash: sha256:([0-9a-f]+)", line)
            if m:
                return m.group(1)
            if not line.startswith("#"):
                break
    return None


def write_if_changed(path, country_label, ip_type, lines):
    """Write file only when the content hash differs from the existing one.
    Returns True if the file was written.
    """
    new_hash = content_hash(lines)
    if new_hash == read_file_hash(path):
        return False

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = (
        f"# Country: {country_label}\n"
        f"# Type: {ip_type}\n"
        f"# Last updated: {now}\n"
        f"# Hash: sha256:{new_hash}\n"
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(header)
        f.write("\n")
        body = "\n".join(lines)
        if body:
            f.write(body + "\n")

    return True


def write_text_if_changed(path, content):
    """Write file only if content differs from existing."""
    if path.exists() and path.read_text() == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return True


def load_overrides(country_code):
    """Load addition and exemption overrides for a country.
    Returns two lists of (network, reason_or_None) tuples.
    """
    additions_path = OVERRIDES_DIR / f"{country_code}.additions.txt"
    exemptions_path = OVERRIDES_DIR / f"{country_code}.exemptions.txt"

    additions = parse_cidr_text(additions_path.read_text()) if additions_path.exists() else []
    exemptions = parse_cidr_text(exemptions_path.read_text()) if exemptions_path.exists() else []
    return additions, exemptions


# ---------------------------------------------------------------------------
# Per-country processing
# ---------------------------------------------------------------------------


def process_country(entry):
    """Fetch data, apply overrides, and write all output files for one country.
    Returns the number of files that were updated.
    """
    code = entry["code"]
    name = entry["name"]
    label = f"{name} ({code.upper()})"
    list_v4 = entry.get("list_v4")
    list_v6 = entry.get("list_v6")

    print(f"Processing {label}...")

    try:
        ipv4_ranges, ipv6_ranges = entry["fetch"]()
    except Exception as exc:
        print(f"  Error fetching data: {exc}", file=sys.stderr)
        return 0

    ipv4_ranges = compact_ranges(ipv4_ranges)
    if ipv6_ranges is not None:
        ipv6_ranges = compact_ranges(ipv6_ranges)

    additions, exemptions = load_overrides(code)

    v4_add = [(n, r) for n, r in additions if n.version == 4]
    v4_exc = [(n, r) for n, r in exemptions if n.version == 4]
    v4_lines = apply_overrides(ipv4_ranges, v4_add, v4_exc)

    v6_lines = None
    if ipv6_ranges is not None and list_v6:
        v6_add = [(n, r) for n, r in additions if n.version == 6]
        v6_exc = [(n, r) for n, r in exemptions if n.version == 6]
        v6_lines = apply_overrides(ipv6_ranges, v6_add, v6_exc)

    updates = 0

    if write_if_changed(LISTS_DIR / f"{code}.ipv4.txt", label, "IPv4", v4_lines):
        print(f"  Updated lists/{code}.ipv4.txt")
        updates += 1

    if v6_lines is not None:
        if write_if_changed(LISTS_DIR / f"{code}.ipv6.txt", label, "IPv6", v6_lines):
            print(f"  Updated lists/{code}.ipv6.txt")
            updates += 1

    if list_v4:
        v4_rsc = build_routeros_lines(v4_lines, list_v4, 4)
        if write_if_changed(ROUTEROS_DIR / f"{code}.ipv4.rsc", label, "IPv4", v4_rsc):
            print(f"  Updated routeros/{code}.ipv4.rsc")
            updates += 1

    if list_v6 and v6_lines is not None:
        v6_rsc = build_routeros_lines(v6_lines, list_v6, 6)
        if write_if_changed(ROUTEROS_DIR / f"{code}.ipv6.rsc", label, "IPv6", v6_rsc):
            print(f"  Updated routeros/{code}.ipv6.rsc")
            updates += 1

    v4_sb = build_singbox_ruleset(v4_lines)
    if write_text_if_changed(SINGBOX_DIR / f"{code}.ipv4.json", v4_sb):
        print(f"  Updated sing-box/{code}.ipv4.json")
        updates += 1

    if v6_lines is not None:
        v6_sb = build_singbox_ruleset(v6_lines)
        if write_text_if_changed(SINGBOX_DIR / f"{code}.ipv6.json", v6_sb):
            print(f"  Updated sing-box/{code}.ipv6.json")
            updates += 1

    if updates == 0:
        print("  No changes")

    return updates


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    total = 0
    for entry in COUNTRIES:
        total += process_country(entry)
    print(f"\nDone. {total} file(s) updated.")


if __name__ == "__main__":
    main()
