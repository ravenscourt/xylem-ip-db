#!/usr/bin/env python3
"""Validate addition/exemption requests submitted as GitHub issues.

Reads the issue payload from GITHUB_EVENT_PATH, checks the requested
IP range against the current generated lists, and prints a comment body
to stdout.  The calling workflow posts that comment on the issue.
"""

import ipaddress
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LISTS_DIR = ROOT / "lists"


def discover_countries():
    """Return the set of country codes that have generated list files."""
    codes = set()
    if not LISTS_DIR.exists():
        return codes
    for f in LISTS_DIR.iterdir():
        m = re.match(r"^([a-z]{2})\.ipv[46]\.txt$", f.name)
        if m:
            codes.add(m.group(1))
    return codes


def parse_issue_body(body):
    """Parse '### Field' sections produced by GitHub issue form templates."""
    fields = {}
    current_key = None
    current_lines = []

    for line in body.splitlines():
        header = re.match(r"^###\s+(.+)", line)
        if header:
            if current_key is not None:
                fields[current_key] = "\n".join(current_lines).strip()
            current_key = header.group(1).strip().lower()
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)

    if current_key is not None:
        fields[current_key] = "\n".join(current_lines).strip()

    return fields


def load_ranges(path):
    """Load CIDR networks from a generated list file."""
    networks = []
    if not path.exists():
        return networks
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                networks.append(ipaddress.ip_network(line, strict=False))
            except ValueError:
                continue
    return networks


def validate_addition(requested, existing):
    """Return a diagnostic string if the range is already covered, else None."""
    for net in existing:
        if requested.subnet_of(net):
            return f"The range `{requested}` is already included (covered by `{net}`)."
        if requested.overlaps(net):
            return (
                f"The range `{requested}` partially overlaps with `{net}`. "
                f"Please verify and narrow down the request."
            )
    return None


def validate_exemption(requested, existing):
    """Return a diagnostic string if the range is already absent, else None."""
    if not any(requested.overlaps(net) for net in existing):
        return (
            f"The range `{requested}` is not present in the current list. No exemption is needed."
        )
    return None


def main():
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("GITHUB_EVENT_PATH not set", file=sys.stderr)
        sys.exit(1)

    with open(event_path) as f:
        event = json.load(f)

    issue = event.get("issue", {})
    body = issue.get("body", "") or ""
    labels = {lb["name"].lower() for lb in issue.get("labels", [])}

    is_addition = "addition" in labels
    is_exemption = "exemption" in labels
    if not is_addition and not is_exemption:
        sys.exit(0)

    fields = parse_issue_body(body)

    country_raw = fields.get("country", "")
    country_match = re.match(r"^([A-Za-z]{2})", country_raw)
    country = country_match.group(1).lower() if country_match else ""

    ip_range = fields.get("ip or cidr range", "").strip()

    if not country or not ip_range:
        print(
            "**Automated check:** Could not parse the issue fields. "
            "Please use the issue template and fill in all required fields."
        )
        sys.exit(0)

    known_countries = discover_countries()
    if country not in known_countries:
        valid = ", ".join(f"`{c}`" for c in sorted(known_countries))
        print(
            f"**Automated check:** Unknown country code `{country}`. Supported countries: {valid}."
        )
        sys.exit(0)

    try:
        requested = ipaddress.ip_network(ip_range, strict=False)
    except ValueError:
        print(f"**Automated check:** `{ip_range}` is not a valid IP address or CIDR range.")
        sys.exit(0)

    version = "ipv4" if requested.version == 4 else "ipv6"
    existing = load_ranges(LISTS_DIR / f"{country}.{version}.txt")

    if is_addition:
        problem = validate_addition(requested, existing)
        ok_msg = "This range is not yet in the list. The request looks valid."
    else:
        problem = validate_exemption(requested, existing)
        ok_msg = "This range is present in the list. The exemption request looks valid."

    if problem:
        print(f"**Automated check:** {problem}")
    else:
        print(f"**Automated check:** {ok_msg}")


if __name__ == "__main__":
    main()
