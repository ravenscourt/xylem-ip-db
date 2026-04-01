"""Fetch Chinese IP ranges from chnroutes2 (IPv4 only)."""

import ipaddress

from utils import fetch_text

CHNROUTES_URL = "https://raw.githubusercontent.com/misakaio/chnroutes2/master/chnroutes.txt"


def fetch():
    """Return (ipv4_list, None) for China from chnroutes2."""
    text = fetch_text(CHNROUTES_URL)

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
