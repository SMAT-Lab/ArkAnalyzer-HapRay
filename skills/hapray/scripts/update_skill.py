#!/usr/bin/env python3
"""Safely update an installed HapRay Skill from AtomGit tags."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_API_BASE = "https://api.atomgit.com/api/v5"
DEFAULT_REPOSITORY = "SMAT/ArkAnalyzer-HapRay"
SKILL_REPOSITORY_PATH = "skills/hapray"
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
MAX_FILES = 512
MAX_TOTAL_BYTES = 8 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 20


class UpdateError(RuntimeError):
    """Raised when an update cannot be downloaded or installed safely."""


def parse_version(value: str) -> Tuple[int, int, int]:
    match = VERSION_RE.fullmatch(value.strip())
    if not match:
        raise UpdateError(f"Unsupported version: {value!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def read_skill_metadata(skill_file: Path) -> Dict[str, str]:
    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError as error:
        raise UpdateError(f"Cannot read {skill_file}: {error}") from error

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise UpdateError(f"Missing YAML frontmatter in {skill_file}")

    metadata: Dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("\"'")

    if metadata.get("name") != "hapray":
        raise UpdateError(f"Unexpected Skill name in {skill_file}")
    if "version" not in metadata:
        raise UpdateError(f"Missing Skill version in {skill_file}")
    parse_version(metadata["version"])
    return metadata


class AtomGitClient:
    def __init__(
        self, api_base: str, repository: str, timeout: int = REQUEST_TIMEOUT_SECONDS
    ):
        self.api_base = api_base.rstrip("/")
        self.repository = repository.strip("/")
        self.timeout = timeout

    def _url(self, endpoint: str, query: Optional[Dict[str, str]] = None) -> str:
        repository = "/".join(
            urllib.parse.quote(part, safe="") for part in self.repository.split("/")
        )
        url = f"{self.api_base}/repos/{repository}/{endpoint.lstrip('/')}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        return url

    def get_json(self, endpoint: str, query: Optional[Dict[str, str]] = None) -> Any:
        request = urllib.request.Request(
            self._url(endpoint, query),
            headers={
                "Accept": "application/json",
                "User-Agent": "hapray-skill-updater",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise UpdateError(f"AtomGit request failed: {error}") from error

    def latest_stable_tag(self) -> Tuple[str, Tuple[int, int, int]]:
        payload = self.get_json("tags", {"per_page": "100"})
        if not isinstance(payload, list):
            raise UpdateError("AtomGit tags response is not a list")

        candidates: List[Tuple[Tuple[int, int, int], str]] = []
        for item in payload:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            try:
                version = parse_version(item["name"])
            except UpdateError:
                continue
            candidates.append((version, item["name"]))

        if not candidates:
            raise UpdateError("No stable semantic-version tag found")
        version, tag = max(candidates)
        return tag, version

    def list_contents(self, path: str, ref: str) -> List[Dict[str, Any]]:
        encoded_path = "/".join(
            urllib.parse.quote(part, safe="") for part in path.split("/")
        )
        payload = self.get_json(f"contents/{encoded_path}", {"ref": ref})
        if not isinstance(payload, list):
            raise UpdateError(f"Expected a directory at {path}")
        return payload

    def read_file(self, path: str, ref: str) -> Tuple[bytes, str]:
        encoded_path = "/".join(
            urllib.parse.quote(part, safe="") for part in path.split("/")
        )
        payload = self.get_json(f"contents/{encoded_path}", {"ref": ref})
        if not isinstance(payload, dict) or payload.get("type") != "file":
            raise UpdateError(f"Expected a file at {path}")
        if payload.get("encoding") != "base64" or not isinstance(
            payload.get("content"), str
        ):
            raise UpdateError(f"Unsupported file encoding at {path}")
        try:
            data = base64.b64decode(payload["content"], validate=True)
        except (ValueError, TypeError) as error:
            raise UpdateError(f"Invalid base64 content at {path}") from error
        sha = payload.get("sha")
        if not isinstance(sha, str):
            raise UpdateError(f"Missing blob SHA at {path}")
        return data, sha


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _safe_relative_path(repository_path: str) -> Path:
    prefix = f"{SKILL_REPOSITORY_PATH}/"
    if not repository_path.startswith(prefix):
        raise UpdateError(f"Path escaped Skill root: {repository_path}")
    relative = Path(repository_path[len(prefix) :])
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise UpdateError(f"Unsafe repository path: {repository_path}")
    return relative


def _walk_remote_files(
    client: AtomGitClient, path: str, ref: str
) -> Iterable[Dict[str, Any]]:
    for entry in client.list_contents(path, ref):
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise UpdateError(f"Malformed contents entry under {path}")
        entry_type = entry.get("type")
        if entry_type == "dir":
            yield from _walk_remote_files(client, entry["path"], ref)
        elif entry_type == "file":
            yield entry
        else:
            raise UpdateError(
                f"Unsupported entry type {entry_type!r} at {entry['path']}"
            )


def download_skill(client: AtomGitClient, tag: str, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    file_count = 0
    total_bytes = 0

    for entry in _walk_remote_files(client, SKILL_REPOSITORY_PATH, tag):
        file_count += 1
        if file_count > MAX_FILES:
            raise UpdateError(f"Skill contains more than {MAX_FILES} files")

        data, sha = client.read_file(entry["path"], tag)
        total_bytes += len(data)
        if total_bytes > MAX_TOTAL_BYTES:
            raise UpdateError(f"Skill exceeds {MAX_TOTAL_BYTES} bytes")
        if git_blob_sha(data) != sha.lower():
            raise UpdateError(f"Blob SHA mismatch for {entry['path']}")

        relative = _safe_relative_path(entry["path"])
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    if file_count == 0:
        raise UpdateError("Downloaded Skill is empty")


def validate_staged_skill(
    staged_dir: Path, expected_version: Tuple[int, int, int]
) -> None:
    metadata = read_skill_metadata(staged_dir / "SKILL.md")
    actual_version = parse_version(metadata["version"])
    if actual_version != expected_version:
        raise UpdateError(
            f"Tag version {expected_version} does not match Skill version {actual_version}"
        )
    if not (staged_dir / "scripts" / "update_skill.py").is_file():
        raise UpdateError("Downloaded Skill does not include the updater")


def is_hapray_source_checkout(skill_dir: Path) -> bool:
    repository_root = skill_dir.parent.parent
    package_file = repository_root / "package.json"
    if (
        skill_dir.parent.name != "skills"
        or not (repository_root / ".git").exists()
        or not package_file.is_file()
    ):
        return False
    try:
        package = json.loads(package_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    repository = package.get("repository")
    repository_url = (
        repository.get("url", "") if isinstance(repository, dict) else repository or ""
    )
    return package.get("name") == "hapray" and "ArkAnalyzer-HapRay" in str(
        repository_url
    )


def _replace_path(source: Path, target: Path) -> None:
    os.replace(str(source), str(target))


def install_staged_skill(skill_dir: Path, staged_dir: Path) -> None:
    backup_dir = skill_dir.parent / f".{skill_dir.name}.backup-{os.getpid()}"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)

    _replace_path(skill_dir, backup_dir)
    try:
        _replace_path(staged_dir, skill_dir)
    except BaseException:
        try:
            if skill_dir.exists():
                shutil.rmtree(skill_dir)
            _replace_path(backup_dir, skill_dir)
        except BaseException as rollback_error:
            raise UpdateError(
                f"Skill replacement failed and rollback also failed; backup remains at {backup_dir}: {rollback_error}"
            ) from rollback_error
        raise
    else:
        shutil.rmtree(backup_dir)


def update_skill(
    skill_dir: Path,
    client: AtomGitClient,
    check_only: bool = False,
) -> Dict[str, str]:
    skill_dir = skill_dir.resolve()
    metadata = read_skill_metadata(skill_dir / "SKILL.md")
    if is_hapray_source_checkout(skill_dir):
        return {
            "status": "source_checkout",
            "version": metadata["version"],
            "message": "Use Git to update the ArkAnalyzer-HapRay source checkout.",
        }
    current_version = parse_version(metadata["version"])
    tag, latest_version = client.latest_stable_tag()

    if latest_version <= current_version:
        return {"status": "current", "version": metadata["version"], "tag": tag}
    if check_only:
        return {
            "status": "available",
            "version": metadata["version"],
            "latest_version": ".".join(str(part) for part in latest_version),
            "tag": tag,
        }

    staged_parent = Path(
        tempfile.mkdtemp(prefix=f".{skill_dir.name}.update-", dir=str(skill_dir.parent))
    )
    staged_dir = staged_parent / skill_dir.name
    try:
        download_skill(client, tag, staged_dir)
        validate_staged_skill(staged_dir, latest_version)
        install_staged_skill(skill_dir, staged_dir)
    finally:
        if staged_parent.exists():
            shutil.rmtree(staged_parent, ignore_errors=True)

    return {
        "status": "updated",
        "version": ".".join(str(part) for part in latest_version),
        "previous_version": metadata["version"],
        "tag": tag,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skill-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Installed hapray Skill directory (defaults to this script's parent Skill)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Report an available update without installing it",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code when the update check fails",
    )
    parser.add_argument(
        "--api-base",
        default=os.environ.get("HAPRAY_SKILL_UPDATE_API", DEFAULT_API_BASE),
    )
    parser.add_argument(
        "--repository",
        default=os.environ.get("HAPRAY_SKILL_UPDATE_REPOSITORY", DEFAULT_REPOSITORY),
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if os.environ.get("HAPRAY_SKILL_AUTO_UPDATE", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        print(json.dumps({"status": "disabled"}, ensure_ascii=False))
        return 0

    client = AtomGitClient(args.api_base, args.repository)
    try:
        result = update_skill(args.skill_dir, client, check_only=args.check_only)
    except Exception as error:
        print(
            json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1 if args.strict else 0

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
