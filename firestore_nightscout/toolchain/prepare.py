#!/usr/bin/env python3
"""Download the pieces the TC002 demo build needs.

The compiler archive is https://download.flythings.cn/toolchain/ssd.tar.gz
(arm-linux-gnueabihf GCC 8.2.1, an x86-64 Linux program). The demo's libraries
and headers are the Z21 packages named in Z21_TC002_Demo/.deps.lock, from
https://package.flythings.cn. Nothing here is committed. build.sh compiles.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
TOOLCHAIN_TAR = CACHE / "ssd.tar.gz"
TOOLCHAIN_GCC = CACHE / "ssd" / "toolchain" / "bin" / "arm-linux-gnueabihf-g++"
DEMO_DIR = CACHE / "demo"
DEMO_LOCK = DEMO_DIR / "Z21_TC002_Demo" / ".deps.lock"
PACKAGES = CACHE / "packages"
TOOLCHAIN_URL = "https://download.flythings.cn/toolchain/ssd.tar.gz"
DEMO_URL = "https://github.com/UlanziTechnology/Ulanzi-U-Clock-TC002.git"
PACKAGE_API = "https://package.flythings.cn/api/platforms/z21/packages"


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    ensure_toolchain()
    ensure_demo()
    ensure_packages()
    print(f"Toolchain {TOOLCHAIN_GCC}")
    print(f"Demo {DEMO_DIR / 'Z21_TC002_Demo'}")
    print(f"Packages {PACKAGES}")


def ensure_toolchain() -> None:
    if TOOLCHAIN_GCC.is_file():
        print("Toolchain already extracted")
        return
    if not TOOLCHAIN_TAR.is_file():
        print(f"Downloading {TOOLCHAIN_URL}")
        download(TOOLCHAIN_URL, TOOLCHAIN_TAR)
    print(f"Extracting {TOOLCHAIN_TAR.name}")
    with tarfile.open(TOOLCHAIN_TAR) as archive:
        archive.extractall(CACHE / "ssd")
    if not TOOLCHAIN_GCC.is_file():
        raise SystemExit(f"Expected compiler at {TOOLCHAIN_GCC}")


def ensure_demo() -> None:
    if DEMO_LOCK.is_file():
        print("Demo already cloned")
        return
    if DEMO_DIR.exists():
        shutil.rmtree(DEMO_DIR)
    print(f"Cloning {DEMO_URL}")
    subprocess.run(
        ["git", "clone", "--depth", "1", DEMO_URL, str(DEMO_DIR)],
        check=True,
    )


def ensure_packages() -> None:
    text = "\n".join(
        line for line in DEMO_LOCK.read_text(errors="replace").splitlines() if not line.strip().startswith("//")
    )
    wanted: set[tuple[str, str]] = set()
    collect(json.loads(text), wanted)
    PACKAGES.mkdir(parents=True, exist_ok=True)
    for name, revision in sorted(wanted):
        dest = PACKAGES / f"{name}-{revision}"
        if package_root(dest) is not None:
            print(f"Package {name} {revision} already extracted")
            continue
        archive_path = PACKAGES / f"{name}-{revision}.zip"
        url = f"{PACKAGE_API}/{name}/versions/{revision}/archive"
        if not archive_path.is_file():
            print(f"Downloading {name} {revision}")
            download(url, archive_path)
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(dest)
        if package_root(dest) is None:
            raise SystemExit(f"{archive_path.name} has no include/ or lib/ directory")
        print(f"Extracted {name} {revision}")


def collect(node, wanted: set[tuple[str, str]]) -> None:
    if isinstance(node, dict):
        if "id" in node and "revision" in node:
            wanted.add((str(node["id"]), str(node["revision"])))
        for value in node.values():
            collect(value, wanted)
    elif isinstance(node, list):
        for item in node:
            collect(item, wanted)


def package_root(dest: Path) -> Path | None:
    """Directory that directly contains include/ or lib/."""
    if not dest.is_dir():
        return None
    if (dest / "include").is_dir() or (dest / "lib").is_dir():
        return dest
    children = [path for path in dest.iterdir() if path.is_dir()]
    if len(children) == 1 and ((children[0] / "include").is_dir() or (children[0] / "lib").is_dir()):
        return children[0]
    return None


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dest)


if __name__ == "__main__":
    main()
