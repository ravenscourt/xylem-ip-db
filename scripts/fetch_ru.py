"""Fetch Russian IP ranges from antifilter (IPv4 only)."""

import ipaddress

from utils import fetch_text

ANTIFILTER_URL = "https://antifilter.download/list/allyouneed.lst"


def fetch():
    """Return (ipv4_list, None) for Russia from antifilter.download."""
    text = fetch_text(ANTIFILTER_URL)

    ipv4 = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            ipv4.append(ipaddress.ip_network(line, strict=False))
        except ValueError:
            pass
    return ipv4, None
