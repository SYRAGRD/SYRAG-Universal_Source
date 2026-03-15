from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any

import requests


class AnchoringError(RuntimeError):
    pass


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def anchor_pinata(file_path: Path, cfg: Dict[str, Any], timeout_s: int = 120) -> str:
    p_cfg = cfg.get("anchoring", {}).get("providers", {}).get("pinata", {})
    env_name = p_cfg.get("jwt_env", "PINATA_JWT")
    jwt = os.getenv(env_name, "")
    if not jwt:
        raise AnchoringError(f"Missing Pinata JWT env var: {env_name}")

    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    headers = {"Authorization": f"Bearer {jwt}"}

    with file_path.open("rb") as fh:
        files = {"file": (file_path.name, fh)}
        r = requests.post(url, headers=headers, files=files, timeout=timeout_s)

    if r.status_code >= 400:
        raise AnchoringError(f"Pinata error {r.status_code}: {r.text[:400]}")

    data = r.json()
    ipfs_hash = data.get("IpfsHash", "")
    if not ipfs_hash:
        raise AnchoringError("Pinata response missing IpfsHash")
    return ipfs_hash


def stamp_with_ots(file_path: Path) -> Path:
    if shutil.which("ots") is None:
        raise AnchoringError("OTS CLI not found. Install opentimestamps-client (`ots`) and retry.")

    cmd = ["ots", "stamp", str(file_path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise AnchoringError(f"OTS stamp failed: {res.stderr.strip() or res.stdout.strip()}")

    ots_path = file_path.with_suffix(file_path.suffix + ".ots")
    if not ots_path.exists():
        raise AnchoringError("OTS stamp completed but .ots file not found")
    return ots_path
