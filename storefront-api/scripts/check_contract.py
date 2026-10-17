"""Freshness gate: is the pinned contract the version the provider publishes now?

The provider's published contract location is given by INVENTORY_CONTRACT (a path or
file:// URL in this example; in a real pipeline, the provider's contract registry).
Exit 0 if the major versions match, 1 if they differ. If freshness can't be checked
(nothing pinned, contract unreachable, no info.version) it says UNVERIFIED and exits 1,
or 0 when ALLOW_UNVERIFIED is set.
"""
import os
import pathlib
import sys
import urllib.parse

import yaml

root = pathlib.Path(__file__).resolve().parent.parent
where = os.environ.get("INVENTORY_CONTRACT", str(root.parent / "inventory-service" / "contracts" / "inventory.openapi.yaml"))
published = pathlib.Path(urllib.parse.unquote(urllib.parse.urlparse(where).path) if where.startswith("file://") else where)


def unverified(why):
    print(f"UNVERIFIED: {why}; freshness not checked")
    sys.exit(0 if os.environ.get("ALLOW_UNVERIFIED") else 1)


pinned = (root / "contracts" / "PINNED").read_text().split()
if len(pinned) != 2:
    unverified("no contract version pinned in contracts/PINNED")
pinned_name, pinned_version = pinned
if not published.is_file():
    unverified(f"provider contract not reachable at {published}")
try:
    live = str(yaml.safe_load(published.read_text())["info"]["version"])
except (yaml.YAMLError, KeyError, TypeError):
    unverified(f"no info.version in {published}")
if live.split(".")[0] != pinned_version.split(".")[0]:
    print(f"STALE: pinned {pinned_name} {pinned_version}, provider publishes {live} (major change)")
    sys.exit(1)
print(f"ok: pinned {pinned_version}, provider publishes {live}")
