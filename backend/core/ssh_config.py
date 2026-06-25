"""Parse the user's ~/.ssh/config so the UI can offer saved-host aliases and the
connectors can resolve them (HostName/User/Port/IdentityFile/ProxyJump).

The engine mounts ~/.ssh read-only, so the user's existing SSH setup is reused —
"if `ssh <alias>` works in your terminal, the app can use the same alias."
"""
import os
import re
from typing import List, Dict, Optional

import paramiko


def _config_path() -> str:
    return os.path.expanduser(os.getenv("NIR_SSH_CONFIG", "~/.ssh/config"))


def list_ssh_hosts() -> List[Dict]:
    """Return concrete (non-wildcard) Host aliases with resolved host/user/port."""
    path = _config_path()
    if not os.path.isfile(path):
        return []

    aliases: List[str] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                m = re.match(r"(?i)host\s+(.+)", s)
                if not m:
                    continue
                for tok in m.group(1).split():
                    if any(c in tok for c in "*?!"):
                        continue  # skip patterns
                    aliases.append(tok)
    except Exception:
        return []

    # de-dup, preserve order
    seen = set()
    uniq = [a for a in aliases if not (a in seen or seen.add(a))]

    cfg = paramiko.SSHConfig()
    try:
        with open(path, encoding="utf-8") as fh:
            cfg.parse(fh)
    except Exception:
        return []

    out: List[Dict] = []
    for a in uniq:
        r = cfg.lookup(a)
        out.append({
            "alias": a,
            "hostname": r.get("hostname", a),
            "user": r.get("user", ""),
            "port": int(r.get("port", 22) or 22),
            "proxyjump": r.get("proxyjump", ""),
        })
    return out


def resolve_alias(alias: str) -> Optional[Dict]:
    """Resolve one alias to connection params (None if no config)."""
    path = _config_path()
    if not os.path.isfile(path):
        return None
    cfg = paramiko.SSHConfig()
    try:
        with open(path, encoding="utf-8") as fh:
            cfg.parse(fh)
    except Exception:
        return None
    r = cfg.lookup(alias)
    idf = r.get("identityfile")
    return {
        "hostname": r.get("hostname", alias),
        "user": r.get("user"),
        "port": int(r.get("port", 22) or 22),
        "identityfile": (idf[0] if isinstance(idf, list) and idf else idf) or None,
        "proxyjump": r.get("proxyjump"),
    }
