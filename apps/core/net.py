"""Network helpers: CIDR allowlists for client IPs."""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable


def ip_in_cidrs(ip: str | None, cidrs: Iterable[str]) -> bool:
    """Return True when ``ip`` belongs to any network in ``cidrs``; malformed input never matches."""
    if not ip:
        return False
    try:
        address = ipaddress.ip_address(ip.strip())
    except ValueError:
        return False
    for cidr in cidrs:
        cidr = cidr.strip()
        if not cidr:
            continue
        try:
            if address in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False
