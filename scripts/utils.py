"""Shared utilities for IP list generation.

Data-transformation functions (pure, no side effects) and HTTP fetch helpers
with retry/backoff.
"""

import hashlib
import ipaddress
import json
import sys
import time
import urllib.request

# ---------------------------------------------------------------------------
# HTTP fetch with retry / backoff
# ---------------------------------------------------------------------------


def fetch_url(url, retries=3, backoff_base=1.0, timeout=120):
    """Fetch a URL with retry and exponential backoff.
    Returns the response body as bytes.
    Retries up to ``retries`` times on failure, sleeping
    backoff_base * 2^attempt seconds between attempts.
    """
    last_exc = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"Connection": "close"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                delay = backoff_base * (2**attempt)
                print(
                    f"  Retry {attempt + 1}/{retries} for {url} (waiting {delay:.1f}s): {exc}",
                    file=sys.stderr,
                )
                time.sleep(delay)
    raise last_exc


def fetch_json(url, **kwargs):
    """Fetch a URL and parse the response as JSON."""
    return json.loads(fetch_url(url, **kwargs).decode())


def fetch_text(url, **kwargs):
    """Fetch a URL and return the response as a string."""
    return fetch_url(url, **kwargs).decode()


# ---------------------------------------------------------------------------
# CIDR parsing and transformation
# ---------------------------------------------------------------------------


def parse_cidr_text(text):
    """Parse CIDR ranges from text content, capturing the comment above each
    range as its reason/label.  A blank line resets the current reason.
    Returns a list of (network, reason_or_None) tuples.
    """
    entries = []
    current_reason = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            current_reason = None
            continue
        if line.startswith("#"):
            current_reason = line.lstrip("#").strip() or None
            continue
        try:
            net = ipaddress.ip_network(line, strict=False)
            entries.append((net, current_reason))
        except ValueError:
            pass
    return entries


def compact_ranges(networks):
    """Collapse adjacent and overlapping CIDR ranges into the smallest set."""
    return list(ipaddress.collapse_addresses(sorted(networks)))


def apply_overrides(networks, additions, exemptions):
    """Merge additions into the network list, then split ranges to exclude
    exemptions.  Returns a list of output lines (CIDR strings and comment
    annotations for additions and exemption splits).

    When multiple exemptions carve into the same original range, their
    comments are merged and the resulting fragments are grouped.
    """
    addition_nets = [n for n, _ in additions]
    addition_reasons = {n: r for n, r in additions if r}

    merged = list(ipaddress.collapse_addresses(sorted(networks + addition_nets)))
    addition_set = set(addition_nets)

    origin_map = {net: net for net in merged}
    exemptions_by_origin = {}

    for exemption, _ in exemptions:
        updated = []
        for net in merged:
            if not net.overlaps(exemption):
                updated.append(net)
                continue

            origin = origin_map.get(net, net)

            if net.subnet_of(exemption):
                if origin in exemptions_by_origin:
                    if exemption not in exemptions_by_origin[origin]:
                        exemptions_by_origin[origin].append(exemption)
                origin_map.pop(net, None)
                continue

            exemptions_by_origin.setdefault(origin, [])
            if exemption not in exemptions_by_origin[origin]:
                exemptions_by_origin[origin].append(exemption)

            for fragment in net.address_exclude(exemption):
                origin_map[fragment] = origin
                updated.append(fragment)

            origin_map.pop(net, None)

        merged = sorted(updated)

    parts_count = {}
    for net in merged:
        origin = origin_map.get(net)
        if origin is not None and origin in exemptions_by_origin:
            parts_count[origin] = parts_count.get(origin, 0) + 1

    lines = []
    fragment_index = {}

    for net in merged:
        origin = origin_map.get(net)

        if origin is not None and origin in exemptions_by_origin:
            fragment_index[origin] = fragment_index.get(origin, 0) + 1
            idx = fragment_index[origin]
            total = parts_count.get(origin, 0)

            reason = addition_reasons.get(origin)
            excluded = ", ".join(str(e) for e in exemptions_by_origin[origin])

            if reason:
                ann = f"# {reason} - {excluded} excluded from {origin}"
            else:
                ann = f"# {excluded} excluded from {origin}"
            ann += f" - fragment {idx}/{total}"

            lines.append(ann)
            lines.append(str(net))
            continue

        if net in addition_set:
            reason = addition_reasons.get(net)
            if reason:
                lines.append(f"# {reason}")

        lines.append(str(net))

    return lines


def build_routeros_lines(range_lines, list_name, ip_version):
    """Convert plain-text range lines into RouterOS address-list commands.
    Comment lines (``# ...``) preceding addresses are used as the
    ``comment=`` attribute on the generated ``add`` commands.
    """
    prefix = "/ip" if ip_version == 4 else "/ipv6"
    output = [
        f"{prefix} firewall address-list remove "
        f"[{prefix} firewall address-list find list={list_name}]",
        f"{prefix} firewall address-list",
    ]
    current_comment = None
    for line in range_lines:
        if not line:
            current_comment = None
        elif line.startswith("#"):
            current_comment = line.lstrip("#").strip() or None
        else:
            if current_comment:
                output.append(
                    f":do {{ add address={line} list={list_name}"
                    f' comment="{current_comment}"}} on-error={{}}'
                )
                current_comment = None
            else:
                output.append(f":do {{ add address={line} list={list_name}}} on-error={{}}")
    return output


def build_singbox_ruleset(range_lines):
    """Build a sing-box rule set JSON from range lines."""
    cidrs = [x for x in range_lines if x and not x.startswith("#")]
    return (
        json.dumps(
            {"version": 2, "rules": [{"ip_cidr": cidrs}]},
            indent=2,
        )
        + "\n"
    )


def content_hash(lines):
    """SHA-256 of non-comment, non-empty lines (the actual ranges)."""
    payload = "\n".join(x for x in lines if x and not x.startswith("#"))
    return hashlib.sha256(payload.encode()).hexdigest()
