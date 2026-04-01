"""Fetch Iranian IP ranges via RIPE NCC ASN-based prefix resolution (IPv4 + IPv6).

1. Fetch routed ASNs for IR from country-asns endpoint.
2. For each ASN, fetch announced prefixes with timeline filtering.
3. Keep only prefixes whose announcement covers the current time.
4. Return deduplicated IPv4/IPv6 lists.
"""

import ipaddress
import re
import sys
import time
from datetime import datetime, timedelta, timezone

from utils import fetch_json

COUNTRY_ASNS_URL = "https://stat.ripe.net/data/country-asns/data.json?resource=IR&lod=1"
ANNOUNCED_PREFIXES_URL = "https://stat.ripe.net/data/announced-prefixes/data.json?resource=AS{asn}"
INTER_REQUEST_DELAY = 0.1


def _parse_routed_asns(routed_str):
    """Extract ASN numbers from the routed string like '{AsnSingle(12345), ...}'."""
    return [int(m) for m in re.findall(r"AsnSingle\((\d+)\)", routed_str)]


def _is_active(timelines, now):
    """Return True if any timeline interval overlaps the current week.
    RIPE's endtime is the last observation boundary, so a strict
    timestamp comparison misses actively announced prefixes.
    """
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    week_end = week_start + timedelta(days=7)
    for tl in timelines:
        start = datetime.fromisoformat(tl["starttime"]).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(tl["endtime"]).replace(tzinfo=timezone.utc)
        if start < week_end and end >= week_start:
            return True
    return False


def _fetch_prefixes_for_asn(asn, now):
    """Fetch announced prefixes for a single ASN, returning active networks."""
    url = ANNOUNCED_PREFIXES_URL.format(asn=asn)
    data = fetch_json(url)
    active = []
    for entry in data.get("data", {}).get("prefixes", []):
        if _is_active(entry.get("timelines", []), now):
            try:
                active.append(ipaddress.ip_network(entry["prefix"], strict=False))
            except ValueError:
                pass
    return active


def _print_progress(done, total, asn, status, bar_len, is_tty):
    if is_tty:
        filled = int(bar_len * done / total)
        bar = "█" * filled + "░" * (bar_len - filled)
        line1 = f"\033[A\r\033[K  [{bar}] {done}/{total} ASNs"
        line2 = f"\n\033[K  AS{asn}: {status}"
        print(line1 + line2, end="", flush=True)
    elif done % 50 == 0 or done == total:
        print(f"  {done}/{total} ASNs fetched...")


def fetch():
    """Return (ipv4_list, ipv6_list) for Iran via ASN-based prefix resolution."""
    data = fetch_json(COUNTRY_ASNS_URL)
    routed_str = data["data"]["countries"][0].get("routed", "")
    asns = _parse_routed_asns(routed_str)

    if not asns:
        return [], []

    now = datetime.now(timezone.utc)
    all_networks = []
    total = len(asns)
    is_tty = sys.stdout.isatty()
    bar_len = 30

    print(f"  Fetching prefixes for {total} Iranian ASNs...")
    if is_tty:
        print(f"  [{'░' * bar_len}] 0/{total} ASNs\n", end="", flush=True)

    for i, asn in enumerate(asns, 1):
        try:
            prefixes = _fetch_prefixes_for_asn(asn, now)
            all_networks.extend(prefixes)
            _print_progress(i, total, asn, f"{len(prefixes)} prefixes", bar_len, is_tty)
        except Exception as exc:
            _print_progress(i, total, asn, "failed", bar_len, is_tty)
            print(f"  Warning: AS{asn} failed: {exc}", file=sys.stderr)
        if i < total:
            time.sleep(INTER_REQUEST_DELAY)

    if is_tty:
        print()

    ipv4 = [n for n in all_networks if n.version == 4]
    ipv6 = [n for n in all_networks if n.version == 6]

    print(f"  Collected {len(ipv4)} IPv4 and {len(ipv6)} IPv6 prefixes")
    return ipv4, ipv6
