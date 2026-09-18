"""Shared utilities for IP list generation.

Data-transformation functions (pure, no side effects) and HTTP fetch helpers
with retry/backoff.
"""

import hashlib
import ipaddress
import json
import re
import sys
import time
import urllib.request

# ---------------------------------------------------------------------------
# HTTP fetch with retry / backoff
# ---------------------------------------------------------------------------


def fetch_url(url, retries=3, backoff_base=1.0, timeout=120, headers=None):
    """Fetch a URL with retry and exponential backoff.
    Returns the response body as bytes.
    Retries up to ``retries`` times on failure, sleeping
    backoff_base * 2^attempt seconds between attempts.
    ``headers`` are merged over the default ``{"Connection": "close"}``.
    """
    merged_headers = {"Connection": "close"}
    if headers:
        merged_headers.update(headers)
    last_exc = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=merged_headers)
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
# DNS-over-HTTPS resolution
# ---------------------------------------------------------------------------

DOH_ENDPOINTS = [
    ("https://cloudflare-dns.com/dns-query", {"accept": "application/dns-json"}),
    ("https://dns.google/resolve", {}),
]
RECORD_TYPES = (("A", 1), ("AAAA", 28))


def _resolve_record(domain, record_name, record_code, retries, backoff_base, timeout):
    """Resolve a single record type across the DoH endpoints in order.
    Returns a list of ip strings, or None if every endpoint failed to answer.
    """
    for base_url, headers in DOH_ENDPOINTS:
        url = f"{base_url}?name={domain}&type={record_name}"
        try:
            data = fetch_json(
                url,
                retries=retries,
                backoff_base=backoff_base,
                timeout=timeout,
                headers=headers,
            )
        except Exception:
            continue

        status = data.get("Status")
        if status == 3:  # NXDOMAIN: authoritative empty answer.
            return []
        if status != 0:
            continue

        return [
            answer["data"]
            for answer in data.get("Answer", [])
            if answer.get("type") == record_code and answer.get("data")
        ]
    return None


def resolve_domain(domain, retries=1, backoff_base=1.0, timeout=15):
    """Resolve a domain to /32 and /128 networks over DoH.

    Queries A and AAAA records, walking ``DOH_ENDPOINTS`` in order for each and
    falling back to the next endpoint when one fails to answer.  Returns a tuple
    ``(networks, failed_record_types)`` where ``failed_record_types`` lists the
    record names for which no endpoint produced an answer.
    """
    networks = []
    failed = []
    for record_name, record_code in RECORD_TYPES:
        addresses = _resolve_record(
            domain, record_name, record_code, retries, backoff_base, timeout
        )
        if addresses is None:
            failed.append(record_name)
            continue
        for addr in addresses:
            try:
                networks.append(ipaddress.ip_network(addr, strict=False))
            except ValueError:
                pass
    return networks, failed


# ---------------------------------------------------------------------------
# CIDR parsing and transformation
# ---------------------------------------------------------------------------


_HOSTNAME_LABEL = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")


def _is_hostname(value):
    """Return True if ``value`` looks like a resolvable domain name."""
    if len(value) > 253 or "." not in value:
        return False
    return all(_HOSTNAME_LABEL.match(label) for label in value.split("."))


def parse_override_text(text):
    """Parse an override file into CIDR entries and domain entries.

    Captures the comment above each entry as its reason/label; a blank line
    resets the current reason.  Returns two lists of ``(value, reason_or_None)``
    tuples: the first holds ``ip_network`` objects, the second holds hostname
    strings.  Lines that are neither a valid CIDR nor a hostname are skipped.
    """
    cidr_entries = []
    domain_entries = []
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
            cidr_entries.append((net, current_reason))
            continue
        except ValueError:
            pass
        if _is_hostname(line):
            domain_entries.append((line, current_reason))
    return cidr_entries, domain_entries


def parse_cidr_text(text):
    """Parse CIDR ranges from text content, capturing the comment above each
    range as its reason/label.  A blank line resets the current reason.
    Returns a list of (network, reason_or_None) tuples.
    """
    cidr_entries, _ = parse_override_text(text)
    return cidr_entries


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
