#!/usr/bin/env python3

import base64
import hashlib
import importlib.util
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, unquote, urlparse


MODULE_PATH = Path(__file__).with_name("update_skill.py")
SPEC = importlib.util.spec_from_file_location("hapray_update_skill", MODULE_PATH)
assert SPEC and SPEC.loader
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)


def blob_sha(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


class FakeAtomGitServer:
    def __init__(self, version="1.5.3", fail_path=None):
        self.version = version
        self.tag = f"v{version}"
        self.fail_path = fail_path
        self.files = {
            "skills/hapray/SKILL.md": (
                f'---\nname: hapray\nversion: "{version}"\ndescription: test\n---\nnew skill\n'.encode()
            ),
            "skills/hapray/scripts/update_skill.py": b"# updater\n",
            "skills/hapray/workflow/new.md": b"new workflow\n",
        }
        self.server = None
        self.thread = None

    def __enter__(self):
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                if fixture.fail_path and fixture.fail_path in unquote(parsed.path):
                    self.send_error(500)
                    return
                marker = "/repos/SMAT/ArkAnalyzer-HapRay/"
                if marker not in parsed.path:
                    self.send_error(404)
                    return
                endpoint = unquote(parsed.path.split(marker, 1)[1])
                if endpoint == "tags":
                    self._json([{"name": fixture.tag}, {"name": "v1.5.2"}])
                    return
                if not endpoint.startswith("contents/"):
                    self.send_error(404)
                    return
                repository_path = endpoint[len("contents/") :]
                if parse_qs(parsed.query).get("ref") != [fixture.tag]:
                    self.send_error(404)
                    return
                if repository_path in fixture.files:
                    data = fixture.files[repository_path]
                    self._json(
                        {
                            "type": "file",
                            "path": repository_path,
                            "encoding": "base64",
                            "content": base64.b64encode(data).decode("ascii"),
                            "sha": blob_sha(data),
                        }
                    )
                    return
                prefix = repository_path.rstrip("/") + "/"
                children = {}
                for file_path, data in fixture.files.items():
                    if not file_path.startswith(prefix):
                        continue
                    remainder = file_path[len(prefix) :]
                    name = remainder.split("/", 1)[0]
                    child_path = prefix + name
                    children[name] = {
                        "name": name,
                        "path": child_path,
                        "type": "dir" if "/" in remainder else "file",
                        "sha": blob_sha(data) if "/" not in remainder else "directory",
                    }
                if children:
                    self._json(list(children.values()))
                    return
                self.send_error(404)

            def _json(self, payload):
                data = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format, *args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_port}/api/v5"

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def create_installed_skill(root, version="1.5.2"):
    skill_dir = root / "hapray"
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f'---\nname: hapray\nversion: "{version}"\ndescription: test\n---\nold skill\n',
        encoding="utf-8",
    )
    (skill_dir / "scripts" / "update_skill.py").write_text(
        "# old updater\n", encoding="utf-8"
    )
    (skill_dir / "obsolete.md").write_text("remove me\n", encoding="utf-8")
    return skill_dir


class UpdateSkillTests(unittest.TestCase):
    def test_updates_152_to_153_and_replaces_the_complete_skill(self):
        with tempfile.TemporaryDirectory() as temp, FakeAtomGitServer() as api_base:
            skill_dir = create_installed_skill(Path(temp))
            result = updater.update_skill(
                skill_dir, updater.AtomGitClient(api_base, updater.DEFAULT_REPOSITORY)
            )

            self.assertEqual(result["status"], "updated")
            self.assertEqual(result["previous_version"], "1.5.2")
            self.assertEqual(result["version"], "1.5.3")
            self.assertFalse((skill_dir / "obsolete.md").exists())
            self.assertEqual(
                (skill_dir / "workflow" / "new.md").read_text(), "new workflow\n"
            )

    def test_current_version_is_left_untouched(self):
        with tempfile.TemporaryDirectory() as temp, FakeAtomGitServer() as api_base:
            skill_dir = create_installed_skill(Path(temp), version="1.5.3")
            result = updater.update_skill(
                skill_dir, updater.AtomGitClient(api_base, updater.DEFAULT_REPOSITORY)
            )

            self.assertEqual(result["status"], "current")
            self.assertTrue((skill_dir / "obsolete.md").exists())

    def test_source_checkout_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as temp, FakeAtomGitServer() as api_base:
            repository_root = Path(temp) / "ArkAnalyzer-HapRay"
            (repository_root / ".git").mkdir(parents=True)
            (repository_root / "package.json").write_text(
                json.dumps(
                    {
                        "name": "hapray",
                        "repository": {
                            "url": "git+https://gitcode.com/SMAT/ArkAnalyzer-HapRay.git"
                        },
                    }
                ),
                encoding="utf-8",
            )
            skill_dir = create_installed_skill(repository_root / "skills")
            result = updater.update_skill(
                skill_dir,
                updater.AtomGitClient(api_base, updater.DEFAULT_REPOSITORY),
            )

            self.assertEqual(result["status"], "source_checkout")
            self.assertEqual(
                updater.read_skill_metadata(skill_dir / "SKILL.md")["version"],
                "1.5.2",
            )
            self.assertTrue((skill_dir / "obsolete.md").exists())

    def test_download_failure_keeps_the_installed_version(self):
        with (
            tempfile.TemporaryDirectory() as temp,
            FakeAtomGitServer(fail_path="workflow/new.md") as api_base,
        ):
            skill_dir = create_installed_skill(Path(temp))
            with self.assertRaises(updater.UpdateError):
                updater.update_skill(
                    skill_dir,
                    updater.AtomGitClient(api_base, updater.DEFAULT_REPOSITORY),
                )

            self.assertEqual(
                updater.read_skill_metadata(skill_dir / "SKILL.md")["version"], "1.5.2"
            )
            self.assertTrue((skill_dir / "obsolete.md").exists())

    def test_install_failure_rolls_back_the_previous_directory(self):
        with tempfile.TemporaryDirectory() as temp, FakeAtomGitServer() as api_base:
            skill_dir = create_installed_skill(Path(temp))
            real_replace = updater._replace_path
            calls = 0

            def fail_second_replace(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated replacement failure")
                return real_replace(source, target)

            with mock.patch.object(
                updater, "_replace_path", side_effect=fail_second_replace
            ):
                with self.assertRaises(OSError):
                    updater.update_skill(
                        skill_dir,
                        updater.AtomGitClient(api_base, updater.DEFAULT_REPOSITORY),
                    )

            self.assertEqual(
                updater.read_skill_metadata(skill_dir / "SKILL.md")["version"], "1.5.2"
            )
            self.assertTrue((skill_dir / "obsolete.md").exists())


if __name__ == "__main__":
    unittest.main()
