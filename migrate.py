#!/usr/bin/env python3
"""
Portainer-to-Arcane Migration Tool

Migrates Docker resources (stacks, containers, volumes, networks, registries,
users, settings) from Portainer CE/EE to Arcane.

Usage:
    python migrate.py [options]

See --help for full option list.
"""

__version__ = "0.4.1"

# ---------------------------------------------------------------------------
# Dependency bootstrap -- runs before any third-party imports
# ---------------------------------------------------------------------------

import importlib
import subprocess
import sys
import os


def _project_dir() -> str:
    """Directory that contains this script. The project venv lives here."""
    return os.path.dirname(os.path.abspath(__file__))


def _venv_dir() -> str:
    return os.path.join(_project_dir(), ".venv")


def _venv_python(venv_dir: str) -> str:
    if os.name == "nt":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def _in_virtualenv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def _missing_packages(python: str) -> list:
    """Package names this interpreter cannot import. Empty when both import."""
    code = (
        "import importlib\n"
        "missing = []\n"
        "for name in ('rich', 'requests'):\n"
        "    try:\n"
        "        importlib.import_module(name)\n"
        "    except ImportError:\n"
        "        missing.append(name)\n"
        "print('\\n'.join(missing))\n"
    )
    result = subprocess.run(
        [python, "-c", code],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ["rich", "requests"]
    return [line for line in result.stdout.splitlines() if line.strip()]


def _recommend_venv_package() -> None:
    """Tell the user how to get the stdlib venv module."""
    print()
    print("Python's venv module is not installed, so dependencies")
    print("cannot be installed into a virtual environment.")
    print()
    print("Install it, then run this again:")
    if sys.platform.startswith("linux"):
        print("  sudo apt install python3-venv    # Debian/Ubuntu")
        print("  sudo dnf install python3-venv    # Fedora/RHEL")
    elif sys.platform == "darwin":
        print("  brew install python3")
    else:
        print("  Install the venv module for this Python (often python3-venv).")
    print()


def _manual_venv_help(venv_dir: str) -> None:
    py = _venv_python(venv_dir)
    pip = os.path.join(os.path.dirname(py), "pip")
    req = os.path.join(_project_dir(), "requirements.txt")
    print("Create a virtual environment and install them:")
    print(f"  {sys.executable} -m venv {venv_dir}")
    if os.path.isfile(req):
        print(f"  {pip} install -r {req}")
    else:
        print(f"  {pip} install rich requests")
    print(f"  {py} {os.path.abspath(__file__)}")


def _venv_module_available() -> bool:
    try:
        import venv  # noqa: F401
    except ImportError:
        return False
    return True


def check_dependencies():
    """Verify that required third-party packages are installed.

    Missing packages are installed into a ``.venv`` next to this script,
    then the process restarts with that interpreter. An already-active
    virtual environment is used as-is. When the stdlib ``venv`` module is
    missing (Debian/Ubuntu without ``python3-venv``), tell the user how
    to install it instead of pip-installing into the system Python.
    """
    missing = []
    for pkg in ("rich", "requests"):
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing.append(pkg)
    if not missing:
        return

    venv_dir = _venv_dir()
    venv_python = _venv_python(venv_dir)

    # System Python is missing packages, but the project venv already has
    # them. Switch over without asking again.
    if not _in_virtualenv() and os.path.isfile(venv_python):
        if not _missing_packages(venv_python):
            result = subprocess.run([venv_python, *sys.argv])
            sys.exit(result.returncode)

    print(f"Missing required packages: {', '.join(missing)}")
    dest = "this virtual environment" if _in_virtualenv() else venv_dir
    try:
        answer = input(f"Install them into {dest}? [Y/n] ").strip().lower()
    except EOFError:
        print("No TTY to prompt for install.")
        print()
        if _in_virtualenv():
            print(f"  {sys.executable} -m pip install {' '.join(missing)}")
        else:
            _manual_venv_help(venv_dir)
        sys.exit(1)
    if answer not in ("", "y", "yes"):
        print("Cannot continue without required packages.")
        if not _in_virtualenv():
            print()
            _manual_venv_help(venv_dir)
        sys.exit(1)

    if _in_virtualenv():
        target = sys.executable
        install_cmd = [target, "-m", "pip", "install", *missing]
    else:
        if not os.path.isfile(venv_python):
            if not _venv_module_available():
                _recommend_venv_package()
                sys.exit(1)
            print(f"Creating {venv_dir}", flush=True)
            try:
                subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
            except subprocess.CalledProcessError:
                _recommend_venv_package()
                sys.exit(1)
            if not os.path.isfile(venv_python):
                _recommend_venv_package()
                sys.exit(1)
        target = venv_python
        req = os.path.join(_project_dir(), "requirements.txt")
        install_cmd = [target, "-m", "pip", "install"]
        if os.path.isfile(req):
            install_cmd += ["-r", req]
        else:
            install_cmd += missing

    # No --quiet: pip failures (missing ensurepip, network errors) stay
    # visible instead of turning into an ImportError on restart.
    try:
        subprocess.check_call(install_cmd)
    except subprocess.CalledProcessError:
        if not _in_virtualenv():
            print()
            print("If pip is missing inside the new environment, install")
            print("the venv package and remove the incomplete directory:")
            print("  sudo apt install python3-venv    # Debian/Ubuntu")
            print("  sudo dnf install python3-venv    # Fedora/RHEL")
            print(f"  rm -rf {venv_dir}")
        sys.exit(1)
    print("Dependencies installed. Restarting...", flush=True)
    # os.execv has surprising behaviour on Windows (parent may return
    # immediately). Spawn a fresh subprocess and exit with its code.
    result = subprocess.run([target, *sys.argv])
    sys.exit(result.returncode)


check_dependencies()

# ---------------------------------------------------------------------------
# Third-party imports (guaranteed present after check_dependencies)
# ---------------------------------------------------------------------------

import requests as http_requests  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402
from rich.progress import (  # noqa: E402
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)
from rich.prompt import Prompt, Confirm, IntPrompt  # noqa: E402
from rich.logging import RichHandler  # noqa: E402
from rich.text import Text  # noqa: E402
from rich.tree import Tree  # noqa: E402
from rich import box  # noqa: E402

# ---------------------------------------------------------------------------
# Standard-library imports
# ---------------------------------------------------------------------------

import argparse  # noqa: E402
import hashlib  # noqa: E402
import ipaddress  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import platform  # noqa: E402
import secrets  # noqa: E402
import re  # noqa: E402
import shlex  # noqa: E402
import shutil  # noqa: E402
import time  # noqa: E402
import warnings  # noqa: E402
from dataclasses import dataclass, field, asdict  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Optional, List, Dict, Any, Callable  # noqa: E402
from urllib.parse import urlparse  # noqa: E402

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

console = Console()

DISPLAY_NAMES = {
    "stacks": "Stacks",
    "standalone_containers": "Standalone Containers",
    "images": "Images",
    "volumes": "Volumes",
    "networks": "Networks",
    "registries": "Registries",
    "custom_templates": "Custom Templates",
    "users": "Users",
    "webhooks": "Webhooks",
    "teams": "Teams",
    "roles": "Roles",
    "edge_stacks": "Edge Stacks",
    "settings": "Settings",
    "team_memberships": "Team Memberships",
    "resource_controls": "Resource Controls",
    "activity_logs": "Activity Logs",
}

_SENSITIVE_KEY_RE = re.compile(
    r"(password|passwd|secret|token|apikey|api_key|credential|authorization|"
    r"accesskey|access_key|privatekey|private_key|awssecretaccesskey|bearer)",
    re.IGNORECASE,
)


def _redact_sensitive(obj: Any) -> Any:
    """Deep-copy *obj* with any value under a secret-looking key masked.

    Used before logging or serializing payloads that may carry credentials
    (registry passwords, user passwords, git tokens, AWS keys, etc.).
    Keys matching ``_SENSITIVE_KEY_RE`` have their value replaced with
    ``"[REDACTED]"``. Unknown types pass through unchanged.
    """
    if isinstance(obj, dict):
        return {
            k: ("[REDACTED]" if isinstance(k, str) and _SENSITIVE_KEY_RE.search(k) and v
                else _redact_sensitive(v))
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        cls = type(obj)
        return cls(_redact_sensitive(v) for v in obj)
    return obj


_PROJECTS_DIR_PERM_RE = re.compile(
    r"projects directory\s+(\S+)\s+must be writable by uid\s+(\d+)",
    re.IGNORECASE,
)


class MigrationStopped(Exception):
    """The Arcane host will reject every remaining project create the same way.

    ``action_item`` is the one-line note stored on the migration report.
    """

    def __init__(self, message: str, action_item: str):
        super().__init__(message)
        self.action_item = action_item


def projects_directory_block(exc: BaseException) -> Optional["MigrationStopped"]:
    """Return a stop signal when *exc* is Arcane's projects-directory 403.

    Arcane creates each project as a subdirectory of its projects directory
    (often ``/opt/docker``). When that directory is not writable by the
    Arcane user, every later stack fails with the same permission error.
    Other failures (name conflicts, bad mount options) return None so the
    run can continue with the next resource.
    """
    text = str(exc)
    lowered = text.lower()
    directory_problem = (
        "projects directory" in lowered
        or "create project directory" in lowered
        or "failed to create project directory" in lowered
    )
    permission_problem = (
        "permission denied" in lowered or "must be writable" in lowered
    )
    if not (directory_problem and permission_problem):
        return None

    directory = ""
    uid = ""
    match = _PROJECTS_DIR_PERM_RE.search(text)
    if match:
        directory = match.group(1).rstrip(".,)")
        uid = match.group(2)

    if directory and uid:
        lead = (
            f"Arcane cannot create projects. {directory} must be writable "
            f"by uid {uid}."
        )
        fix = (
            "On the Arcane host, run:\n"
            f"  sudo chown -R {uid}:{uid} {directory}\n"
            f"  sudo chmod u+rwx {directory}\n"
        )
        action = (
            f"Make {directory} writable by uid {uid}, then run with --resume."
        )
    else:
        lead = (
            "Arcane cannot create projects because the projects directory "
            "is not writable."
        )
        fix = (
            "On the Arcane host, make the projects directory writable by "
            "the Arcane process user.\n"
        )
        action = (
            "Make the Arcane projects directory writable by the Arcane "
            "user, then run with --resume."
        )
    message = (
        f"{lead}\n"
        f"{fix}"
        "Then resume this migration with --resume.\n"
        "Resources already created are listed in the report and rollback script."
    )
    return MigrationStopped(message, action)


# Docker rejects a bind mode when any token is unknown
# ("invalid mode: rw,rprivate,rbind"). Podman inspect copies kernel mount
# flags (rbind, nosuid, nodev, …) into HostConfig.Binds. Those flags are
# not create options. Propagation is legal on a bind mount and illegal on
# a named volume ("BindOptions must not be specified").
_VOLUME_MOUNT_MODES = {"ro", "rw", "z", "Z", "nocopy"}
_BIND_MOUNT_MODES = _VOLUME_MOUNT_MODES | {
    "private", "rprivate",
    "shared", "rshared",
    "slave", "rslave",
}

_PODMAN_SOCKETS = {
    "/run/podman/podman.sock",
    "/var/run/podman/podman.sock",
}
_DOCKER_SOCKETS = {
    "/var/run/docker.sock",
    "/run/docker.sock",
}


def _sanitize_mount_mode(mode: str, *, bind: bool) -> str:
    """Keep only mount options the Docker create API accepts for this source."""
    allowed = _BIND_MOUNT_MODES if bind else _VOLUME_MOUNT_MODES
    kept = []
    for part in (mode or "").split(","):
        token = part.strip()
        if token in allowed and token not in kept:
            kept.append(token)
    return ",".join(kept)


_PODMAN_VOLUME_HOST = re.compile(
    r"^/var/lib/containers/storage/volumes/([^/]+)/_data/?$"
)
_DOCKER_VOLUME_HOST = re.compile(
    r"^/var/lib/docker/volumes/([^/]+)/_data/?$"
)


def classify_engine(info: Optional[dict]) -> str:
    """Return ``podman``, ``docker``, or ``""`` when *info* is missing.

    Podman's Docker-compatible ``/info`` reports a storage root under
    ``/var/lib/containers``. Docker reports ``/var/lib/docker``. A Podman
    init binary or a ``Name`` of ``podman`` counts when the root is absent.
    """
    if not isinstance(info, dict) or not info:
        return ""
    root = str(info.get("DockerRootDir") or "").replace("\\", "/").lower()
    name = str(info.get("Name") or "").strip().lower()
    init_bin = str(info.get("InitBinary") or "").lower()
    if "/var/lib/containers" in root or "podman" in init_bin or name == "podman":
        return "podman"
    if root or info.get("ID") or info.get("ServerVersion"):
        return "docker"
    return ""


def engine_summary(kind: str, info: Optional[dict]) -> str:
    """One line for the preflight table. ``kind`` is podman, docker, or empty."""
    if not kind:
        return "not detected"
    label = "Podman" if kind == "podman" else "Docker"
    version = str((info or {}).get("ServerVersion") or "unknown")
    root = str((info or {}).get("DockerRootDir") or "unknown root")
    return f"{label} {version}, root {root}"


def _named_volume_from_host_path(path: str) -> str:
    """``.../volumes/<name>/_data`` is that named volume, not a bind path."""
    for pattern in (_PODMAN_VOLUME_HOST, _DOCKER_VOLUME_HOST):
        match = pattern.match(path or "")
        if match:
            return match.group(1)
    return path


def _rewrite_engine_socket(
    source: str, source_engine: str, target_engine: str
) -> str:
    """Point an engine-socket bind at the destination engine.

    When both sides are the same kind, the path is already right. When the
    source kind is unknown, the path itself decides: a Podman socket is
    rewritten for a Docker target, and a Docker socket for a Podman target.
    """
    path = (source or "").rstrip("/") or source
    if source_engine and target_engine and source_engine == target_engine:
        return source
    source_is_podman = source_engine in ("", "podman")
    source_is_docker = source_engine in ("", "docker")
    if source_is_podman and target_engine == "docker" and path in _PODMAN_SOCKETS:
        return "/var/run/docker.sock"
    if source_is_docker and target_engine == "podman" and path in _DOCKER_SOCKETS:
        return "/run/podman/podman.sock"
    return source


def normalize_bind_spec(
    spec: str, target_engine: str = "", source_engine: str = ""
) -> str:
    """Turn one Podman or Docker bind into a spec the target engine accepts.

    ``src:dst[:mode]``. The mode loses flags Docker rejects. Propagation
    stays on a host path and is removed from a named volume. A volume
    ``_data`` directory becomes the volume name. Sockets are rewritten
    only when the two engines are different kinds.
    """
    parts = spec.split(":")
    if len(parts) >= 2 and parts[0]:
        parts[0] = _named_volume_from_host_path(parts[0])
        parts[0] = _rewrite_engine_socket(parts[0], source_engine, target_engine)
    # A mode does not contain a slash. A path in the last field is not a mode.
    if len(parts) >= 3 and "/" not in parts[-1] and "\\" not in parts[-1]:
        source = parts[0]
        bind = source.startswith("/") or (len(source) > 2 and source[1] == ":")
        mode = _sanitize_mount_mode(parts[-1], bind=bind)
        head = ":".join(parts[:-1])
        return f"{head}:{mode}" if mode else head
    return ":".join(parts)


def _name_conflict(exc: BaseException) -> bool:
    """True when the engine rejected a create because the name is taken."""
    text = str(exc).lower()
    return "already exists" in text


# Exact container or stack names. A workload that merely contains the word
# (portainer-proxy, arcane-exporter) is not one of these apps.
_MANAGEMENT_APP_NAMES = {
    "portainer": "Portainer",
    "portainer-ce": "Portainer",
    "portainer-ee": "Portainer",
    "portainer-agent": "Portainer",
    "portainer_agent": "Portainer",
    "arcane": "Arcane",
}
_MANAGEMENT_IMAGE_REPOS = (
    ("portainer/portainer-ce", "Portainer"),
    ("portainer/portainer-ee", "Portainer"),
    ("portainer/portainer", "Portainer"),
    ("portainer/agent", "Portainer"),
    ("getarcaneapp/arcane", "Arcane"),
)


def _image_repo(image: str) -> str:
    """``registry/org/name:tag`` -> ``org/name``, without a digest or tag."""
    ref = (image or "").strip().lower()
    if not ref or ref.startswith("sha256:"):
        return ""
    ref = ref.split("@", 1)[0]
    last = ref.rsplit("/", 1)[-1]
    if ":" in last:
        ref = ref[: -(len(last.split(":", 1)[1]) + 1)]
    for prefix in ("docker.io/", "ghcr.io/", "registry.hub.docker.com/"):
        if ref.startswith(prefix):
            ref = ref[len(prefix):]
            break
    return ref


def container_image_ref(item: Any) -> str:
    """Image tag from a container list entry or an inspect payload."""
    if not isinstance(item, dict):
        return ""
    image = item.get("Image") or ""
    if not isinstance(image, str) or image.startswith("sha256:"):
        image = ""
    if not image:
        config = item.get("Config")
        if isinstance(config, dict):
            image = str(config.get("Image") or "")
    return image


def management_app(name: str, image: str = "") -> str:
    """Return ``Portainer`` or ``Arcane`` when this is that product's own app.

    Image match uses the repository. Name match is exact after a leading
    slash. Other containers and stacks are workloads and stay in the migration.
    """
    repo = _image_repo(image)
    for suffix, app in _MANAGEMENT_IMAGE_REPOS:
        if repo == suffix or repo.endswith("/" + suffix):
            return app
    bare = (name or "").strip().lstrip("/").lower()
    return _MANAGEMENT_APP_NAMES.get(bare, "")


def _ssl_verify_default(url: str) -> bool:
    """Whether "Verify SSL certificate?" should default to yes.

    A private, loopback, or link-local address defaults to no. Those hosts
    almost always present a certificate that is not publicly trusted.
    A hostname, including localhost, still defaults to yes.
    """
    text = (url or "").strip()
    if "://" not in text:
        text = "https://" + text
    host = urlparse(text).hostname or ""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    local = address.is_private or address.is_loopback or address.is_link_local
    return not local


def _quiet_unverified_https() -> None:
    """Silence urllib3 after the user turns certificate verification off.

    The wizard already asked and the user said no. urllib3 still prints
    ``InsecureRequestWarning`` on every request to that host.
    """
    try:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")


# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------


@dataclass
class Config:
    """Central configuration for the migration run."""

    # -- Portainer ---------------------------------------------------------
    portainer_url: str = ""
    portainer_api_key: str = ""
    portainer_endpoint_id: int = 1
    portainer_ssl_verify: bool = True
    portainer_edition: str = ""
    portainer_version: str = ""

    # -- Arcane ------------------------------------------------------------
    arcane_url: str = ""
    arcane_api_key: str = ""
    arcane_username: str = ""
    arcane_password: str = ""
    arcane_token: str = ""
    arcane_refresh_token: str = ""
    arcane_environment_id: str = "0"
    arcane_ssl_verify: bool = True

    # -- Options -----------------------------------------------------------
    # Empty until resolved by --export-only, --import-dir, or the strategy
    # prompt — so the mode badge doesn't falsely advertise EXPORT-ONLY on
    # early phase headers before the user actually picks.
    strategy: str = ""
    dry_run: bool = False
    backup_dir: str = "./migration_export"
    log_file: str = ""

    # -- Runtime -----------------------------------------------------------
    docker_socket: str = ""
    has_docker: bool = False
    platform_name: str = ""

    # -- Import mode -------------------------------------------------------
    import_mode: bool = False

    # -- State -------------------------------------------------------------
    checkpoint_file: str = "./migration_state.json"
    selected_items: Dict[str, List[str]] = field(default_factory=dict)

    # -- Methods -----------------------------------------------------------

    def detect_platform(self):
        """Detect OS, set the Docker socket path, and check docker availability."""
        self.platform_name = platform.system().lower()
        if self.platform_name == "windows":
            self.docker_socket = "//./pipe/docker_engine"
        else:
            self.docker_socket = "/var/run/docker.sock"
        self.has_docker = shutil.which("docker") is not None

    def to_dict(self) -> Dict[str, Any]:
        """Return a dict representation with secrets masked."""
        d = asdict(self)
        for key in (
            "portainer_api_key",
            "arcane_api_key",
            "arcane_password",
            "arcane_token",
            "arcane_refresh_token",
        ):
            if d.get(key):
                d[key] = d[key][:4] + "****"
        return d

    def config_hash(self) -> str:
        """SHA-256 fingerprint of the key connection identifiers."""
        payload = (
            f"{self.portainer_url}|{self.portainer_endpoint_id}"
            f"|{self.arcane_url}|{self.arcane_environment_id}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# PortainerClient
# ---------------------------------------------------------------------------


class PortainerClient:
    """Read-only wrapper around the Portainer CE / EE API."""

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.session = http_requests.Session()
        self.session.headers.update({"X-API-Key": config.portainer_api_key})
        self.session.verify = config.portainer_ssl_verify
        if not config.portainer_ssl_verify:
            _quiet_unverified_https()
        self.base_url = config.portainer_url.rstrip("/")

    # -- low-level helpers -------------------------------------------------

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """GET *path* (relative to base_url) and return parsed JSON.

        Retries transient network errors (ConnectionError, Timeout) up to
        three times with exponential backoff. Does NOT retry on HTTPError —
        4xx/5xx are treated as authoritative responses.
        """
        url = f"{self.base_url}{path}"
        self.logger.debug("GET %s params=%s", url, params)
        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=30)
                resp.raise_for_status()
                break
            except (
                http_requests.exceptions.ConnectionError,
                http_requests.exceptions.Timeout,
            ) as exc:
                last_exc = exc
                if attempt == 2:
                    raise
                wait = 2 ** attempt
                self.logger.warning(
                    "GET %s transient failure (%s); retry in %ss",
                    url, exc.__class__.__name__, wait,
                )
                time.sleep(wait)
        ctype = resp.headers.get("Content-Type", "")
        try:
            return resp.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Expected JSON from {url}, got Content-Type={ctype!r}: "
                f"{resp.text[:200]}"
            ) from exc

    def _safe_get(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Like _get but returns [] on 404 (EE-only endpoint on CE).

        403 is treated as a permission problem rather than a missing feature:
        the caller is told their API key can't see the resource. The call
        still degrades to an empty list so discovery/export proceeds, but the
        WARNING lets the user know their data may be incomplete.
        """
        try:
            return self._get(path, params)
        except http_requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 404:
                self.logger.debug(
                    "Endpoint %s returned 404 -- treating as empty (EE-only?)", path
                )
                return []
            if status == 403:
                self.logger.warning(
                    "Endpoint %s returned 403 -- your Portainer API key lacks "
                    "permission; treating as empty", path
                )
                return []
            raise

    def _docker(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Proxied Docker API call via Portainer endpoint.

        Surfaces endpoint ID in the exception message so a failure on a
        multi-endpoint Portainer is easy to attribute.
        """
        eid = self.config.portainer_endpoint_id
        try:
            return self._get(f"/api/endpoints/{eid}/docker{path}", params)
        except http_requests.exceptions.HTTPError as exc:
            exc.args = (f"endpoint {eid}: {exc.args[0] if exc.args else exc}",)
            raise

    def _safe_docker(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Proxied Docker API call that returns [] on 404/403."""
        eid = self.config.portainer_endpoint_id
        return self._safe_get(f"/api/endpoints/{eid}/docker{path}", params)

    # -- CE + EE methods ---------------------------------------------------

    def test_connection(self) -> Dict[str, Any]:
        """GET /api/status -- returns version + edition info."""
        return self._get("/api/status")

    def detect_edition(self) -> Dict[str, Any]:
        """Call test_connection and populate config edition/version fields."""
        status = self.test_connection()
        self.config.portainer_version = status.get("Version", "")
        # Edition field present in EE; absent or "CE" in Community
        edition = status.get("Edition", "CE")
        if isinstance(edition, int):
            edition = "EE" if edition >= 2 else "CE"
        self.config.portainer_edition = edition
        self.logger.info(
            "Portainer %s %s detected",
            self.config.portainer_edition,
            self.config.portainer_version,
        )
        return status

    def list_endpoints(self) -> List[Dict[str, Any]]:
        return self._get("/api/endpoints")

    def get_endpoint(self, endpoint_id: int) -> Dict[str, Any]:
        return self._get(f"/api/endpoints/{endpoint_id}")

    def list_stacks(self) -> List[Dict[str, Any]]:
        return self._get("/api/stacks")

    def get_stack(self, stack_id: int) -> Dict[str, Any]:
        return self._get(f"/api/stacks/{stack_id}")

    def get_stack_file(self, stack_id: int) -> Dict[str, Any]:
        return self._get(f"/api/stacks/{stack_id}/file")

    def list_registries(self) -> List[Dict[str, Any]]:
        return self._get("/api/registries")

    def list_users(self) -> List[Dict[str, Any]]:
        return self._get("/api/users")

    def get_settings(self) -> Dict[str, Any]:
        return self._get("/api/settings")

    def list_custom_templates(self) -> Any:
        return self._safe_get("/api/custom_templates")

    def get_custom_template_file(self, template_id: int) -> Dict[str, Any]:
        return self._get(f"/api/custom_templates/{template_id}/file")

    def trigger_backup(self, password: str = "", dest_path: Optional[str] = None) -> bytes:
        """POST /api/backup.

        If *dest_path* is provided, stream the response directly to disk and
        return b"". Otherwise load the whole archive into memory and return
        it (retained for backward-compat). Streaming is strongly preferred
        for large Portainer instances where the archive can exceed RAM.
        """
        url = f"{self.base_url}/api/backup"
        self.logger.debug("POST %s (backup)", url)
        if dest_path is None:
            # Legacy in-memory path; kept for compatibility. Callers with
            # large backups should pass dest_path to avoid OOM.
            resp = self.session.post(
                url, json={"password": password}, timeout=600
            )
            resp.raise_for_status()
            return resp.content
        with self.session.post(
            url, json={"password": password}, timeout=600, stream=True
        ) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)
        return b""

    # -- EE-only methods ---------------------------------------------------

    def list_webhooks(self) -> Any:
        return self._safe_get("/api/webhooks")

    def list_teams(self) -> Any:
        return self._safe_get("/api/teams")

    def list_team_memberships(self) -> Any:
        return self._safe_get("/api/team_memberships")

    def list_roles(self) -> Any:
        return self._safe_get("/api/roles")

    def list_resource_controls(self) -> Any:
        return self._safe_get("/api/resource_controls")

    def list_edge_stacks(self) -> Any:
        return self._safe_get("/api/edge_stacks")

    # -- Docker proxy methods ----------------------------------------------

    def list_containers(self, all_containers: bool = True) -> List[Dict[str, Any]]:
        params = {"all": "true"} if all_containers else {}
        return self._docker("/containers/json", params)

    def inspect_container(self, container_id: str) -> Dict[str, Any]:
        return self._docker(f"/containers/{container_id}/json")

    def list_images(self) -> List[Dict[str, Any]]:
        return self._docker("/images/json")

    def list_volumes(self) -> Dict[str, Any]:
        return self._docker("/volumes")

    def list_networks(self) -> List[Dict[str, Any]]:
        return self._docker("/networks")

    def get_docker_info(self) -> Dict[str, Any]:
        return self._docker("/info")

    def get_system_df(self) -> Any:
        return self._safe_docker("/system/df")


# ---------------------------------------------------------------------------
# ArcaneClient
# ---------------------------------------------------------------------------


class ArcaneClient:
    """Read+write wrapper around the Arcane API."""

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.session = http_requests.Session()
        self.session.verify = config.arcane_ssl_verify
        if not config.arcane_ssl_verify:
            _quiet_unverified_https()
        self.base_url = config.arcane_url.rstrip("/") + "/api"

    # -- auth helpers ------------------------------------------------------

    def _auth_headers(self) -> Dict[str, str]:
        """Return the appropriate authorization header."""
        if self.config.arcane_api_key:
            return {"X-API-Key": self.config.arcane_api_key}
        if self.config.arcane_token:
            return {"Authorization": f"Bearer {self.config.arcane_token}"}
        return {}

    # -- low-level helpers -------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        files: Optional[Any] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Generic request with auth, timeout, and error handling."""
        url = f"{self.base_url}{path}"
        headers = self._auth_headers()
        self.logger.debug(
            "%s %s json=%s params=%s",
            method,
            url,
            _redact_sensitive(json_data),
            _redact_sensitive(params),
        )
        resp = self.session.request(
            method,
            url,
            headers=headers,
            json=json_data,
            params=params,
            files=files,
            timeout=timeout if timeout is not None else 60,
        )
        if not resp.ok:
            # Include the response body in the exception text. raise_for_status()
            # only says "422 Client Error", which hid the real reason
            # (Arcane 2.x project create requires multipart, name conflicts, …).
            body_snippet = resp.text[:500] if resp.text else ""
            self.logger.error(
                "%s %s -> %s: %s", method, url, resp.status_code, body_snippet
            )
            raise http_requests.HTTPError(
                f"{resp.status_code} {resp.reason} for url: {url}: {body_snippet}",
                response=resp,
            )
        if resp.status_code == 204 or not resp.content:
            return {}
        ctype = resp.headers.get("Content-Type", "")
        try:
            body = resp.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Expected JSON from {url}, got Content-Type={ctype!r}: "
                f"{resp.text[:200]}"
            ) from exc
        # Arcane wraps most responses in {"success": bool, "data": ...}.
        # Unwrap automatically so callers receive the inner payload directly.
        if isinstance(body, dict) and "data" in body and "success" in body:
            return body["data"]
        return body

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request("GET", path, params=params)

    def _list_paginated(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        page_size: int = 200,
    ) -> List[Dict[str, Any]]:
        """GET a paginated Arcane list endpoint, looping until exhausted.

        Arcane list endpoints default to limit=20 and return responses
        shaped ``{success, data, pagination}`` where pagination carries
        ``totalItems`` / ``itemsPerPage`` / ``currentPage``. Without this
        loop, the tool would silently stop at the first 20 items on any
        install with more than that — a silent migration truncation.

        We bypass ``_request``'s auto-unwrap by calling the HTTP layer
        directly, so we can read the pagination sibling field.
        """
        url = f"{self.base_url}{path}"
        headers = self._auth_headers()
        items: List[Dict[str, Any]] = []
        start = 0
        while True:
            page_params = dict(params or {})
            page_params["start"] = start
            page_params["limit"] = page_size
            self.logger.debug(
                "GET %s params=%s", url, _redact_sensitive(page_params)
            )
            resp = self.session.get(
                url, headers=headers, params=page_params, timeout=60
            )
            resp.raise_for_status()
            if resp.status_code == 204 or not resp.content:
                break
            try:
                body = resp.json()
            except ValueError as exc:
                raise RuntimeError(
                    f"Expected JSON from {url}: {resp.text[:200]}"
                ) from exc
            if not isinstance(body, dict):
                # Endpoint returned a bare list (non-paginated) — just use it.
                if isinstance(body, list):
                    items.extend(body)
                break
            page = body.get("data") or []
            items.extend(page)
            pagination = body.get("pagination") or {}
            total = pagination.get("totalItems")
            if total is not None and len(items) >= total:
                break
            if not page or len(page) < page_size:
                break
            start += page_size
        return items

    def _post(
        self,
        path: str,
        json_data: Optional[Any] = None,
        files: Optional[Any] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        return self._request(
            "POST", path, json_data=json_data, files=files, timeout=timeout
        )

    def _put(self, path: str, json_data: Optional[Any] = None) -> Any:
        return self._request("PUT", path, json_data=json_data)

    def _delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    # -- Auth --------------------------------------------------------------

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """POST /auth/login -- store token in config."""
        data = self._request(
            "POST", "/auth/login", json_data={"username": username, "password": password}
        )
        self.config.arcane_token = data.get("token", "")
        self.config.arcane_refresh_token = data.get("refreshToken", data.get("refresh_token", ""))
        self.logger.info("Arcane login successful")
        return data

    # -- Health ------------------------------------------------------------

    def health_check(self) -> Any:
        return self._get("/health")

    def get_version(self) -> Any:
        return self._get("/app-version")

    # -- Environments ------------------------------------------------------

    def list_environments(self) -> List[Dict[str, Any]]:
        return self._list_paginated("/environments")

    def get_environment(self, eid: str) -> Dict[str, Any]:
        return self._get(f"/environments/{eid}")

    # -- Registries --------------------------------------------------------

    def list_registries(self) -> List[Dict[str, Any]]:
        return self._list_paginated("/container-registries")

    def create_registry(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post("/container-registries", json_data=data)

    # -- Git repos ---------------------------------------------------------

    def list_git_repos(self) -> List[Dict[str, Any]]:
        return self._list_paginated("/customize/git-repositories")

    def create_git_repo(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post("/customize/git-repositories", json_data=data)

    # -- Projects ----------------------------------------------------------

    def list_projects(self, eid: str) -> List[Dict[str, Any]]:
        return self._list_paginated(f"/environments/{eid}/projects")

    def get_docker_info(self, eid: str) -> Dict[str, Any]:
        """Engine info for this environment. Podman reports a containers/storage root."""
        data = self._get(f"/environments/{eid}/system/docker/info")
        return data if isinstance(data, dict) else {}

    def create_project(self, eid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Compose project.

        Arcane 2.x rejects an ``application/json`` body on this route with
        422 ``cannot read multipart form``. The UI sends two JSON parts:
        ``project`` (name, composeContent, envContent) and ``manifest``
        (workspace file changes, empty when the compose file is the only input).
        Creating the project does not redeploy. A project whose compose name
        matches containers already running on this engine is attached to them.
        """
        project: Dict[str, Any] = {
            "name": data.get("name", ""),
            "composeContent": data.get("composeContent", ""),
        }
        if data.get("envContent") is not None:
            project["envContent"] = data.get("envContent") or ""
        manifest = {"fileChanges": data.get("fileChanges") or []}
        files = {
            "project": (None, json.dumps(project), "application/json"),
            "manifest": (None, json.dumps(manifest), "application/json"),
        }
        return self._request(
            "POST", f"/environments/{eid}/projects", files=files
        )

    # -- GitOps ------------------------------------------------------------

    def create_gitops_sync(self, eid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post(f"/environments/{eid}/gitops-syncs", json_data=data)

    # -- Networks ----------------------------------------------------------

    def list_networks(self, eid: str) -> List[Dict[str, Any]]:
        return self._list_paginated(f"/environments/{eid}/networks")

    def create_network(self, eid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post(f"/environments/{eid}/networks", json_data=data)

    # -- Volumes -----------------------------------------------------------

    def list_volumes(self, eid: str) -> List[Dict[str, Any]]:
        return self._list_paginated(f"/environments/{eid}/volumes")

    def create_volume(self, eid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post(f"/environments/{eid}/volumes", json_data=data)

    def upload_volume_backup(
        self, eid: str, name: str, filepath: str
    ) -> Dict[str, Any]:
        # Volume tarballs can be many GB; a 60s timeout would silently
        # truncate large uploads. Scale the timeout to file size (~1 MB/s
        # worst case) with a 10-minute floor and 4-hour cap.
        try:
            size = os.path.getsize(filepath)
        except OSError:
            size = 0
        timeout = min(max(600.0, size / 1_000_000.0), 14_400.0)
        with open(filepath, "rb") as fh:
            return self._post(
                f"/environments/{eid}/volumes/{name}/backups/upload",
                files={"file": (os.path.basename(filepath), fh, "application/gzip")},
                timeout=timeout,
            )

    # -- Containers --------------------------------------------------------

    def list_containers(self, eid: str) -> List[Dict[str, Any]]:
        return self._list_paginated(f"/environments/{eid}/containers")

    def create_container(self, eid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post(f"/environments/{eid}/containers", json_data=data)

    def start_container(self, eid: str, cid: str) -> Dict[str, Any]:
        return self._post(f"/environments/{eid}/containers/{cid}/start")

    # -- Users -------------------------------------------------------------

    def list_users(self) -> List[Dict[str, Any]]:
        return self._list_paginated("/users")

    def create_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post("/users", json_data=data)

    def set_user_role_assignments(
        self, user_id: str, assignments: List[Dict[str, Any]]
    ) -> Any:
        """Replace a user's manual role assignments.

        Arcane 2.17 rejects a ``roles`` field on ``POST /users`` with
        422 ``unexpected property``. Roles are applied with this call.
        Omit ``environmentId`` on an assignment for a global role.
        """
        return self._put(
            f"/users/{user_id}/role-assignments",
            json_data={"assignments": assignments},
        )

    # -- Webhooks ----------------------------------------------------------

    def list_webhooks(self, eid: str) -> List[Dict[str, Any]]:
        return self._list_paginated(f"/environments/{eid}/webhooks")

    def create_webhook(self, eid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post(f"/environments/{eid}/webhooks", json_data=data)

    # -- Templates ---------------------------------------------------------

    def list_templates(self) -> List[Dict[str, Any]]:
        return self._list_paginated("/templates")

    def create_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post("/templates", json_data=data)


# ---------------------------------------------------------------------------
# DockerLocal
# ---------------------------------------------------------------------------


class DockerLocal:
    """Local Docker socket / CLI operations for volume backup, etc."""

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def is_available(self) -> bool:
        """Return True if the docker CLI is functional."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def backup_volume(self, name: str, backup_dir: str) -> Optional[str]:
        """Create a tar.gz backup of a Docker volume. Returns filepath or None."""
        os.makedirs(backup_dir, exist_ok=True)
        archive_name = f"{name}.tar.gz"
        self.logger.info("Backing up volume %s to %s/%s", name, backup_dir, archive_name)
        try:
            result = subprocess.run(
                [
                    "docker", "run", "--rm",
                    "-v", f"{name}:/source:ro",
                    "-v", f"{os.path.abspath(backup_dir)}:/backup",
                    "alpine",
                    "tar", "czf", f"/backup/{archive_name}", "-C", "/source", ".",
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                self.logger.error(
                    "Volume backup failed for %s: %s", name, result.stderr.strip()
                )
                return None
            filepath = os.path.join(backup_dir, archive_name)
            self.logger.info("Volume %s backed up to %s", name, filepath)
            return filepath
        except subprocess.TimeoutExpired:
            self.logger.error("Volume backup timed out for %s", name)
            return None

    def get_volume_size(self, name: str) -> Optional[int]:
        """Return the size in bytes of a volume, or None on failure."""
        try:
            result = subprocess.run(
                [
                    "docker", "run", "--rm",
                    "-v", f"{name}:/source:ro",
                    "alpine",
                    "du", "-sb", "/source",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                return None
            # Output: "<bytes>\t/source\n"
            return int(result.stdout.strip().split()[0])
        except (subprocess.TimeoutExpired, ValueError, IndexError):
            return None


# ---------------------------------------------------------------------------
# WizardUI
# ---------------------------------------------------------------------------


class WizardUI:
    """Terminal-based wizard interface using rich for all console output."""

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.console = console  # global Console instance

    # -- Banner & phase helpers --------------------------------------------

    def banner(self):
        """Display welcome banner with version, platform info."""
        banner_text = Text()
        banner_text.append("Portainer ", style="bold cyan")
        banner_text.append("-> ", style="bold white")
        banner_text.append("Arcane ", style="bold green")
        banner_text.append("Migration Tool", style="bold white")
        banner_text.append(f"\nv{__version__}", style="dim")
        banner_text.append(
            f"  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim"
        )
        banner_text.append(f"  |  Platform: {self.config.platform_name}", style="dim")
        banner_text.append(
            "  |  Local Docker CLI: "
            + (
                "[green]available[/green]"
                if self.config.has_docker
                else "[yellow]not found[/yellow]"
            ),
            style="dim",
        )
        if self.config.log_file:
            banner_text.append(f"\nLog file: {self.config.log_file}", style="dim")
        if self.config.dry_run:
            banner_text.append("\n[DRY RUN MODE]", style="bold yellow")

        self.console.print(
            Panel(
                banner_text,
                title="[cyan]migrate.py[/cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    def _mode_badge(self) -> str:
        """Return a persistent [MODE] badge for phase headers so the user
        can't forget mid-session that dry-run or export-only is active."""
        if self.config.dry_run:
            return "[bold yellow][DRY RUN][/bold yellow] "
        if getattr(self.config, "strategy", "") == "export":
            return "[bold magenta][EXPORT-ONLY][/bold magenta] "
        return ""

    def phase_header(self, phase_num, total: int, title: str):
        """Display phase separator. phase_num can be int or string like '1.5'."""
        self.console.print()
        self.console.rule(
            f"{self._mode_badge()}"
            f"[bold blue]Phase {phase_num} of {total}: {title}[/bold blue]"
        )
        self.console.print()

    # -- Message helpers ---------------------------------------------------

    def success(self, msg: str):
        """Green checkmark prefix."""
        self.console.print(f"  [green]\u2714[/green] {msg}")

    def warning(self, msg: str):
        """Yellow triangle prefix."""
        self.console.print(f"  [yellow]\u26a0[/yellow] {msg}")

    def error(self, msg: str):
        """Red cross prefix."""
        self.console.print(f"  [red]\u2718[/red] {msg}")

    def show_migration_stopped(self, message: str):
        """Explain why the run halted and how to resume after the fix."""
        self.console.print()
        self.console.print(
            Panel(
                message,
                title="[bold red]Migration stopped[/bold red]",
                border_style="red",
            )
        )
        self.console.print()

    def info(self, msg: str):
        """Blue info prefix."""
        self.console.print(f"  [blue]\u2139[/blue] {msg}")

    def dry_run_msg(self, msg: str):
        """Display a dry-run notice."""
        self.console.print(f"  [yellow][DRY RUN][/yellow] Would {msg}")

    def diagnose_connection_error(self, label: str, url: str, exc: Exception):
        """Print a targeted hint for common connection failure modes so the
        user isn't left guessing whether the issue is DNS, port, scheme,
        SSL, or a bad API key. *label* is "Portainer" or "Arcane"."""
        self.error(f"Cannot connect to {label} ({url}): {exc}")
        msg = str(exc).lower()
        cls = exc.__class__.__name__
        if "ssl" in msg or "certificate" in msg:
            self.info(
                f"SSL/TLS error. If {label} uses a self-signed cert, "
                f"answer 'n' at 'Verify SSL?' on the connection prompt."
            )
        elif "nameresolution" in msg or "name or service not known" in msg \
                or "nodename nor servname" in msg:
            self.info(
                f"DNS resolution failed. Check the hostname in the {label} URL."
            )
        elif "connection refused" in msg:
            self.info(
                f"TCP connection refused. Check the port and that "
                f"{label} is running on that port."
            )
        elif "401" in msg or "unauthorized" in msg:
            self.info(
                f"Authentication rejected. Your {label} API key/token may "
                f"be invalid, expired, or lack permission."
            )
        elif "403" in msg or "forbidden" in msg:
            self.info(
                f"Access denied. Your {label} API key lacks permission "
                f"for this endpoint."
            )
        elif cls in ("Timeout", "ConnectTimeout", "ReadTimeout"):
            self.info(
                f"{label} did not respond within the timeout. Check that the "
                f"host is reachable and not overloaded."
            )
        elif url.startswith("http://"):
            self.info(
                f"URL uses http://. Most production {label} instances serve "
                f"on https:// — try changing the scheme."
            )

    # -- Edition panel -----------------------------------------------------

    def show_edition_panel(self, edition: str, version: str):
        """Show CE or EE panel after connection."""
        if edition == "EE":
            lines = [
                f"[bold]Portainer Business Edition {version}[/bold]\n",
                "[green]\u2714[/green] Webhooks available for migration",
                "[green]\u2714[/green] RBAC export available",
                "[green]\u2714[/green] Activity logs can be exported",
                "[green]\u2714[/green] Edge device detection enabled",
            ]
            self.console.print(
                Panel(
                    "\n".join(lines),
                    title="[green]Enterprise Edition Detected[/green]",
                    border_style="green",
                )
            )
        else:
            lines = [
                f"[bold]Portainer Community Edition {version}[/bold]\n",
                "[yellow]\u26a0[/yellow] Webhooks may not be available",
                "[yellow]\u26a0[/yellow] Teams and roles are not available",
                "[yellow]\u26a0[/yellow] Activity logs are not available",
                "",
                "[blue]\u2139[/blue] All core resources (stacks, containers, volumes, networks, registries, users) fully supported",
            ]
            self.console.print(
                Panel(
                    "\n".join(lines),
                    title="[cyan]Community Edition Detected[/cyan]",
                    border_style="cyan",
                )
            )

    # -- Connection prompts ------------------------------------------------

    def ask_portainer_connection(self):
        """Prompt for Portainer URL, API key, SSL verify. Store in config."""
        self.console.print("\n[bold cyan]Portainer Connection[/bold cyan]")
        self.config.portainer_url = Prompt.ask(
            "  [blue]Portainer URL[/blue]",
            default="https://localhost:9443/",
        )
        self.config.portainer_api_key = Prompt.ask(
            "  [blue]API Key[/blue]", password=True
        )
        self.config.portainer_ssl_verify = Confirm.ask(
            "  [blue]Verify SSL certificate?[/blue]",
            default=_ssl_verify_default(self.config.portainer_url),
        )

    def ask_arcane_connection(self):
        """Prompt for Arcane URL, auth method, credentials. Store in config."""
        self.console.print("\n[bold cyan]Arcane Connection[/bold cyan]")
        self.config.arcane_url = Prompt.ask(
            "  [blue]Arcane URL[/blue]",
            default="http://localhost:3552/",
        )
        auth_method = Prompt.ask(
            "  [blue]Auth method[/blue]",
            choices=["apikey", "login"],
            default="apikey",
        )
        if auth_method == "apikey":
            self.config.arcane_api_key = Prompt.ask(
                "  [blue]API Key[/blue]", password=True
            )
        else:
            self.config.arcane_username = Prompt.ask(
                "  [blue]Username[/blue]", default="admin"
            )
            self.config.arcane_password = Prompt.ask(
                "  [blue]Password[/blue]", password=True
            )

    # -- Selection prompts -------------------------------------------------

    def select_endpoint(self, endpoints: list) -> int:
        """Show numbered table of Portainer endpoints. Return endpoint ID."""
        if len(endpoints) == 1:
            ep = endpoints[0]
            self.info(
                f"Auto-selected endpoint: [bold]{ep.get('Name', 'unknown')}[/bold] (ID {ep['Id']})"
            )
            return ep["Id"]

        table = Table(title="Portainer Endpoints", box=box.ROUNDED)
        table.add_column("#", style="dim", width=4)
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("URL", style="dim")
        table.add_column("Status", style="green")

        for idx, ep in enumerate(endpoints, 1):
            status = "[green]Up[/green]" if ep.get("Status") == 1 else "[red]Down[/red]"
            table.add_row(
                str(idx),
                str(ep.get("Id", "")),
                ep.get("Name", ""),
                ep.get("URL", ""),
                status,
            )

        self.console.print(table)
        # Loop until a valid row is chosen. Previous implementation silently
        # clamped out-of-range input to the first/last row -- dangerous for
        # a destructive migration target.
        while True:
            choice = IntPrompt.ask("  [blue]Select endpoint #[/blue]", default=1)
            if 1 <= choice <= len(endpoints):
                return endpoints[choice - 1]["Id"]
            self.console.print(
                f"  [red]Please enter 1-{len(endpoints)}[/red]"
            )

    def select_arcane_environment(self, environments: list) -> str:
        """Show numbered table of Arcane environments. Return environment ID."""
        if len(environments) == 1:
            env = environments[0]
            env_id = str(env.get("id", env.get("Id", "")))
            self.info(
                f"Auto-selected environment: [bold]{env.get('name', env.get('Name', 'unknown'))}[/bold] (ID {env_id})"
            )
            return env_id

        table = Table(title="Arcane Environments", box=box.ROUNDED)
        table.add_column("#", style="dim", width=4)
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="bold")
        table.add_column("Status", style="green")

        for idx, env in enumerate(environments, 1):
            env_id = str(env.get("id", env.get("Id", "")))
            env_name = env.get("name", env.get("Name", ""))
            env_status = env.get("status", env.get("Status", "unknown"))
            table.add_row(str(idx), env_id, env_name, str(env_status))

        self.console.print(table)
        while True:
            choice = IntPrompt.ask(
                "  [blue]Select environment #[/blue]", default=1
            )
            if 1 <= choice <= len(environments):
                sel = environments[choice - 1]
                return str(sel.get("id", sel.get("Id", "")))
            self.console.print(
                f"  [red]Please enter 1-{len(environments)}[/red]"
            )

    # -- Discovery summary -------------------------------------------------

    def show_discovery_summary(self, discovery: dict, edition: str):
        """Show resource table and NOT migrated table."""
        # -- Discovered resources table --
        table = Table(title="Discovered Resources", box=box.ROUNDED)
        table.add_column("Resource", style="bold")
        table.add_column("Count", justify="right", style="cyan")
        table.add_column("Details", style="dim")
        table.add_column("Edition", style="dim")

        # Core resources (always shown)
        core_types = [
            "stacks", "standalone_containers", "volumes", "networks",
            "registries", "users", "custom_templates", "settings",
            "webhooks",
        ]
        for rtype in core_types:
            data = discovery.get(rtype, {})
            count = data.get("count", 0) if isinstance(data, dict) else len(data) if isinstance(data, list) else 0
            details = data.get("details", "") if isinstance(data, dict) else ""
            table.add_row(DISPLAY_NAMES.get(rtype, rtype), str(count), str(details), "CE+EE")

        # EE-only resources
        if edition == "EE":
            ee_types = [
                "teams", "team_memberships", "roles",
                "resource_controls", "edge_stacks", "activity_logs",
            ]
            for rtype in ee_types:
                data = discovery.get(rtype, {})
                count = data.get("count", 0) if isinstance(data, dict) else len(data) if isinstance(data, list) else 0
                details = data.get("details", "") if isinstance(data, dict) else ""
                table.add_row(DISPLAY_NAMES.get(rtype, rtype), str(count), str(details), "EE only")

        self.console.print(table)

        # -- NOT migrated table --
        not_migrated = Table(title="NOT Migrated (reference only)", box=box.ROUNDED)
        not_migrated.add_column("Resource", style="yellow")
        not_migrated.add_column("Reason", style="dim")
        not_migrated.add_column("Edition", style="dim")

        not_migrated.add_row("Endpoint Groups", "No equivalent in Arcane", "CE+EE")
        not_migrated.add_row("SSL Certificates", "Managed differently in Arcane", "CE+EE")

        if edition == "EE":
            ee_not_migrated = [
                ("Teams & Memberships", "EE RBAC -- exported for reference"),
                ("Granular Roles", "EE RBAC -- exported for reference"),
                ("Resource ACLs", "EE RBAC -- exported for reference"),
                ("Edge Groups/Jobs/Stacks", "Edge compute -- exported for reference"),
                ("Activity Logs", "Audit data -- exported for reference"),
            ]
            for name, reason in ee_not_migrated:
                not_migrated.add_row(name, reason, "EE only")

        self.console.print(not_migrated)

    # -- Strategy & scope --------------------------------------------------

    def ask_strategy(self):
        """Prompt: export/live, dry-run toggle, backup dir. Store in config."""
        self.console.print("\n[bold cyan]Migration Strategy[/bold cyan]")
        self.config.strategy = Prompt.ask(
            "  [blue]Strategy[/blue] (export = files only, live = export + import)",
            choices=["export", "live"],
            default=self.config.strategy or "export",
        )
        self.config.dry_run = Confirm.ask(
            "  [blue]Enable dry-run mode?[/blue] (simulate without changes)",
            default=self.config.dry_run,
        )
        self.config.backup_dir = Prompt.ask(
            "  [blue]Backup / export directory[/blue]",
            default=self.config.backup_dir,
        )

    def ask_scope_confirmation(self, discovery: dict, edition: str) -> bool:
        """Ask 'Migrate ALL?' If no, show per-type selection. Return True if any selected."""
        migrate_all = Confirm.ask(
            "\n  [blue]Migrate ALL discovered resources?[/blue]", default=True
        )

        core_types = [
            "stacks", "standalone_containers", "volumes", "networks",
            "registries", "users", "custom_templates", "settings",
            "webhooks",
        ]
        ee_types = [
            "teams", "team_memberships", "roles",
            "resource_controls", "edge_stacks", "activity_logs",
        ]

        if migrate_all:
            self.config.selected_items = {
                rt: [] for rt in core_types
            }
            if edition == "EE":
                for rt in ee_types:
                    self.config.selected_items[rt] = []
            return True

        # Per-type selection
        self.config.selected_items = {}

        self.console.print("\n  [bold]Core resources:[/bold]")
        for rt in core_types:
            data = discovery.get(rt, {})
            count = data.get("count", 0) if isinstance(data, dict) else len(data) if isinstance(data, list) else 0
            display = DISPLAY_NAMES.get(rt, rt)
            if count > 0 and Confirm.ask(
                f"    [blue]Migrate {display}?[/blue] ({count} found)",
                default=True,
            ):
                self.config.selected_items[rt] = []

        if edition == "EE":
            self.console.print("\n  [bold]EE-only resources:[/bold]")
            for rt in ee_types:
                data = discovery.get(rt, {})
                count = data.get("count", 0) if isinstance(data, dict) else len(data) if isinstance(data, list) else 0
                display = DISPLAY_NAMES.get(rt, rt)
                if count > 0 and Confirm.ask(
                    f"    [blue]Migrate {display}?[/blue] ({count} found)",
                    default=True,
                ):
                    self.config.selected_items[rt] = []

        return bool(self.config.selected_items)

    # -- Preflight ---------------------------------------------------------

    def show_preflight_results(self, results: list) -> bool:
        """Show preflight table. If any FAIL, ask continue? Return bool."""
        table = Table(title="Preflight Checks", box=box.ROUNDED)
        table.add_column("Check", style="bold")
        table.add_column("Result", justify="center")
        table.add_column("Details", style="dim")

        has_fail = False
        for r in results:
            status = r.get("status", "pass")
            if status == "pass":
                styled_status = "[green]PASS[/green]"
            elif status == "warn":
                styled_status = "[yellow]WARN[/yellow]"
            else:
                styled_status = "[red]FAIL[/red]"
                has_fail = True
            table.add_row(r.get("name", ""), styled_status, r.get("details", ""))

        self.console.print(table)

        if has_fail:
            return Confirm.ask(
                "  [yellow]Some checks failed. Continue anyway?[/yellow]",
                default=False,
            )
        return True

    # -- Migration plan ----------------------------------------------------

    def show_migration_plan(self, config: Config):
        """Show Panel with migration plan details."""
        lines = [
            f"[bold]Strategy:[/bold]       {config.strategy}",
            f"[bold]Dry run:[/bold]        {'[yellow]Yes[/yellow]' if config.dry_run else '[green]No[/green]'}",
            f"[bold]Backup dir:[/bold]     [dim]{config.backup_dir}[/dim]",
            f"[bold]Local Docker CLI:[/bold] {'[green]available[/green]' if config.has_docker else '[yellow]not available[/yellow]'} (volume backup on this machine)",
            "",
            "[bold]Execution order:[/bold]",
        ]

        execution_order = [
            "1. Registries",
            "2. Networks",
            "3. Volumes (with backup if docker available)",
            "4. Stacks / Compose projects",
            "5. Standalone containers",
            "6. Custom templates",
            "7. Users",
            "8. Webhooks (EE or if available)",
            "9. Settings",
        ]
        for step in execution_order:
            lines.append(f"  {step}")

        self.console.print(
            Panel(
                "\n".join(lines),
                title="[cyan]Migration Plan[/cyan]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    # -- Progress ----------------------------------------------------------

    def create_progress(self) -> Progress:
        """Return configured Progress with spinner + text + bar + percentage."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        )

    # -- Final report ------------------------------------------------------

    def show_final_report(self, report: dict, edition: str):
        """Show final migration report with summary, errors, and action items."""
        self.console.print()
        self.console.rule("[bold cyan]Migration Report[/bold cyan]")
        self.console.print()

        # 1. Summary table
        summary = Table(title="Migration Summary", box=box.ROUNDED)
        summary.add_column("Resource", style="bold")
        summary.add_column("Migrated", justify="right", style="green")
        summary.add_column("Failed", justify="right", style="red")
        summary.add_column("Skipped", justify="right", style="yellow")
        summary.add_column("Edition", style="dim")

        resources = report.get("resources", {})
        for rtype, data in resources.items():
            ed = "EE only" if rtype in (
                "webhooks", "teams", "team_memberships", "roles",
                "resource_controls", "edge_stacks",
            ) else "CE+EE"
            summary.add_row(
                rtype.replace("_", " ").title(),
                str(data.get("migrated", 0)),
                str(data.get("failed", 0)),
                str(data.get("skipped", 0)),
                ed,
            )

        self.console.print(summary)

        # 2. EE Reference Exports table
        ee_ref = report.get("ee_reference", {})
        if edition == "EE" and ee_ref:
            self.console.print()
            ee_table = Table(title="EE Reference Exports", box=box.ROUNDED)
            ee_table.add_column("Resource", style="bold")
            ee_table.add_column("Count", justify="right", style="cyan")
            ee_table.add_column("File", style="dim")

            for rtype, data in ee_ref.items():
                ee_table.add_row(
                    rtype.replace("_", " ").title(),
                    str(data.get("count", 0)),
                    data.get("file_path", ""),
                )

            self.console.print(ee_table)

        # 3. Errors list
        errors = report.get("errors", [])
        if errors:
            self.console.print()
            self.console.print("[bold red]Errors:[/bold red]")
            for err in errors:
                self.console.print(
                    f"  [red]\u2718[/red] [{err.get('resource_type', '')}] "
                    f"{err.get('name', '')}: {err.get('error', '')}"
                )

        # 4. Action items
        action_items = report.get("action_items", [])
        if not action_items:
            # Provide sensible defaults
            action_items = []
        # Always suggest common post-migration steps
        default_actions = [
            "Reset user passwords in Arcane (passwords cannot be migrated)",
            "Manually map webhooks if URLs differ between systems",
            "Review RBAC / role assignments in Arcane",
            "Review and adjust environment settings in Arcane",
        ]
        all_actions = list(action_items) + [
            a for a in default_actions if a not in action_items
        ]

        if all_actions:
            self.console.print()
            self.console.print("[bold yellow]Action Items:[/bold yellow]")
            for item in all_actions:
                self.console.print(f"  [yellow]\u26a0[/yellow] {item}")

        # 5. File paths
        config = report.get("config", {})
        backup_dir = config.get("backup_dir", "./migration_export")
        self.console.print()
        self.console.print("[bold cyan]Output Files:[/bold cyan]")
        file_paths = [
            ("Report", f"{backup_dir}/migration_report.json"),
            ("Rollback script", f"{backup_dir}/rollback.sh"),
            ("Log", config.get("log_file", "")),
            ("Backup directory", backup_dir),
        ]
        if edition == "EE":
            file_paths.append(("EE reference", f"{backup_dir}/ee_reference/"))

        for label, path in file_paths:
            if path:
                self.console.print(f"  [dim]{label}:[/dim] {path}")

        self.console.print()

    def show_rollback_instructions(self, rollback_file: str):
        """Explain that rollback.sh was written and has not been executed.

        The script ships with a placeholder API key so no credentials are
        written to disk. It deletes only resources this run created.
        """
        self.info(f"Rollback script written (not run): {rollback_file}")
        self.console.print(
            "\n[bold yellow]The rollback script was not executed.[/bold yellow]\n"
            f"  1. Edit [cyan]{rollback_file}[/cyan] and replace "
            "[magenta]YOUR_API_KEY_HERE[/magenta] with your Arcane API key.\n"
            "  2. Review the DELETE commands. They remove resources this run created.\n"
            f"  3. Run it only if you want to undo those creates: "
            f"[cyan]bash {rollback_file}[/cyan]"
        )


# ---------------------------------------------------------------------------
# ReportGenerator
# ---------------------------------------------------------------------------


class ReportGenerator:
    """Tracks migration results and generates output files."""

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.report: Dict[str, Any] = {
            "version": __version__,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "portainer_edition": config.portainer_edition,
            "config": config.to_dict(),
            "resources": {},
            "ee_reference": {},
            "errors": [],
            "action_items": [],
            "completed_at": None,
        }
        self.rollback_commands: List[Dict[str, str]] = []

    def _ensure_resource(self, resource_type: str):
        """Ensure the resource_type key exists in the report resources dict."""
        if resource_type not in self.report["resources"]:
            self.report["resources"][resource_type] = {
                "migrated": 0,
                "failed": 0,
                "skipped": 0,
                "items": [],
            }

    def record_success(
        self,
        resource_type: str,
        name: str,
        source_id: Any,
        target_id: Any,
        status: str = "migrated",
    ):
        """Track a successful migration.

        ``status="adopted"`` means the resource was already on the target
        engine and was left in place. It still counts as migrated, and no
        rollback command is recorded for it.
        """
        self._ensure_resource(resource_type)
        self.report["resources"][resource_type]["migrated"] += 1
        self.report["resources"][resource_type]["items"].append({
            "name": name,
            "source_id": source_id,
            "target_id": target_id,
            "status": status,
        })
        verb = "Adopted" if status == "adopted" else "Migrated"
        self.logger.info(
            "%s %s: %s (source=%s -> target=%s)",
            verb, resource_type, name, source_id, target_id,
        )

    def record_failure(self, resource_type: str, name: str, error: str):
        """Track a failed migration."""
        self._ensure_resource(resource_type)
        self.report["resources"][resource_type]["failed"] += 1
        self.report["errors"].append({
            "resource_type": resource_type,
            "name": name,
            "error": str(error),
        })
        self.logger.error("Failed %s: %s -- %s", resource_type, name, error)

    def record_skip(self, resource_type: str, name: str, reason: str):
        """Track a skipped resource."""
        self._ensure_resource(resource_type)
        self.report["resources"][resource_type]["skipped"] += 1
        self.logger.info("Skipped %s: %s -- %s", resource_type, name, reason)

    def record_ee_export(self, resource_type: str, count: int, file_path: str):
        """Track an EE-only reference export."""
        self.report["ee_reference"][resource_type] = {
            "count": count,
            "file_path": file_path,
        }
        self.logger.info("EE export %s: %d items -> %s", resource_type, count, file_path)

    def add_action_item(self, message: str):
        """Append a post-migration action item."""
        self.report["action_items"].append(message)

    def add_rollback(self, method: str, url: str, description: str):
        """Append a rollback command."""
        self.rollback_commands.append({
            "method": method,
            "url": url,
            "description": description,
        })

    def save_report(self) -> str:
        """Save JSON report to migration_export/migration_report.json. Return file path."""
        self.report["completed_at"] = datetime.now(timezone.utc).isoformat()
        report_dir = self.config.backup_dir
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, "migration_report.json")
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(self.report, fh, indent=2, default=str)
        self.logger.info("Migration report saved to %s", report_path)
        return report_path

    def save_rollback_script(self) -> Optional[str]:
        """Generate rollback.sh with curl commands (reversed order). Return path or None."""
        if not self.rollback_commands:
            return None

        report_dir = self.config.backup_dir
        os.makedirs(report_dir, exist_ok=True)
        script_path = os.path.join(report_dir, "rollback.sh")

        api_key = "YOUR_API_KEY_HERE"  # Never embed real credentials in scripts
        lines = [
            "#!/usr/bin/env bash",
            "# Rollback script -- generated by migrate.py",
            f"# Generated: {datetime.now(timezone.utc).isoformat()}",
            "# Review carefully before executing!",
            "",
            'set -euo pipefail',
            "",
            f'API_KEY="{api_key}"',
            "",
        ]

        for cmd in reversed(self.rollback_commands):
            lines.append(f"# {cmd['description']}")
            lines.append(f'curl -X {cmd["method"]} {shlex.quote(cmd["url"])} -H "X-API-Key: $API_KEY"')
            lines.append("")

        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

        os.chmod(script_path, 0o700)  # Owner-only: script contains sensitive URLs
        self.logger.info("Rollback script saved to %s", script_path)
        return script_path


# ---------------------------------------------------------------------------
# MigrationEngine
# ---------------------------------------------------------------------------


class MigrationEngine:
    """Orchestrates the full migration with checkpoint/resume and CE/EE branching."""

    PHASE_TOTAL = 6

    PHASES = [
        "portainer_backup", "registries", "git_repos", "networks", "volumes",
        "stacks", "gitops_syncs", "containers", "templates", "users",
        "webhooks", "ee_rbac_export", "ee_audit_export",
    ]

    REGISTRY_TYPE_MAP = {
        1: "custom", 2: "custom", 3: "custom", 4: "custom",
        5: "custom", 6: "dockerhub", 7: "ecr", 8: "custom",
    }

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.portainer = PortainerClient(config, logger)
        self.arcane = ArcaneClient(config, logger)
        self.docker = DockerLocal(config, logger)
        self.ui = WizardUI(config, logger)
        self.report = ReportGenerator(config, logger)
        self._git_repo_map: Dict[str, str] = {}  # stack_id -> arcane_repo_id
        self._ee_exported: bool = False
        self.state = self._load_state()
        self.discovery: Dict[str, Any] = {}
        # Filled by _refresh_target_engine once both APIs are connected.
        # engine_kind / engine_info are the Arcane side. source_* is Portainer.
        self.engine_kind: str = ""
        self.engine_info: Dict[str, Any] = {}
        self.source_engine_kind: str = ""
        self.source_engine_info: Dict[str, Any] = {}
        self.same_engine: bool = False
        self.engine_proven: bool = False
        self.engine_match_reason: str = ""
        # None until the user answers. False means proven, but they declined.
        # A bool in state["adopt_in_place"] is that answer from a previous run.
        self._adopt_in_place: Optional[bool] = None
        self._target_names: Dict[str, set] = {
            "containers": set(),
            "networks": set(),
            "volumes": set(),
            "projects": set(),
        }
        self._engine_noted: bool = False
        self._engines_announced: bool = False

    # ------------------------------------------------------------------
    # Task 7: Checkpoint & State Management
    # ------------------------------------------------------------------

    def _load_state(self) -> dict:
        """Load from checkpoint file if exists and config_hash matches.

        Otherwise return fresh state with all phases pending. A corrupt
        checkpoint is treated as fatal rather than silently discarded: the
        combination of non-atomic writes + silent reset would cause every
        already-migrated item to be re-migrated on the next resume, creating
        duplicates on Arcane.
        """
        cp = self.config.checkpoint_file
        if os.path.isfile(cp):
            try:
                with open(cp, "r", encoding="utf-8") as fh:
                    saved = json.load(fh)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Checkpoint file {cp} is corrupt ({exc}). "
                    f"Inspect the file manually; if you intend to start "
                    f"fresh, delete it and re-run."
                ) from exc
            except OSError as exc:
                raise RuntimeError(
                    f"Could not read checkpoint {cp}: {exc}"
                ) from exc

            if saved.get("config_hash") == self.config.config_hash():
                self.logger.info("Resuming from checkpoint: %s", cp)
                self._git_repo_map = saved.get("git_repo_map", {})
                return saved
            self.logger.warning(
                "Checkpoint config_hash mismatch -- starting fresh"
            )

        # Fresh state
        return {
            "config_hash": self.config.config_hash(),
            "phases": {phase: "pending" for phase in self.PHASES},
            "migrated_items": {phase: [] for phase in self.PHASES},
        }

    def _attach_checkpoint(self) -> None:
        """Load the checkpoint once the connection identity is known.

        The engine is built before the wizard asks for URLs, so the load in
        ``__init__`` compares the file to an empty connection and misses.
        Saving that empty state would replace the file. When the Portainer
        endpoint and Arcane environment are known, reload a file whose hash
        matches so a resume keeps migrated items and saved answers.
        """
        current = self.config.config_hash()
        cp = self.config.checkpoint_file
        if os.path.isfile(cp):
            try:
                with open(cp, "r", encoding="utf-8") as fh:
                    saved = json.load(fh)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Checkpoint file {cp} is corrupt ({exc}). "
                    f"Inspect the file manually; if you intend to start "
                    f"fresh, delete it and re-run."
                ) from exc
            except OSError as exc:
                raise RuntimeError(
                    f"Could not read checkpoint {cp}: {exc}"
                ) from exc
            if isinstance(saved, dict) and saved.get("config_hash") == current:
                self.state = saved
                self._git_repo_map = saved.get("git_repo_map", {}) or {}
                self.logger.info("Checkpoint matches this connection: %s", cp)
                return
            self.logger.warning(
                "Checkpoint config_hash mismatch -- starting fresh"
            )
        self.state["config_hash"] = current
        self._save_state()

    def _save_state(self):
        """Atomically write state to checkpoint file.

        A naive open("w") + json.dump is not atomic: an interrupt between
        truncate and flush leaves a zero-byte or partial file, and the
        next ``--resume`` would then re-run every already-migrated item.
        Write to a sibling temp file, fsync, and os.replace into place.
        """
        self.state["git_repo_map"] = self._git_repo_map
        cp = self.config.checkpoint_file
        tmp = f"{cp}.tmp.{os.getpid()}"
        try:
            try:
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(self.state, fh, indent=2, default=str)
                    fh.flush()
                    try:
                        os.fsync(fh.fileno())
                    except OSError:
                        pass  # fsync not supported (e.g., some network FS)
                os.replace(tmp, cp)
            except OSError as exc:
                self.logger.warning("Could not save checkpoint: %s", exc)
        finally:
            # Always clean up the temp file — e.g. if json.dump raises
            # TypeError on an unserializable value, the .tmp would otherwise
            # linger and accumulate across runs.
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def _phase_status(self, phase: str) -> str:
        """Return status of a phase from state."""
        return self.state.get("phases", {}).get(phase, "pending")

    def _mark_phase(self, phase: str, status: str):
        """Update phase status and save."""
        self.state.setdefault("phases", {})[phase] = status
        self._save_state()

    def _is_migrated(self, phase: str, item_id: str) -> bool:
        """Check if item already migrated (for resume)."""
        migrated = self.state.get("migrated_items", {}).get(phase, [])
        return str(item_id) in migrated

    def _record_migrated(self, phase: str, item_id: str):
        """Add item to migrated list and save."""
        self.state.setdefault("migrated_items", {}).setdefault(phase, [])
        item_str = str(item_id)
        if item_str not in self.state["migrated_items"][phase]:
            self.state["migrated_items"][phase].append(item_str)
        self._save_state()

    def _should_include(self, resource_type: str) -> bool:
        """Check if resource type is in user's scope selection.

        An empty ``selected_items`` dict means nothing was selected (exclude all).
        If the key is present, the resource type is included.  An empty list
        value for the key means *all items* of that type are selected.
        """
        return resource_type in self.config.selected_items

    def _management_candidate_lines(self) -> List[str]:
        """Portainer and Arcane apps still in scope, for the skip prompt."""
        lines: List[str] = []
        seen = set()

        def add(kind: str, name: str, image: str = "") -> None:
            app = management_app(name, image)
            if not app or not name:
                return
            label = f"{app} {kind} '{name}'"
            if label not in seen:
                seen.add(label)
                lines.append(label)

        if self._should_include("stacks"):
            for stack in self.discovery.get("stacks", {}).get("data", []) or []:
                if isinstance(stack, dict):
                    add("stack", str(stack.get("Name") or ""))
        if self._should_include("standalone_containers"):
            for container in (
                self.discovery.get("standalone_containers", {}).get("data", [])
                or []
            ):
                if not isinstance(container, dict):
                    continue
                add(
                    "container",
                    self._resource_name(
                        container, "Names", "names", "Name", "name"
                    ),
                    container_image_ref(container),
                )
        return lines

    def _skip_management_apps(self) -> bool:
        """True when Portainer and Arcane's own apps should be left out.

        Asked once. The default is to skip. The answer is stored in the
        checkpoint so a resume does not ask again and does not flip the choice.
        """
        decided = self.state.get("skip_management_containers")
        if isinstance(decided, bool):
            return decided
        found = self._management_candidate_lines()
        if not found:
            return False
        self.ui.info(
            "These are the management apps, not workloads: " + ", ".join(found)
        )
        try:
            skip = Confirm.ask(
                "  [blue]Skip Portainer and Arcane's own containers?[/blue]",
                default=True,
            )
        except EOFError:
            skip = True
            self.ui.warning(
                "No answer. Portainer and Arcane's own containers will be skipped."
            )
        self.state["skip_management_containers"] = skip
        self._save_state()
        if skip:
            self.ui.info(
                "Portainer and Arcane's own containers will be skipped."
            )
        else:
            self.ui.info(
                "Portainer and Arcane's own containers will be migrated."
            )
        return skip

    def _leave_management_app(
        self,
        resource_type: str,
        name: str,
        item_id: str,
        phase: str,
        image: str = "",
    ) -> bool:
        """Skip one Portainer or Arcane app. No create and no rollback delete."""
        app = management_app(name, image)
        if not app or not self._skip_management_apps():
            return False
        self.report.record_skip(
            resource_type,
            name,
            f"{app}'s own app, skipped",
        )
        self.ui.info(f"Skipping {app} '{name}'")
        self._record_migrated(phase, item_id)
        return True

    def _is_ee(self) -> bool:
        """Shorthand for Enterprise Edition check."""
        return self.config.portainer_edition == "EE"

    def _execute_or_log(
        self,
        action: str,
        api_call: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Dry-run wrapper: if dry_run, log and return stub; else call api_call."""
        if self.config.dry_run:
            self.ui.dry_run_msg(action)
            # Redact registry passwords / user passwords / git tokens / AWS
            # keys before they reach the debug log file on disk.
            self.logger.debug(
                "[DRY RUN] %s args=%s kwargs=%s",
                action,
                _redact_sensitive(args),
                _redact_sensitive(kwargs),
            )
            return {"dry_run": True, "action": action}
        return api_call(*args, **kwargs)

    def _stop_if_projects_directory_blocked(self, exc: BaseException) -> None:
        """Halt the run when Arcane cannot create project directories.

        A projects-directory permission error is a property of the Arcane
        host. The next stack fails the same way, so the remaining phases
        are not attempted. The failed item is already recorded by the caller.
        """
        stopped = projects_directory_block(exc)
        if stopped is None:
            return
        self.report.add_action_item(stopped.action_item)
        self.ui.show_migration_stopped(str(stopped))
        raise stopped

    # ------------------------------------------------------------------
    # Import from directory (--import-dir)
    # ------------------------------------------------------------------

    def _import_from_directory(self, import_dir: str) -> dict:
        """Rebuild discovery dict from a previously exported migration directory.

        Reads manifest.json and the individual JSON/YAML files produced by
        ``--export-only`` and returns a discovery dict compatible with
        ``self.discovery``.
        """
        base = Path(import_dir)
        if not base.is_dir():
            raise FileNotFoundError(f"Import directory does not exist: {import_dir}")

        # ---- Manifest ----
        manifest_path = base / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(
                f"No manifest.json found in {import_dir}. "
                "Is this a valid migration export directory?"
            )
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)

        self.ui.info(
            f"Import manifest: exported at {manifest.get('exported_at', 'unknown')}, "
            f"tool v{manifest.get('tool_version', '?')}, "
            f"Portainer {manifest.get('portainer_edition', '?')} "
            f"v{manifest.get('portainer_version', '?')}"
        )

        # Carry forward edition info so _is_ee() works
        self.config.portainer_edition = manifest.get("portainer_edition", "CE")
        self.config.portainer_version = manifest.get("portainer_version", "")
        self._remember_source_engine(manifest.get("source_engine"))

        counts = manifest.get("counts", {})
        discovery: Dict[str, Any] = {}

        def _load_json(filepath: Path) -> Any:
            """Load JSON from filepath. Return [] if missing or malformed
            (surfaces the filename in a warning so the user can fix it)."""
            if not filepath.is_file():
                self.logger.debug("Import file not found: %s", filepath)
                return []
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                self.ui.warning(
                    f"Skipping malformed import file {filepath}: {exc}"
                )
                self.logger.error("Malformed import file %s: %s", filepath, exc)
                return []

        # ---- Registries ----
        registries = _load_json(base / "registries" / "registries.json")
        discovery["registries"] = {
            "count": len(registries),
            "details": "",
            "edition": "CE + EE",
            "data": registries,
        }

        # ---- Stacks ----
        stacks_dir = base / "stacks"
        stacks_data: list = []
        if stacks_dir.is_dir():
            for stack_subdir in sorted(stacks_dir.iterdir()):
                if not stack_subdir.is_dir():
                    continue
                metadata_path = stack_subdir / "metadata.json"
                if metadata_path.is_file():
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        stack_meta = json.load(f)
                    stacks_data.append(stack_meta)
                else:
                    # Minimal entry from directory name
                    stacks_data.append({"Name": stack_subdir.name})

        git_stacks = [s for s in stacks_data if s.get("GitConfig")]
        file_stacks = [s for s in stacks_data if not s.get("GitConfig")]
        discovery["stacks"] = {
            "count": len(stacks_data),
            "details": f"{len(file_stacks)} file-based, {len(git_stacks)} git-based",
            "edition": "CE + EE",
            "data": stacks_data,
        }

        # ---- Standalone Containers ----
        containers = _load_json(base / "containers" / "standalone.json")
        discovery["standalone_containers"] = {
            "count": len(containers),
            "details": "(imported from export)",
            "edition": "CE + EE",
            "data": containers,
        }

        # ---- Networks ----
        networks = _load_json(base / "networks" / "networks.json")
        discovery["networks"] = {
            "count": len(networks),
            "details": "",
            "edition": "CE + EE",
            "data": networks,
        }

        # ---- Volumes ----
        volumes = _load_json(base / "volumes" / "volumes.json")
        discovery["volumes"] = {
            "count": len(volumes),
            "details": "",
            "edition": "CE + EE",
            "data": volumes,
        }

        # ---- Custom Templates ----
        templates = _load_json(base / "templates" / "custom_templates.json")
        discovery["custom_templates"] = {
            "count": len(templates),
            "details": "",
            "edition": "CE + EE",
            "data": templates,
        }

        # ---- Users ----
        users = _load_json(base / "users" / "users.json")
        discovery["users"] = {
            "count": len(users),
            "details": "",
            "edition": "CE + EE",
            "data": users,
        }

        # ---- Webhooks ----
        webhooks = _load_json(base / "webhooks" / "webhooks.json")
        if webhooks:
            discovery["webhooks"] = {
                "count": len(webhooks),
                "details": "",
                "edition": self.config.portainer_edition,
                "data": webhooks,
            }

        # ---- Settings ----
        settings = _load_json(base / "settings" / "portainer_settings.json")
        if isinstance(settings, dict):
            discovery["settings"] = {
                "count": 1,
                "details": "Imported from export",
                "edition": "CE + EE",
                "data": settings,
            }
        elif isinstance(settings, list) and settings:
            discovery["settings"] = {
                "count": 1,
                "details": "Imported from export",
                "edition": "CE + EE",
                "data": settings[0] if len(settings) == 1 else settings,
            }

        # ---- Images placeholder (not exported) ----
        discovery["images"] = {
            "count": 0,
            "details": "Not available in import mode",
            "edition": "CE + EE",
            "data": [],
        }

        # ---- EE reference data (if present) ----
        ee_dir = base / "ee_reference"
        if ee_dir.is_dir():
            for rtype, filename in [
                ("teams", "teams.json"),
                ("roles", "roles.json"),
                ("edge_stacks", "edge_stacks.json"),
            ]:
                data = _load_json(ee_dir / filename)
                if data:
                    discovery[rtype] = {
                        "count": len(data),
                        "details": "",
                        "edition": "EE",
                        "data": data,
                    }

        self.discovery = discovery

        # Show summary
        total_resources = sum(
            d.get("count", 0) if isinstance(d, dict) else 0
            for d in discovery.values()
        )
        self.ui.success(
            f"Loaded {total_resources} resources from {import_dir}"
        )
        self.ui.show_discovery_summary(discovery, self.config.portainer_edition)

        return discovery

    # ------------------------------------------------------------------
    # Task 8: Discovery Phase
    # ------------------------------------------------------------------

    def discover(self) -> dict:
        """Enumerate all Portainer resources. Returns discovery dict."""
        self.ui.phase_header(2, self.PHASE_TOTAL, "Discovery & Audit")
        discovery: Dict[str, Any] = {}

        # Count items to discover: 9 for CE, 13 for EE (includes settings)
        total_items = 13 if self._is_ee() else 9

        def _discover_one(rtype: str, edition: str, loader, transform):
            """Run *loader()* → *transform(raw)* and drop the result into
            discovery[rtype]. On failure, record the error and continue so a
            single flaky endpoint doesn't abort the whole discovery phase.

            *transform* receives the raw response and returns the discovery
            dict body (without "edition" — added here).
            """
            try:
                raw = loader()
                body = transform(raw)
            except Exception as exc:
                self.logger.error("Discovery failed for %s: %s", rtype, exc)
                self.ui.warning(f"{rtype} discovery failed: {exc}")
                discovery[rtype] = {
                    "count": 0,
                    "details": f"[red]discovery failed: {exc}[/red]",
                    "edition": edition,
                    "data": [],
                    "error": str(exc),
                }
                return
            body.setdefault("edition", edition)
            discovery[rtype] = body

        with self.ui.create_progress() as progress:
            task = progress.add_task("Discovering resources...", total=total_items)

            # --- CE + EE resources ---

            def _stacks_transform(stacks):
                compose = [s for s in stacks if s.get("Type") == 2]
                git = [s for s in compose if s.get("GitConfig")]
                file_ = [s for s in compose if not s.get("GitConfig")]
                return {
                    "count": len(compose),
                    "details": f"{len(file_)} file-based, {len(git)} git-based",
                    "data": compose,
                }
            _discover_one("stacks", "CE + EE",
                          self.portainer.list_stacks, _stacks_transform)
            progress.advance(task)

            def _containers_transform(containers):
                standalone = [
                    c for c in containers
                    if not c.get("Labels", {}).get("com.docker.compose.project")
                ]
                compose_count = len(containers) - len(standalone)
                return {
                    "count": len(standalone),
                    "details": f"({compose_count} compose-managed excluded)",
                    "data": standalone,
                }
            _discover_one(
                "standalone_containers", "CE + EE",
                lambda: self.portainer.list_containers(all_containers=True),
                _containers_transform,
            )
            progress.advance(task)

            def _images_transform(images):
                total_size = sum(img.get("Size", 0) for img in images)
                return {
                    "count": len(images),
                    "details": f"{total_size / (1024**3):.1f} GB total",
                    "data": images,
                }
            _discover_one("images", "CE + EE",
                          self.portainer.list_images, _images_transform)
            progress.advance(task)

            def _volumes_transform(vol_data):
                volumes = (vol_data or {}).get("Volumes", []) or []
                return {"count": len(volumes), "details": "", "data": volumes}
            _discover_one("volumes", "CE + EE",
                          self.portainer.list_volumes, _volumes_transform)
            progress.advance(task)

            def _networks_transform(networks):
                default_nets = {
                    "bridge", "host", "none", "ingress", "docker_gwbridge",
                }
                user_nets = [
                    n for n in networks if n.get("Name") not in default_nets
                ]
                return {
                    "count": len(user_nets),
                    "details": f"({len(networks) - len(user_nets)} default excluded)",
                    "data": user_nets,
                }
            _discover_one("networks", "CE + EE",
                          self.portainer.list_networks, _networks_transform)
            progress.advance(task)

            def _registries_transform(regs):
                return {
                    "count": len(regs),
                    "details": ", ".join(
                        r.get("Name", "")[:20] for r in regs[:3]
                    ),
                    "data": regs,
                }
            _discover_one("registries", "CE + EE",
                          self.portainer.list_registries, _registries_transform)
            progress.advance(task)

            def _templates_transform(templates):
                return {
                    "count": len(templates),
                    "details": ", ".join(
                        t.get("Title", "")[:20] for t in templates[:3]
                    ),
                    "data": templates,
                }
            _discover_one("custom_templates", "CE + EE",
                          self.portainer.list_custom_templates, _templates_transform)
            progress.advance(task)

            def _users_transform(users):
                return {
                    "count": len(users),
                    "details": ", ".join(u.get("Username", "") for u in users[:4]),
                    "data": users,
                }
            _discover_one("users", "CE + EE",
                          self.portainer.list_users, _users_transform)
            progress.advance(task)

            # --- EE-only resources ---
            if self._is_ee():
                _discover_one("webhooks", "EE", self.portainer.list_webhooks,
                              lambda w: {"count": len(w), "details": "", "data": w})
                progress.advance(task)

                _discover_one("teams", "EE", self.portainer.list_teams,
                              lambda t: {
                                  "count": len(t),
                                  "details": ", ".join(
                                      x.get("Name", "") for x in t[:3]
                                  ),
                                  "data": t,
                              })
                progress.advance(task)

                _discover_one("roles", "EE", self.portainer.list_roles,
                              lambda r: {"count": len(r), "details": "", "data": r})
                progress.advance(task)

                _discover_one("edge_stacks", "EE", self.portainer.list_edge_stacks,
                              lambda e: {
                                  "count": len(e),
                                  "details": "(detected)" if e else "(none)",
                                  "data": e,
                              })
                progress.advance(task)
            else:
                # CE: attempt webhooks gracefully
                try:
                    webhooks = self.portainer.list_webhooks()
                    if webhooks:
                        discovery["webhooks"] = {
                            "count": len(webhooks),
                            "details": "",
                            "edition": "CE",
                            "data": webhooks,
                        }
                except Exception as exc:
                    self.logger.warning("CE webhook probe failed: %s", exc)

            # Settings (always export as reference)
            _discover_one("settings", "CE + EE",
                          self.portainer.get_settings,
                          lambda s: {
                              "count": 1,
                              "details": "Exported for reference",
                              "data": s,
                          })
            progress.advance(task)

        self.discovery = discovery
        self.ui.show_discovery_summary(discovery, self.config.portainer_edition)
        return discovery

    # ------------------------------------------------------------------
    # Task 9: Data Transformation Helpers
    # ------------------------------------------------------------------

    def _transform_registry(self, reg: dict) -> dict:
        """Map Portainer registry to Arcane CreateContainerRegistryRequest.

        Arcane's CreateContainerRegistryRequest marks awsAccessKeyId,
        awsSecretAccessKey, and awsRegion as REQUIRED for every registry
        type — not just ECR. We therefore send them on every payload,
        populated from Portainer's Ecr block when the registry is ECR and
        as empty strings otherwise so the schema's required-fields
        constraint is satisfied.

        Arcane has no ``name`` field for registries; ``description`` carries
        the Portainer ``Name``. Arcane's ``token`` field holds the password.
        """
        port_type = reg.get("Type", 1)
        registry_type = self.REGISTRY_TYPE_MAP.get(port_type, "custom")
        ecr = reg.get("Ecr", {}) or {}
        is_ecr = registry_type == "ecr"

        result: Dict[str, Any] = {
            "url": reg.get("URL", ""),
            "username": reg.get("Username", ""),
            "token": reg.get("Password", ""),          # Arcane calls it "token"
            "description": reg.get("Name", ""),         # Arcane has no "name"; use description
            "insecure": False,
            "enabled": True,
            "registryType": registry_type,
            "awsAccessKeyId": ecr.get("AccessKeyID", "") if is_ecr else "",
            "awsSecretAccessKey": ecr.get("SecretAccessKey", "") if is_ecr else "",
            "awsRegion": ecr.get("Region", "") if is_ecr else "",
        }

        # Warn about registries that may need manual credential verification
        if port_type in (2, 3, 5):
            type_names = {2: "Quay.io", 3: "Azure ACR", 5: "GitLab"}
            self.logger.warning(
                "Registry '%s' (type: %s) -- credentials may need manual verification in Arcane",
                reg.get("Name", ""),
                type_names.get(port_type, "unknown"),
            )

        return result

    def _transform_stack_to_project(self, stack: dict, compose_content: str) -> dict:
        """Convert Portainer stack to Arcane project payload.

        Converts stack.Env array [{name, value}] to envContent string (KEY=VALUE lines).
        """
        env_vars = stack.get("Env", []) or []
        env_lines = [
            f"{v.get('name', '')}={v.get('value', '')}"
            for v in env_vars
            if v.get("name")
        ]
        env_content = "\n".join(env_lines)
        if env_content:
            env_content += "\n"

        return {
            "name": stack.get("Name", ""),
            "composeContent": compose_content,
            "envContent": env_content,
        }

    def _transform_git_stack_to_gitops(self, stack: dict, repo_id: str) -> dict:
        """Convert a git-based stack to an Arcane GitOps sync payload.

        Extracts GitConfig: branch (strips ``refs/heads/``), composePath,
        autoSync, syncInterval.
        """
        git_cfg = stack.get("GitConfig", {}) or {}
        branch = git_cfg.get("ReferenceName", "main")
        # Strip refs/heads/ prefix if present
        if branch.startswith("refs/heads/"):
            branch = branch[len("refs/heads/"):]

        auto_update = stack.get("AutoUpdate", {}) or {}
        auto_sync = bool(auto_update.get("Interval"))
        # Default sync interval: 5 minutes (300s) if auto-sync is on
        sync_interval = auto_update.get("Interval", 300) if auto_sync else 0
        # Coerce to int: handle string values like "5m" or "300"
        if isinstance(sync_interval, str):
            # Try plain int first, then extract leading digits, default 300
            try:
                sync_interval = int(sync_interval)
            except ValueError:
                m = re.match(r"(\d+)", sync_interval)
                if m:
                    val = int(m.group(1))
                    # If the suffix is 'm' (minutes), convert to seconds
                    if sync_interval.rstrip().endswith("m"):
                        sync_interval = val * 60
                    else:
                        sync_interval = val
                else:
                    sync_interval = 300

        return {
            "name": stack.get("Name", ""),
            "repositoryId": repo_id,
            "branch": branch,
            "composePath": git_cfg.get("ComposeFilePathInRepository", "docker-compose.yml"),
            "autoSync": auto_sync,
            "syncInterval": sync_interval,
        }

    def _transform_git_config_to_repo(self, stack: dict) -> dict:
        """Extract git repository info from a git-based stack.

        Returns payload for Arcane ``create_git_repo``.
        """
        git_cfg = stack.get("GitConfig", {}) or {}
        auth = git_cfg.get("Authentication", {}) or {}

        # Determine auth type
        has_token = bool(auth.get("Password") or auth.get("Token"))
        has_username = bool(auth.get("Username"))
        auth_type = "token" if (has_token or has_username) else "none"

        return {
            "name": f"repo-{stack.get('Name', 'unknown')}",
            "url": git_cfg.get("URL", ""),
            "authType": auth_type,
            "token": auth.get("Password", "") or auth.get("Token", ""),
            "username": auth.get("Username", ""),
            "enabled": True,
        }

    def _container_bind_specs(
        self,
        mounts_raw: list,
        host_config: dict,
    ) -> List[str]:
        """Bind specs Arcane can pass to Docker.

        Prefers HostConfig.Binds because a named volume appears there by
        name. Mount.Source for a volume is the engine's host directory.
        """
        target = self.engine_kind or ""
        source = self.source_engine_kind or ""
        raw_binds = [
            bind for bind in (host_config.get("Binds") or [])
            if isinstance(bind, str) and bind.strip()
        ]
        if raw_binds:
            return [
                normalize_bind_spec(bind, target, source) for bind in raw_binds
            ]

        specs: List[str] = []
        for mount in mounts_raw or []:
            if not isinstance(mount, dict):
                continue
            dest = mount.get("Destination") or ""
            mount_type = (mount.get("Type") or "").lower()
            if mount_type == "volume":
                src = mount.get("Name") or ""
            else:
                src = mount.get("Source") or ""
            if not src or not dest:
                continue
            mode = mount.get("Mode") or ""
            if not mode:
                bits = []
                if mount.get("RW") is False:
                    bits.append("ro")
                propagation = mount.get("Propagation") or ""
                if propagation:
                    bits.append(propagation)
                mode = ",".join(bits)
            spec = f"{src}:{dest}"
            if mode:
                spec = f"{spec}:{mode}"
            specs.append(normalize_bind_spec(spec, target, source))
        return specs

    def _transform_network(self, net: dict) -> dict:
        """Map a Portainer/Docker network to Arcane network create payload.

        Preserves driver, IPAM config, labels, and options.
        """
        ipam_cfg = net.get("IPAM", {}) or {}
        ipam_config_list = ipam_cfg.get("Config", []) or []

        # Build IPAM section
        ipam: Dict[str, Any] = {}
        if ipam_cfg.get("Driver"):
            ipam["driver"] = ipam_cfg["Driver"]
        if ipam_config_list:
            ipam["config"] = []
            for subnet_cfg in ipam_config_list:
                entry: Dict[str, str] = {}
                if subnet_cfg.get("Subnet"):
                    entry["subnet"] = subnet_cfg["Subnet"]
                if subnet_cfg.get("Gateway"):
                    entry["gateway"] = subnet_cfg["Gateway"]
                if subnet_cfg.get("IPRange"):
                    entry["ipRange"] = subnet_cfg["IPRange"]
                if subnet_cfg.get("AuxAddress"):
                    entry["auxAddress"] = subnet_cfg["AuxAddress"]
                if entry:
                    ipam["config"].append(entry)
        if ipam_cfg.get("Options"):
            ipam["options"] = ipam_cfg["Options"]

        options: Dict[str, Any] = {
            "driver": net.get("Driver", "bridge"),
            "internal": net.get("Internal", False),
            "attachable": net.get("Attachable", False),
            "enableIPv6": net.get("EnableIPv6", False),
            "labels": net.get("Labels", {}) or {},
            "options": net.get("Options", {}) or {},
        }
        if ipam:
            options["ipam"] = ipam

        return {
            "name": net.get("Name", ""),
            "options": options,
        }

    def _transform_container(self, inspect_data: dict) -> dict:
        """FULL FIDELITY transform of Docker inspect data to Arcane ContainerCreate schema.

        Parses Config, HostConfig, Mounts, NetworkSettings from the inspect payload.
        Every field matters -- uses ``or []`` for nullable list fields to avoid None issues.
        """
        config = inspect_data.get("Config", {}) or {}
        host_config = inspect_data.get("HostConfig", {}) or {}
        mounts_raw = inspect_data.get("Mounts", []) or []
        network_settings = inspect_data.get("NetworkSettings", {}) or {}

        # --- Port bindings ---
        port_bindings_raw = host_config.get("PortBindings", {}) or {}
        port_bindings: Dict[str, Any] = {}
        for container_port, host_list in port_bindings_raw.items():
            # container_port is like "80/tcp"
            port_bindings[container_port] = [
                {
                    "hostIp": binding.get("HostIp", ""),
                    "hostPort": binding.get("HostPort", ""),
                }
                for binding in (host_list or [])
            ]

        # --- Restart policy ---
        restart_policy = host_config.get("RestartPolicy", {}) or {}

        # --- Exposed ports ---
        exposed_ports = config.get("ExposedPorts", {}) or {}

        # Named volumes use the volume name, not the source host path.
        # Podman stores that path under /var/lib/containers, which does not
        # exist on a Docker host. Binds carry the name and are preferred.
        # Arcane forwards hostConfig.binds when it is non-empty, otherwise
        # the volumes list, so both must be the same sanitized specs.
        volume_strings = self._container_bind_specs(mounts_raw, host_config)

        # --- Restart policy as string ---
        restart_name = restart_policy.get("Name", "")
        max_retry = restart_policy.get("MaximumRetryCount") or 0
        if restart_name == "on-failure" and max_retry:
            restart_str = f"on-failure:{max_retry}"
        else:
            restart_str = restart_name

        # --- Build the result ---
        result: Dict[str, Any] = {
            # From Config
            "image": config.get("Image", ""),
            "env": config.get("Env", []) or [],
            "cmd": config.get("Cmd", []) or [],
            "entrypoint": config.get("Entrypoint", []) or [],
            "labels": config.get("Labels", {}) or {},
            "hostname": config.get("Hostname", ""),
            "domainname": config.get("Domainname", ""),
            "user": config.get("User", ""),
            "workingDir": config.get("WorkingDir", ""),
            "tty": config.get("Tty", False),
            "openStdin": config.get("OpenStdin", False),
            "volumes": volume_strings,
            "exposedPorts": exposed_ports,
            "restartPolicy": restart_str,
            "privileged": host_config.get("Privileged", False),
            # hostConfig -- per ContainerHostConfigCreate schema
            "hostConfig": {
                "networkMode": host_config.get("NetworkMode", "default"),
                "portBindings": port_bindings,
                "binds": volume_strings,
                "memory": host_config.get("Memory") or 0,
                "memorySwap": host_config.get("MemorySwap") or 0,
                "nanoCpus": host_config.get("NanoCpus") or 0,
                "cpuShares": host_config.get("CpuShares") or 0,
                "readonlyRootfs": host_config.get("ReadonlyRootfs", False),
                "privileged": host_config.get("Privileged", False),
                "publishAllPorts": host_config.get("PublishAllPorts", False),
                "autoRemove": host_config.get("AutoRemove", False),
                "restartPolicy": {
                    "name": restart_policy.get("Name", ""),
                    "maximumRetryCount": restart_policy.get("MaximumRetryCount") or 0,
                },
            },
        }

        # Attach container name (strip leading /)
        name = inspect_data.get("Name", "")
        if name.startswith("/"):
            name = name[1:]
        result["name"] = name

        return result

    def _transform_custom_template(self, template: dict, file_content: str) -> dict:
        """Convert Portainer custom template to Arcane template payload."""
        return {
            "name": template.get("Title", ""),
            "description": template.get("Description", ""),
            "content": file_content,
            "envContent": "",
        }

    def _transform_user(self, user: dict) -> dict:
        """Map Portainer user to Arcane user create payload.

        Arcane 2.17's create schema has no ``roles`` field and rejects one
        with 422. ``roleId`` is stripped by the caller and sent to
        ``PUT /users/{id}/role-assignments`` after the account exists.
        Portainer role 1 is the administrator. Role 2 is a standard user,
        mapped to Arcane's editor role (read/write on Docker resources).
        Passwords cannot be migrated.
        """
        role_id = "role_admin" if user.get("Role", 2) == 1 else "role_editor"
        username = user.get("Username", "")
        return {
            "username": username,
            "password": secrets.token_urlsafe(16),
            "displayName": username,
            "roleId": role_id,
        }

    # ------------------------------------------------------------------
    # Task 10: Export to Disk
    # ------------------------------------------------------------------

    def _export_to_disk(self):
        """Save all discovered Portainer data to the export directory.

        Called before any live migration writes.  Respects ``config.dry_run``
        (no files written) and ``_should_include()`` (user scope selection).
        """
        self._load_engine_sides()
        base = Path(self.config.backup_dir)
        manifest: Dict[str, Any] = {
            "tool_version": __version__,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "portainer_edition": self.config.portainer_edition,
            "portainer_version": self.config.portainer_version,
            "source_engine": self._source_engine_record(),
            "counts": {},
        }

        def _write_json(filepath: Path, data: Any):
            """Write *data* as JSON unless dry-run."""
            if self.config.dry_run:
                self.ui.dry_run_msg(f"Write {filepath}")
                return
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, default=str)

        def _write_text(filepath: Path, text: str):
            """Write plain text unless dry-run."""
            if self.config.dry_run:
                self.ui.dry_run_msg(f"Write {filepath}")
                return
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write(text)

        # ---- Registries ----
        if self._should_include("registries"):
            registries = self.discovery.get("registries", {}).get("data", [])
            masked = []
            for r in registries:
                entry = dict(r)
                if "Password" in entry:
                    entry["Password"] = "***MASKED***"
                # Mask ECR credentials if present
                if "Ecr" in entry and isinstance(entry["Ecr"], dict):
                    ecr = dict(entry["Ecr"])
                    if "AccessKeyID" in ecr:
                        ecr["AccessKeyID"] = "***MASKED***"
                    if "SecretAccessKey" in ecr:
                        ecr["SecretAccessKey"] = "***MASKED***"
                    entry["Ecr"] = ecr
                masked.append(entry)
            _write_json(base / "registries" / "registries.json", masked)
            manifest["counts"]["registries"] = len(masked)
            self.ui.success(f"Exported {len(masked)} registries")

        # ---- Stacks ----
        if self._should_include("stacks"):
            stacks = self.discovery.get("stacks", {}).get("data", [])
            for stack in stacks:
                name = stack.get("Name", f"stack_{stack.get('Id', 'unknown')}")
                stack_dir = base / "stacks" / name
                # Compose file
                try:
                    file_resp = self.portainer.get_stack_file(stack.get("Id", ""))
                    compose_content = file_resp.get("StackFileContent", "")
                except Exception as exc:
                    compose_content = ""
                    self.logger.error(
                        "Failed to fetch compose file for stack '%s': %s -- "
                        "writing EMPTY docker-compose.yml", name, exc
                    )
                    self.report.record_failure(
                        "Stacks", name,
                        f"Compose file fetch failed: {exc}",
                    )
                    self.ui.warning(
                        f"Stack '{name}' compose file unreadable -- "
                        f"export written as empty placeholder"
                    )
                _write_text(stack_dir / "docker-compose.yml", compose_content)
                # .env
                env_vars = stack.get("Env", []) or []
                env_lines = [
                    f"{v.get('name', '')}={v.get('value', '')}"
                    for v in env_vars if v.get("name")
                ]
                _write_text(stack_dir / ".env", "\n".join(env_lines) + "\n" if env_lines else "")
                # metadata
                _write_json(stack_dir / "metadata.json", stack)
            manifest["counts"]["stacks"] = len(stacks)
            self.ui.success(f"Exported {len(stacks)} stacks")

        # ---- Standalone Containers ----
        if self._should_include("standalone_containers"):
            containers = self.discovery.get("standalone_containers", {}).get("data", [])
            inspected = []
            for c in containers:
                cid = c.get("Id", "")
                try:
                    inspect_data = self.portainer.inspect_container(cid)
                    inspected.append(inspect_data)
                except Exception as exc:
                    self.logger.warning("Could not inspect container %s: %s", cid, exc)
                    inspected.append(c)
            _write_json(base / "containers" / "standalone.json", inspected)
            manifest["counts"]["standalone_containers"] = len(inspected)
            self.ui.success(f"Exported {len(inspected)} standalone containers")

        # ---- Networks ----
        if self._should_include("networks"):
            networks = self.discovery.get("networks", {}).get("data", [])
            _write_json(base / "networks" / "networks.json", networks)
            manifest["counts"]["networks"] = len(networks)
            self.ui.success(f"Exported {len(networks)} networks")

        # ---- Volumes ----
        if self._should_include("volumes"):
            volumes = self.discovery.get("volumes", {}).get("data", [])
            _write_json(base / "volumes" / "volumes.json", volumes)
            manifest["counts"]["volumes"] = len(volumes)
            # Backup volume data if Docker is available
            if self.config.has_docker and self.docker.is_available():
                backup_path = base / "volumes" / "backups"
                with self.ui.create_progress() as progress:
                    task = progress.add_task("Backing up volumes...", total=len(volumes))
                    for vol in volumes:
                        vol_name = vol.get("Name", "")
                        if vol_name and not self.config.dry_run:
                            self.docker.backup_volume(vol_name, str(backup_path))
                        elif self.config.dry_run:
                            self.ui.dry_run_msg(f"Backup volume {vol_name}")
                        progress.advance(task)
                self.ui.success(f"Exported {len(volumes)} volumes (with backups)")
            else:
                self.ui.info(f"Exported {len(volumes)} volumes (metadata only -- no Docker)")

        # ---- Custom Templates ----
        if self._should_include("custom_templates"):
            templates = self.discovery.get("custom_templates", {}).get("data", [])
            enriched = []
            for t in templates:
                entry = dict(t)
                try:
                    file_resp = self.portainer.get_custom_template_file(t.get("Id", ""))
                    entry["FileContent"] = file_resp.get("FileContent", "")
                except Exception:
                    entry["FileContent"] = ""
                enriched.append(entry)
            _write_json(base / "templates" / "custom_templates.json", enriched)
            manifest["counts"]["custom_templates"] = len(enriched)
            self.ui.success(f"Exported {len(enriched)} custom templates")

        # ---- Users ----
        if self._should_include("users"):
            users = self.discovery.get("users", {}).get("data", [])
            cleaned = []
            for u in users:
                entry = dict(u)
                entry.pop("Password", None)
                cleaned.append(entry)
            _write_json(base / "users" / "users.json", cleaned)
            manifest["counts"]["users"] = len(cleaned)
            self.ui.success(f"Exported {len(cleaned)} users")

        # ---- Webhooks ----
        if self._should_include("webhooks"):
            webhooks = self.discovery.get("webhooks", {}).get("data", [])
            _write_json(base / "webhooks" / "webhooks.json", webhooks)
            manifest["counts"]["webhooks"] = len(webhooks)
            self.ui.success(f"Exported {len(webhooks)} webhooks")

        # ---- Settings ----
        if self._should_include("settings"):
            settings = self.discovery.get("settings", {}).get("data", {})

            SENSITIVE_TERMS = ("password", "secret", "token", "key", "credential", "auth", "cert", "private")

            def _mask_settings(obj: Any) -> Any:
                if isinstance(obj, dict):
                    masked = {}
                    for k, v in obj.items():
                        if isinstance(k, str) and any(
                            s in k.lower() for s in SENSITIVE_TERMS
                        ):
                            masked[k] = "***MASKED***"
                        else:
                            masked[k] = _mask_settings(v)
                    return masked
                if isinstance(obj, list):
                    return [_mask_settings(item) for item in obj]
                return obj

            _write_json(base / "settings" / "portainer_settings.json", _mask_settings(settings))
            manifest["counts"]["settings"] = 1
            self.ui.success("Exported Portainer settings")

        # ---- EE Reference Exports ----
        if self._is_ee():
            ee_dir = base / "ee_reference"

            if self._should_include("teams"):
                teams = self.discovery.get("teams", {}).get("data", [])
                _write_json(ee_dir / "teams.json", teams)
                manifest["counts"]["teams"] = len(teams)
                self.ui.info(f"EE reference: {len(teams)} teams")

            if self._should_include("team_memberships"):
                try:
                    memberships = self.portainer.list_team_memberships()
                except Exception:
                    memberships = []
                _write_json(ee_dir / "team_memberships.json", memberships)
                manifest["counts"]["team_memberships"] = len(memberships)
                self.ui.info(f"EE reference: {len(memberships)} team memberships")

            if self._should_include("roles"):
                roles = self.discovery.get("roles", {}).get("data", [])
                _write_json(ee_dir / "roles.json", roles)
                manifest["counts"]["roles"] = len(roles)
                self.ui.info(f"EE reference: {len(roles)} roles")

            if self._should_include("resource_controls"):
                try:
                    resource_controls = self.portainer.list_resource_controls()
                except Exception:
                    resource_controls = []
                _write_json(ee_dir / "resource_controls.json", resource_controls)
                manifest["counts"]["resource_controls"] = len(resource_controls)
                self.ui.info(f"EE reference: {len(resource_controls)} resource controls")

            if self._should_include("edge_stacks"):
                edge_stacks = self.discovery.get("edge_stacks", {}).get("data", [])
                if edge_stacks:
                    _write_json(ee_dir / "edge_stacks.json", edge_stacks)
                    manifest["counts"]["edge_stacks"] = len(edge_stacks)
                    self.ui.info(f"EE reference: {len(edge_stacks)} edge stacks")

            self._ee_exported = True

        # ---- Manifest ----
        _write_json(base / "manifest.json", manifest)
        self.ui.success("Export manifest saved")

    # ------------------------------------------------------------------
    # Task 11: Live Migration Phases
    # ------------------------------------------------------------------

    def _portainer_backup(self):
        """Create a Portainer server backup (tar.gz)."""
        phase = "portainer_backup"
        if self._phase_status(phase) == "completed":
            self.ui.info("Portainer backup already completed -- skipping")
            return

        self._mark_phase(phase, "in_progress")

        password = Prompt.ask(
            "[bold]Backup encryption password[/bold] (blank for none)",
            password=True,
            default="",
        )

        if self.config.dry_run:
            self.ui.dry_run_msg("Portainer backup")
            self._mark_phase(phase, "completed")
            return

        try:
            backup_dir = Path(self.config.backup_dir) / "portainer_backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / "portainer_backup.tar.gz"
            # Stream directly to disk so huge backups don't OOM the process.
            self.portainer.trigger_backup(password, dest_path=str(backup_path))

            size = backup_path.stat().st_size
            if size < 1024:
                self.ui.warning(f"Backup file is only {size} bytes -- may be corrupt")
                if not Confirm.ask("  Continue without a valid backup?", default=False):
                    self._mark_phase(phase, "failed")
                    return
            else:
                self.ui.success(f"Portainer backup saved ({size:,} bytes)")
            self._mark_phase(phase, "completed")
        except http_requests.exceptions.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (401, 403):
                self.ui.warning(
                    "Portainer backup failed (permission denied) -- not fatal"
                )
                self.logger.warning("Backup permission error: %s", exc)
                self._mark_phase(phase, "completed")
            else:
                self.ui.error(f"Portainer backup failed: {exc}")
                self.logger.error("Backup error: %s", exc)
                self._mark_phase(phase, "failed")
        except Exception as exc:
            self.ui.error(f"Portainer backup failed: {exc}")
            self.logger.error("Backup error: %s", exc)
            self._mark_phase(phase, "failed")

    def _migrate_registries(self):
        """Migrate container registries from Portainer to Arcane."""
        phase = "registries"
        if self._phase_status(phase) == "completed":
            self.ui.info("Registries already migrated -- skipping")
            return
        if not self._should_include("registries"):
            self.ui.info("Registries not selected -- skipping")
            self._mark_phase(phase, "completed")
            return

        self._mark_phase(phase, "in_progress")
        registries = self.discovery.get("registries", {}).get("data", [])

        for reg in registries:
            reg_id = str(reg.get("Id", ""))
            name = reg.get("Name", reg_id)
            if self._is_migrated(phase, reg_id):
                self.report.record_skip("Registries", name, "already migrated")
                continue
            try:
                payload = self._transform_registry(reg)
                result = self._execute_or_log(
                    f"Create registry '{name}'",
                    self.arcane.create_registry,
                    payload,
                )
                target_id = result.get("id", "") if isinstance(result, dict) else ""
                self.report.record_success("Registries", name, reg_id, target_id)
                if not self.config.dry_run:
                    self.report.add_rollback(
                        "DELETE",
                        f"{self.arcane.base_url}/container-registries/{target_id}",
                        f"Delete registry '{name}'",
                    )
                self._record_migrated(phase, reg_id)
            except Exception as exc:
                self.logger.error("Failed to migrate registry %s: %s", name, exc)
                self.report.record_failure("Registries", name, str(exc))
                self.ui.error(f"Registry '{name}' failed: {exc}")

        self._mark_phase(phase, "completed")

    def _migrate_git_repos(self):
        """Migrate git repository configs from git-based stacks."""
        phase = "git_repos"
        if self._phase_status(phase) == "completed":
            self.ui.info("Git repos already migrated -- skipping")
            return
        if not self._should_include("stacks"):
            self.ui.info("Stacks not selected -- skipping git repos")
            self._mark_phase(phase, "completed")
            return

        self._mark_phase(phase, "in_progress")
        stacks = self.discovery.get("stacks", {}).get("data", [])
        git_stacks = [s for s in stacks if s.get("GitConfig")]

        for stack in git_stacks:
            stack_id = str(stack.get("Id", ""))
            name = stack.get("Name", stack_id)
            if self._is_migrated(phase, stack_id):
                self.report.record_skip("Git Repos", name, "already migrated")
                continue
            if self._leave_management_app("Git Repos", name, stack_id, phase):
                continue
            try:
                payload = self._transform_git_config_to_repo(stack)
                result = self._execute_or_log(
                    f"Create git repo for '{name}'",
                    self.arcane.create_git_repo,
                    payload,
                )
                target_id = result.get("id", "") if isinstance(result, dict) else ""
                self._git_repo_map[stack_id] = str(target_id)
                self.report.record_success("Git Repos", name, stack_id, target_id)
                if not self.config.dry_run:
                    self.report.add_rollback(
                        "DELETE",
                        f"{self.arcane.base_url}/customize/git-repositories/{target_id}",
                        f"Delete git repo for '{name}'",
                    )
                self._record_migrated(phase, stack_id)
            except Exception as exc:
                self.logger.error("Failed to migrate git repo for %s: %s", name, exc)
                self.report.record_failure("Git Repos", name, str(exc))
                self.ui.error(f"Git repo for '{name}' failed: {exc}")

        self._mark_phase(phase, "completed")

    @staticmethod
    def _resource_name(item: dict, *keys: str) -> str:
        """First non-empty name from the given keys. Lists use the first entry."""
        for key in keys:
            value = item.get(key)
            if isinstance(value, list) and value:
                value = value[0]
            if isinstance(value, str) and value.strip():
                return value.strip().lstrip("/")
        return ""

    @staticmethod
    def _canonical_resource_id(value: Any) -> str:
        """Return a full 64-hex Docker/Podman ID, or "" when it is not one.

        Short IDs and display names are rejected. A 64-hex ID is what the
        engine assigned to that object. The same value on both APIs is the
        same object, not a name that happens to match on another host.
        """
        raw = str(value or "").strip().lower()
        if raw.startswith("sha256:"):
            raw = raw[7:]
        if len(raw) == 64 and all(ch in "0123456789abcdef" for ch in raw):
            return raw
        return ""

    def _ids_from(self, items: list, *keys: str) -> set:
        found = set()
        for item in items or []:
            if not isinstance(item, dict):
                continue
            for key in keys:
                canonical = self._canonical_resource_id(item.get(key))
                if canonical:
                    found.add(canonical)
                    break
        return found

    def _source_container_names(self) -> set:
        """Container names from discovery. Used only to warn about name clashes."""
        names = set()
        for container in self.discovery.get("standalone_containers", {}).get("data", []) or []:
            name = self._resource_name(container, "Names", "names", "Name", "name")
            if name:
                names.add(name.lower())
        for stack in self.discovery.get("stacks", {}).get("data", []) or []:
            name = self._resource_name(stack, "Name", "name")
            if name:
                names.add(name.lower())
        return names

    def _source_identity_ids(self) -> tuple:
        """Container and network IDs from the live Portainer engine, plus the export.

        The live list includes compose containers. Discovery's standalone list
        omits those, and an export can be stale, so a connected Portainer wins.
        """
        containers: list = []
        networks: list = []
        if self.config.portainer_url:
            try:
                listed = self.portainer.list_containers(all_containers=True)
                if isinstance(listed, list):
                    containers.extend(listed)
            except Exception as exc:
                self.logger.warning("Could not list Portainer containers: %s", exc)
            try:
                listed_nets = self.portainer.list_networks()
                if isinstance(listed_nets, list):
                    networks.extend(listed_nets)
            except Exception as exc:
                self.logger.warning("Could not list Portainer networks: %s", exc)
        containers.extend(
            self.discovery.get("standalone_containers", {}).get("data", []) or []
        )
        networks.extend(self.discovery.get("networks", {}).get("data", []) or [])
        return (
            self._ids_from(containers, "Id", "id"),
            self._ids_from(networks, "Id", "id"),
        )

    def _engine_pair_message(self) -> str:
        """One line naming the engine behind Portainer and the engine behind Arcane."""
        source = engine_summary(self.source_engine_kind, self.source_engine_info)
        target = engine_summary(self.engine_kind, self.engine_info)
        if self.source_engine_kind and self.engine_kind:
            if self.source_engine_kind == self.engine_kind:
                label = "Podman" if self.source_engine_kind == "podman" else "Docker"
                relation = f"Both servers are {label}."
            else:
                src = "Podman" if self.source_engine_kind == "podman" else "Docker"
                dst = "Podman" if self.engine_kind == "podman" else "Docker"
                relation = (
                    f"Portainer is {src} and Arcane is {dst}. "
                    "Container mounts will be translated for the Arcane engine."
                )
        elif self.source_engine_kind:
            relation = "Arcane did not return engine info."
        elif self.engine_kind:
            relation = "Portainer did not return engine info."
        else:
            relation = "Neither server returned engine info."
        return f"Portainer engine: {source}. Arcane engine: {target}. {relation}"

    def _remember_source_engine(self, saved: Any) -> None:
        """Restore the Portainer engine recorded in an export manifest."""
        if not isinstance(saved, dict) or not saved:
            return
        info = {
            "ServerVersion": str(saved.get("serverVersion") or ""),
            "DockerRootDir": str(saved.get("dockerRootDir") or ""),
            "Name": str(saved.get("name") or ""),
            "InitBinary": str(saved.get("initBinary") or ""),
        }
        kind = str(saved.get("kind") or "").strip().lower()
        if kind not in ("podman", "docker"):
            kind = classify_engine(info)
        if not kind:
            return
        self.source_engine_info = info
        self.source_engine_kind = kind

    def _source_engine_record(self) -> Dict[str, str]:
        """Fields written to the export so a later import still knows the source."""
        info = self.source_engine_info or {}
        return {
            "kind": self.source_engine_kind or "",
            "serverVersion": str(info.get("ServerVersion") or ""),
            "dockerRootDir": str(info.get("DockerRootDir") or ""),
            "name": str(info.get("Name") or ""),
            "initBinary": str(info.get("InitBinary") or ""),
        }

    def _load_engine_sides(self) -> None:
        """Classify the Portainer engine and the Arcane engine.

        The two hosts are read separately. A failed read keeps a source
        classification already loaded from an export. The pair is printed
        once, the first time this runs.
        """
        eid = self.config.arcane_environment_id or "0"
        try:
            fetched = self.arcane.get_docker_info(eid) or {}
        except Exception as exc:
            self.logger.warning("Could not read Arcane engine info: %s", exc)
            fetched = None
        if isinstance(fetched, dict) and fetched:
            self.engine_info = fetched
            self.engine_kind = classify_engine(fetched)

        if self.config.portainer_url:
            try:
                source = self.portainer.get_docker_info() or {}
            except Exception as exc:
                self.logger.warning(
                    "Could not read Portainer engine info: %s", exc
                )
                source = None
            if isinstance(source, dict) and source:
                self.source_engine_info = source
                self.source_engine_kind = classify_engine(source)

        if not self._engines_announced:
            self.ui.info(self._engine_pair_message())
            self._engines_announced = True

    def _refresh_target_engine(self) -> None:
        """Detect both engines, and whether both APIs see the same one.

        Same-engine adoption turns on only when a full container or network ID
        is present on both sides, or when both Docker info IDs are present and
        equal. Podman returns a new info ID on every query, so a mismatch
        there is ignored. Matching names are never enough. Matching engine
        kinds are not enough either: Podman on one host and Docker on another
        is a normal migration.
        """
        self._load_engine_sides()
        info = self.engine_info if isinstance(self.engine_info, dict) else {}
        eid = self.config.arcane_environment_id or "0"
        root = str(info.get("DockerRootDir") or "")

        def _collect(items: list, *keys: str) -> set:
            found = set()
            for item in items or []:
                if not isinstance(item, dict):
                    continue
                name = self._resource_name(item, *keys)
                if name:
                    found.add(name.lower())
            return found

        def _safe_list(loader: Callable) -> list:
            try:
                listed = loader()
            except Exception as exc:
                self.logger.warning("Could not list target resources: %s", exc)
                return []
            return listed if isinstance(listed, list) else []

        containers = _safe_list(lambda: self.arcane.list_containers(eid))
        networks = _safe_list(lambda: self.arcane.list_networks(eid))
        volumes = _safe_list(lambda: self.arcane.list_volumes(eid))
        projects = _safe_list(lambda: self.arcane.list_projects(eid))
        self._target_names = {
            "containers": _collect(containers, "names", "Names", "name", "Name"),
            "networks": _collect(networks, "name", "Name"),
            "volumes": _collect(volumes, "name", "Name"),
            "projects": _collect(projects, "name", "Name"),
        }
        source_containers, source_networks = self._source_identity_ids()
        target_containers = self._ids_from(containers, "Id", "id")
        target_networks = self._ids_from(networks, "Id", "id")
        container_hits = len(source_containers & target_containers)
        network_hits = len(source_networks & target_networks)

        source_engine_id = str(
            (self.source_engine_info or {}).get("ID") or ""
        ).strip()
        target_engine_id = str(info.get("ID") or "").strip()
        # Docker stores a stable daemon ID. Podman invents a new UUID per
        # /info call, so equal IDs are evidence and unequal IDs are not.
        engine_id_match = bool(
            source_engine_id
            and target_engine_id
            and source_engine_id.lower() == target_engine_id.lower()
        )

        parts = []
        if container_hits:
            parts.append(f"{container_hits} container ID{'s' if container_hits != 1 else ''}")
        if network_hits:
            parts.append(f"{network_hits} network ID{'s' if network_hits != 1 else ''}")
        if engine_id_match:
            parts.append("Docker engine ID")
        self.engine_proven = bool(parts)
        self.engine_match_reason = (
            " and ".join(parts) + " match on both APIs"
            if parts else "no shared container, network, or engine ID"
        )

        kind = {"podman": "Podman", "docker": "Docker"}.get(
            self.engine_kind, "container"
        )
        if self.engine_proven and self._adopt_in_place is None:
            saved = self.state.get("adopt_in_place")
            if isinstance(saved, bool):
                self._adopt_in_place = saved
            else:
                self.ui.info(
                    f"Portainer and Arcane are the same {kind} engine: "
                    f"{self.engine_match_reason}."
                )
                try:
                    self._adopt_in_place = Confirm.ask(
                        "  [blue]Reuse the containers, networks, and volumes "
                        "already on that engine?[/blue]",
                        default=True,
                    )
                except (EOFError, KeyboardInterrupt):
                    self._adopt_in_place = False
                    self.ui.warning(
                        "No answer on in-place reuse. Resources will be created, not reused."
                    )
                self.state["adopt_in_place"] = self._adopt_in_place
                self._save_state()
        self.same_engine = bool(self.engine_proven and self._adopt_in_place)

        names_overlap = bool(
            self._source_container_names() & self._target_names["containers"]
        )
        if not self._engine_noted:
            if self.same_engine:
                server = str(info.get("ServerVersion") or "unknown")
                self.ui.info(
                    f"In-place reuse is on ({kind} {server}, root {root or 'unknown'}). "
                    "Existing containers, networks, and volumes will be kept."
                )
                self.report.add_action_item(
                    f"Arcane is attached to the same {kind} engine "
                    f"({self.engine_match_reason}). Existing containers, networks, "
                    "and volumes were left in place and were not copied. Compose "
                    "stacks were registered as Arcane projects so the already-running "
                    "containers show up under Projects."
                )
            elif self.engine_proven:
                self.ui.warning(
                    "Same engine was confirmed, and in-place reuse is off. "
                    "Creating resources may fail because those names are already taken."
                )
            elif names_overlap:
                self.ui.warning(
                    "Some container names already exist on Arcane, but no container "
                    "or network ID matches. They are treated as a different server."
                )
            self._engine_noted = True

    def _name_taken(self, kind: str, name: str) -> bool:
        """True when Arcane already lists this name. Names are not identity."""
        if not name:
            return False
        return name.lower() in self._target_names.get(kind, set())

    def _already_on_engine(self, kind: str, name: str) -> bool:
        """True when same-engine mode should keep this named resource as-is."""
        if not self.same_engine or not name:
            return False
        return self._name_taken(kind, name)

    def _migrate_networks(self):
        """Migrate user-defined networks to Arcane."""
        phase = "networks"
        if self._phase_status(phase) == "completed":
            self.ui.info("Networks already migrated -- skipping")
            return
        if not self._should_include("networks"):
            self.ui.info("Networks not selected -- skipping")
            self._mark_phase(phase, "completed")
            return

        self._mark_phase(phase, "in_progress")
        eid = self.config.arcane_environment_id
        networks = self.discovery.get("networks", {}).get("data", [])

        for net in networks:
            net_id = net.get("Id", "")
            name = net.get("Name", net_id)
            if self._is_migrated(phase, net_id):
                self.report.record_skip("Networks", name, "already migrated")
                continue
            if self._name_taken("networks", name):
                # Same-engine adoption reuses the live network. A name that
                # already exists on another host (Arcane's own arcane_default,
                # for example) cannot be created again. Leave it, and do not
                # add a rollback delete for a network this run did not create.
                if self._already_on_engine("networks", name):
                    self.report.record_success(
                        "Networks", name, net_id, name, status="adopted"
                    )
                    self.ui.info(
                        f"Network '{name}' already on this engine -- left in place"
                    )
                else:
                    self.report.record_skip(
                        "Networks", name, "already exists on target"
                    )
                    self.ui.info(
                        f"Network '{name}' already exists on Arcane -- left in place"
                    )
                self._record_migrated(phase, net_id)
                continue
            try:
                payload = self._transform_network(net)
                result = self._execute_or_log(
                    f"Create network '{name}'",
                    self.arcane.create_network,
                    eid,
                    payload,
                )
                target_id = result.get("id", result.get("Id", "")) if isinstance(result, dict) else ""
                self.report.record_success("Networks", name, net_id, target_id)
                if not self.config.dry_run:
                    self.report.add_rollback(
                        "DELETE",
                        f"{self.arcane.base_url}/environments/{eid}/networks/{target_id}",
                        f"Delete network '{name}'",
                    )
                self._record_migrated(phase, net_id)
            except Exception as exc:
                if _name_conflict(exc):
                    self.report.record_skip(
                        "Networks", name, "already exists on target"
                    )
                    self.ui.info(
                        f"Network '{name}' already exists on Arcane -- left in place"
                    )
                    self._record_migrated(phase, net_id)
                    continue
                self.logger.error("Failed to migrate network %s: %s", name, exc)
                self.report.record_failure("Networks", name, str(exc))
                self.ui.error(f"Network '{name}' failed: {exc}")

        self._mark_phase(phase, "completed")

    def _migrate_volumes(self):
        """Migrate volumes and optionally restore volume backups."""
        phase = "volumes"
        if self._phase_status(phase) == "completed":
            self.ui.info("Volumes already migrated -- skipping")
            return
        if not self._should_include("volumes"):
            self.ui.info("Volumes not selected -- skipping")
            self._mark_phase(phase, "completed")
            return

        self._mark_phase(phase, "in_progress")
        eid = self.config.arcane_environment_id
        volumes = self.discovery.get("volumes", {}).get("data", [])

        for vol in volumes:
            name = vol.get("Name", "")
            if self._is_migrated(phase, name):
                self.report.record_skip("Volumes", name, "already migrated")
                continue
            if self._name_taken("volumes", name):
                # Recreating the volume or uploading a tarball would not move
                # data, and a rollback delete would destroy the live volume.
                if self._already_on_engine("volumes", name):
                    self.report.record_success(
                        "Volumes", name, name, name, status="adopted"
                    )
                    self.ui.info(
                        f"Volume '{name}' already on this engine -- left in place"
                    )
                else:
                    self.report.record_skip(
                        "Volumes", name, "already exists on target"
                    )
                    self.ui.info(
                        f"Volume '{name}' already exists on Arcane -- left in place"
                    )
                self._record_migrated(phase, name)
                continue
            try:
                payload = {
                    "name": name,
                    "driver": vol.get("Driver", "local"),
                    "labels": vol.get("Labels", {}) or {},
                    "driverOpts": vol.get("Options", {}) or {},
                }
                result = self._execute_or_log(
                    f"Create volume '{name}'",
                    self.arcane.create_volume,
                    eid,
                    payload,
                )
                target_id = name  # volumes are identified by name
                self.report.record_success("Volumes", name, name, target_id)
                if not self.config.dry_run:
                    self.report.add_rollback(
                        "DELETE",
                        f"{self.arcane.base_url}/environments/{eid}/volumes/{name}",
                        f"Delete volume '{name}'",
                    )
                # Upload backup if it exists
                backup_file = (
                    Path(self.config.backup_dir) / "volumes" / "backups" / f"{name}.tar.gz"
                )
                if backup_file.is_file() and not self.config.dry_run:
                    try:
                        self.arcane.upload_volume_backup(eid, name, str(backup_file))
                        self.ui.success(f"Volume '{name}' backup restored")
                    except Exception as upload_exc:
                        # Previously silently continued: user would see volume
                        # "success" but the data was missing. Record as a
                        # failure so the final report surfaces it.
                        self.ui.error(
                            f"Volume '{name}' created but backup data upload "
                            f"FAILED: {upload_exc}"
                        )
                        self.logger.error(
                            "Volume backup upload failed for %s: %s",
                            name, upload_exc,
                        )
                        self.report.record_failure(
                            "Volume Data", name,
                            f"Upload failed: {upload_exc}",
                        )
                self._record_migrated(phase, name)
            except Exception as exc:
                if _name_conflict(exc):
                    self.report.record_skip(
                        "Volumes", name, "already exists on target"
                    )
                    self.ui.info(
                        f"Volume '{name}' already exists on Arcane -- left in place"
                    )
                    self._record_migrated(phase, name)
                    continue
                self.logger.error("Failed to migrate volume %s: %s", name, exc)
                self.report.record_failure("Volumes", name, str(exc))
                self.ui.error(f"Volume '{name}' failed: {exc}")

        self._mark_phase(phase, "completed")

    def _migrate_stacks(self):
        """Migrate file-based stacks as Arcane projects."""
        phase = "stacks"
        if self._phase_status(phase) == "completed":
            self.ui.info("Stacks already migrated -- skipping")
            return
        if not self._should_include("stacks"):
            self.ui.info("Stacks not selected -- skipping")
            self._mark_phase(phase, "completed")
            return

        self._mark_phase(phase, "in_progress")
        eid = self.config.arcane_environment_id
        stacks = self.discovery.get("stacks", {}).get("data", [])
        file_stacks = [s for s in stacks if not s.get("GitConfig")]

        for stack in file_stacks:
            stack_id = str(stack.get("Id", ""))
            name = stack.get("Name", stack_id)
            if self._is_migrated(phase, stack_id):
                self.report.record_skip("Stacks", name, "already migrated")
                continue
            if self._leave_management_app("Stacks", name, stack_id, phase):
                continue
            if self._name_taken("projects", name):
                if self._already_on_engine("projects", name):
                    self.report.record_success(
                        "Stacks", name, stack_id, name, status="adopted"
                    )
                    self.ui.info(
                        f"Project '{name}' already on this engine -- left in place"
                    )
                else:
                    self.report.record_skip(
                        "Stacks", name, "already exists on target"
                    )
                    self.ui.info(
                        f"Project '{name}' already exists on Arcane -- left in place"
                    )
                self._record_migrated(phase, stack_id)
                continue
            try:
                if self.config.import_mode:
                    # Read compose from exported directory instead of Portainer API
                    compose_path = Path(self.config.backup_dir) / "stacks" / name / "docker-compose.yml"
                    if compose_path.is_file():
                        with open(compose_path, "r", encoding="utf-8") as fh:
                            compose_content = fh.read()
                    else:
                        compose_content = ""
                else:
                    file_resp = self.portainer.get_stack_file(stack.get("Id", ""))
                    compose_content = file_resp.get("StackFileContent", "")
                if not compose_content.strip():
                    self.report.record_failure("Stacks", name, "Empty compose file")
                    self.ui.error(f"Stack '{name}': compose file is empty, skipping")
                    continue
                payload = self._transform_stack_to_project(stack, compose_content)
                result = self._execute_or_log(
                    f"Create project '{name}'",
                    self.arcane.create_project,
                    eid,
                    payload,
                )
                target_id = result.get("id", "") if isinstance(result, dict) else ""
                self.report.record_success("Stacks", name, stack_id, target_id)
                self._target_names.setdefault("projects", set()).add(name.lower())
                if not self.config.dry_run:
                    self.report.add_rollback(
                        "DELETE",
                        f"{self.arcane.base_url}/environments/{eid}/projects/{target_id}/destroy",
                        f"Destroy project '{name}'",
                    )
                self._record_migrated(phase, stack_id)
            except Exception as exc:
                self.logger.error("Failed to migrate stack %s: %s", name, exc)
                self.report.record_failure("Stacks", name, str(exc))
                self.ui.error(f"Stack '{name}' failed: {exc}")
                self._stop_if_projects_directory_blocked(exc)

        self._mark_phase(phase, "completed")

    def _migrate_gitops_syncs(self):
        """Create GitOps syncs for git-based stacks."""
        phase = "gitops_syncs"
        if self._phase_status(phase) == "completed":
            self.ui.info("GitOps syncs already migrated -- skipping")
            return
        if not self._should_include("stacks"):
            self.ui.info("Stacks not selected -- skipping GitOps syncs")
            self._mark_phase(phase, "completed")
            return

        self._mark_phase(phase, "in_progress")
        eid = self.config.arcane_environment_id
        stacks = self.discovery.get("stacks", {}).get("data", [])
        git_stacks = [s for s in stacks if s.get("GitConfig")]

        for stack in git_stacks:
            stack_id = str(stack.get("Id", ""))
            name = stack.get("Name", stack_id)
            if self._is_migrated(phase, stack_id):
                self.report.record_skip("GitOps Syncs", name, "already migrated")
                continue
            if self._leave_management_app("GitOps Syncs", name, stack_id, phase):
                continue
            repo_id = self._git_repo_map.get(stack_id)
            if not repo_id:
                self.report.record_skip(
                    "GitOps Syncs", name, "no matching git repo migrated"
                )
                self.ui.warning(f"GitOps sync for '{name}' skipped -- no repo mapping")
                continue
            try:
                payload = self._transform_git_stack_to_gitops(stack, repo_id)
                result = self._execute_or_log(
                    f"Create GitOps sync '{name}'",
                    self.arcane.create_gitops_sync,
                    eid,
                    payload,
                )
                target_id = result.get("id", "") if isinstance(result, dict) else ""
                self.report.record_success("GitOps Syncs", name, stack_id, target_id)
                if not self.config.dry_run:
                    self.report.add_rollback(
                        "DELETE",
                        f"{self.arcane.base_url}/environments/{eid}/gitops-syncs/{target_id}",
                        f"Delete GitOps sync '{name}'",
                    )
                self._record_migrated(phase, stack_id)
            except Exception as exc:
                self.logger.error("Failed to create GitOps sync for %s: %s", name, exc)
                self.report.record_failure("GitOps Syncs", name, str(exc))
                self.ui.error(f"GitOps sync for '{name}' failed: {exc}")
                self._stop_if_projects_directory_blocked(exc)

        self._mark_phase(phase, "completed")

    def _migrate_containers(self):
        """Migrate standalone containers to Arcane."""
        phase = "containers"
        if self._phase_status(phase) == "completed":
            self.ui.info("Containers already migrated -- skipping")
            return
        if not self._should_include("standalone_containers"):
            self.ui.info("Containers not selected -- skipping")
            self._mark_phase(phase, "completed")
            return

        self._mark_phase(phase, "in_progress")
        eid = self.config.arcane_environment_id
        containers = self.discovery.get("standalone_containers", {}).get("data", [])

        for c in containers:
            cid = c.get("Id", "")
            # List payloads use Names[]; inspect payloads (the export) use Name.
            name = self._resource_name(c, "Names", "names", "Name", "name") or cid[:12]
            if self._is_migrated(phase, cid):
                self.report.record_skip("Containers", name, "already migrated")
                continue
            if self._leave_management_app(
                "Containers",
                name,
                cid,
                phase,
                container_image_ref(c),
            ):
                continue
            if self._already_on_engine("containers", name):
                # Recreating a container that is already running on this engine
                # conflicts on the name and on published ports, and Podman
                # returns that as a 500. Arcane already lists the container.
                self.report.record_success(
                    "Containers", name, cid, name, status="adopted"
                )
                self.ui.info(
                    f"Container '{name}' is already running on this engine -- "
                    "Arcane can manage it from Containers"
                )
                self._record_migrated(phase, cid)
                continue
            try:
                if self.config.import_mode:
                    # In import mode, the standalone.json already contains inspect data
                    inspect_data = c
                else:
                    inspect_data = self.portainer.inspect_container(cid)
                payload = self._transform_container(inspect_data)
                result = self._execute_or_log(
                    f"Create container '{name}'",
                    self.arcane.create_container,
                    eid,
                    payload,
                )
                target_id = result.get("Id", result.get("id", "")) if isinstance(result, dict) else ""
                if not target_id and not self.config.dry_run:
                    self.ui.warning(f"Container '{name}' created but no ID returned; cannot start")
                self.report.record_success("Containers", name, cid, target_id)
                if not self.config.dry_run:
                    self.report.add_rollback(
                        "DELETE",
                        f"{self.arcane.base_url}/environments/{eid}/containers/{target_id}?force=true",
                        f"Delete container '{name}'",
                    )
                # Start the container if it was running
                state = inspect_data.get("State", {})
                was_running = (
                    state.get("Status", "").lower() == "running"
                    if isinstance(state, dict)
                    else False
                )
                if was_running and target_id and not self.config.dry_run:
                    try:
                        self.arcane.start_container(eid, target_id)
                        self.ui.info(f"Started container '{name}'")
                    except Exception as start_exc:
                        # Previously only warned: container was recorded as a
                        # migration "success" even though it wasn't running.
                        # Record as a partial failure so the final report
                        # surfaces it as an action item.
                        self.ui.error(
                            f"Container '{name}' created but FAILED to start: "
                            f"{start_exc}"
                        )
                        self.logger.error(
                            "Container start failed for %s: %s", name, start_exc
                        )
                        self.report.record_failure(
                            "Container Start", name,
                            f"Created but start failed: {start_exc}",
                        )
                self._record_migrated(phase, cid)
            except Exception as exc:
                self.logger.error("Failed to migrate container %s: %s", name, exc)
                self.report.record_failure("Containers", name, str(exc))
                self.ui.error(f"Container '{name}' failed: {exc}")

        self._mark_phase(phase, "completed")

    def _migrate_templates(self):
        """Migrate custom templates to Arcane."""
        phase = "templates"
        if self._phase_status(phase) == "completed":
            self.ui.info("Templates already migrated -- skipping")
            return
        if not self._should_include("custom_templates"):
            self.ui.info("Custom Templates not selected -- skipping")
            self._mark_phase(phase, "completed")
            return

        self._mark_phase(phase, "in_progress")
        templates = self.discovery.get("custom_templates", {}).get("data", [])

        for t in templates:
            tid = str(t.get("Id", ""))
            name = t.get("Title", tid)
            if self._is_migrated(phase, tid):
                self.report.record_skip("Custom Templates", name, "already migrated")
                continue
            try:
                if self.config.import_mode:
                    # In import mode, FileContent is already embedded in the template data
                    file_content = t.get("FileContent", "")
                else:
                    file_resp = self.portainer.get_custom_template_file(t.get("Id", ""))
                    file_content = file_resp.get("FileContent", "")
                payload = self._transform_custom_template(t, file_content)
                result = self._execute_or_log(
                    f"Create template '{name}'",
                    self.arcane.create_template,
                    payload,
                )
                target_id = result.get("id", "") if isinstance(result, dict) else ""
                self.report.record_success("Custom Templates", name, tid, target_id)
                if not self.config.dry_run:
                    self.report.add_rollback(
                        "DELETE",
                        f"{self.arcane.base_url}/templates/{target_id}",
                        f"Delete template '{name}'",
                    )
                self._record_migrated(phase, tid)
            except Exception as exc:
                self.logger.error("Failed to migrate template %s: %s", name, exc)
                self.report.record_failure("Custom Templates", name, str(exc))
                self.ui.error(f"Template '{name}' failed: {exc}")

        self._mark_phase(phase, "completed")

    def _migrate_users(self):
        """Migrate users to Arcane, skipping duplicates."""
        phase = "users"
        if self._phase_status(phase) == "completed":
            self.ui.info("Users already migrated -- skipping")
            return
        if not self._should_include("users"):
            self.ui.info("Users not selected -- skipping")
            self._mark_phase(phase, "completed")
            return

        self._mark_phase(phase, "in_progress")
        users = self.discovery.get("users", {}).get("data", [])

        # Get existing Arcane users to avoid duplicates
        try:
            existing = self.arcane.list_users() if not self.config.dry_run else []
        except Exception:
            existing = []
        existing_usernames = {
            u.get("username", "").lower() for u in existing
        }

        for user in users:
            uid = str(user.get("Id", ""))
            username = user.get("Username", uid)
            if self._is_migrated(phase, uid):
                self.report.record_skip("Users", username, "already migrated")
                continue
            if username.lower() in existing_usernames:
                self.report.record_skip("Users", username, "already exists in Arcane")
                self.ui.info(f"User '{username}' already exists -- skipped")
                self._record_migrated(phase, uid)
                continue
            try:
                payload = self._transform_user(user)
                role_id = str(payload.pop("roleId", "") or "")
                result = self._execute_or_log(
                    f"Create user '{username}'",
                    self.arcane.create_user,
                    payload,
                )
                target_id = result.get("id", "") if isinstance(result, dict) else ""
                if role_id and target_id and not self.config.dry_run:
                    try:
                        self.arcane.set_user_role_assignments(
                            target_id, [{"roleId": role_id}]
                        )
                    except Exception as role_exc:
                        self.logger.error(
                            "User %s created but role %s was not assigned: %s",
                            username, role_id, role_exc,
                        )
                        self.ui.warning(
                            f"User '{username}' was created but role "
                            f"'{role_id}' was not assigned: {role_exc}"
                        )
                        self.report.add_action_item(
                            f"Assign the {role_id} role to '{username}' in Arcane"
                        )
                self.report.record_success("Users", username, uid, target_id)
                if not self.config.dry_run:
                    self.report.add_rollback(
                        "DELETE",
                        f"{self.arcane.base_url}/users/{target_id}",
                        f"Delete user '{username}'",
                    )
                self.report.add_action_item(
                    f"User '{username}' was created with a random password -- set a new password via Arcane admin"
                )
                self._record_migrated(phase, uid)
            except Exception as exc:
                self.logger.error("Failed to migrate user %s: %s", username, exc)
                self.report.record_failure("Users", username, str(exc))
                self.ui.error(f"User '{username}' failed: {exc}")

        self._mark_phase(phase, "completed")

    def _migrate_webhooks(self):
        """Handle webhooks -- requires manual target mapping."""
        phase = "webhooks"
        if self._phase_status(phase) == "completed":
            self.ui.info("Webhooks already handled -- skipping")
            return
        if not self._should_include("webhooks"):
            self.ui.info("Webhooks not selected -- skipping")
            self._mark_phase(phase, "completed")
            return

        self._mark_phase(phase, "in_progress")
        webhooks = self.discovery.get("webhooks", {}).get("data", [])

        for wh in webhooks:
            wh_id = str(wh.get("Id", ""))
            name = f"webhook-{wh_id}"
            self.report.record_skip(
                "Webhooks", name, "needs manual target mapping"
            )
            self.ui.warning(
                f"Webhook '{name}' skipped -- needs manual target mapping"
            )

        self._mark_phase(phase, "completed")

    def _export_ee_rbac(self):
        """Export EE RBAC data (teams, memberships, roles, resource controls)."""
        phase = "ee_rbac_export"
        if self._phase_status(phase) == "completed":
            self.ui.info("EE RBAC export already completed -- skipping")
            return
        if self.config.import_mode:
            self.ui.info("Import mode: EE RBAC data already on disk -- skipping export")
            self._mark_phase(phase, "completed")
            return
        if not self._is_ee():
            self.ui.info("Not EE edition -- skipping RBAC export")
            self._mark_phase(phase, "completed")
            return

        # If _export_to_disk already wrote EE files, skip duplicate writes
        if self._ee_exported:
            self.ui.info("EE RBAC files already written during export phase -- skipping duplicate")
            self._mark_phase(phase, "completed")
            return

        self._mark_phase(phase, "in_progress")
        base = Path(self.config.backup_dir) / "ee_reference"

        def _write(filename: str, data: Any, label: str):
            filepath = base / filename
            if not self.config.dry_run:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, indent=2, default=str)
            else:
                self.ui.dry_run_msg(f"Write {filepath}")
            count = len(data) if isinstance(data, list) else 1
            self.report.record_ee_export(label, count, str(filepath))

        if self._should_include("teams"):
            teams = self.discovery.get("teams", {}).get("data", [])
            _write("teams.json", teams, "Teams")

        if self._should_include("team_memberships"):
            try:
                memberships = self.portainer.list_team_memberships()
            except Exception:
                memberships = []
            _write("team_memberships.json", memberships, "Team Memberships")

        if self._should_include("roles"):
            roles = self.discovery.get("roles", {}).get("data", [])
            _write("roles.json", roles, "Roles")

        if self._should_include("resource_controls"):
            try:
                resource_controls = self.portainer.list_resource_controls()
            except Exception:
                resource_controls = []
            _write("resource_controls.json", resource_controls, "Resource Controls")

        self._mark_phase(phase, "completed")
        self.ui.success("EE RBAC reference exported")

    def _export_ee_audit(self):
        """Export EE audit/activity logs (optional, version-dependent)."""
        phase = "ee_audit_export"
        if self._phase_status(phase) == "completed":
            self.ui.info("EE audit export already completed -- skipping")
            return
        if self.config.import_mode:
            self.ui.info("Import mode: audit data already on disk -- skipping export")
            self._mark_phase(phase, "completed")
            return
        if not self._is_ee():
            self.ui.info("Not EE edition -- skipping audit export")
            self._mark_phase(phase, "completed")
            return
        if not self._should_include("activity_logs"):
            self.ui.info("Activity Logs not selected -- skipping audit export")
            self._mark_phase(phase, "completed")
            return

        self._mark_phase(phase, "in_progress")
        self.report.record_skip(
            "Activity Logs",
            "audit_logs",
            "Audit API varies by EE version -- skipped",
        )
        self.ui.info("EE audit export skipped (API varies by EE version)")
        self._mark_phase(phase, "completed")

    # ------------------------------------------------------------------
    # Task 12: Pre-flight checks
    # ------------------------------------------------------------------

    def preflight_checks(self) -> list:
        """Run pre-flight checks before live migration.

        Returns a list of dicts with keys: name, status (pass|warn|fail), details.
        """
        results: List[Dict[str, str]] = []

        # 1. Arcane API health
        try:
            self.arcane.health_check()
            results.append({
                "name": "Arcane API Health",
                "status": "pass",
                "details": "Arcane API is reachable and healthy",
            })
        except Exception as exc:
            results.append({
                "name": "Arcane API Health",
                "status": "fail",
                "details": f"Arcane API health check failed: {exc}",
            })

        # 2. Arcane environment accessible
        try:
            eid = self.config.arcane_environment_id or "0"
            self.arcane.get_environment(eid)
            results.append({
                "name": "Arcane Environment",
                "status": "pass",
                "details": f"Environment '{eid}' is accessible",
            })
        except Exception as exc:
            results.append({
                "name": "Arcane Environment",
                "status": "fail",
                "details": f"Cannot access Arcane environment: {exc}",
            })

        # 3. Engine on each server. Portainer and Arcane can differ.
        engine_error = ""
        try:
            self._refresh_target_engine()
        except Exception as exc:
            engine_error = str(exc)

        if self.source_engine_kind:
            results.append({
                "name": "Portainer Engine",
                "status": "pass",
                "details": engine_summary(
                    self.source_engine_kind, self.source_engine_info
                ),
            })
        else:
            details = "Portainer did not return engine info"
            if engine_error:
                details = f"{details}: {engine_error}"
            results.append({
                "name": "Portainer Engine",
                "status": "warn",
                "details": details,
            })

        target_summary = engine_summary(self.engine_kind, self.engine_info)
        if not self.engine_kind:
            details = "Arcane did not return engine info"
            if engine_error:
                details = f"{details}: {engine_error}"
            results.append({
                "name": "Arcane Engine",
                "status": "warn",
                "details": details,
            })
        elif self.same_engine:
            results.append({
                "name": "Arcane Engine",
                "status": "warn",
                "details": (
                    f"{target_summary}. Same engine confirmed "
                    f"({self.engine_match_reason}). In-place reuse is on."
                ),
            })
        elif self.engine_proven:
            results.append({
                "name": "Arcane Engine",
                "status": "warn",
                "details": (
                    f"{target_summary}. Same engine confirmed "
                    f"({self.engine_match_reason}). In-place reuse was declined."
                ),
            })
        else:
            extra = ""
            if (
                self.source_engine_kind
                and self.source_engine_kind != self.engine_kind
            ):
                extra = " Container mounts will be translated for this engine."
            reason = self.engine_match_reason
            status = "pass"
            if engine_error:
                status = "warn"
                reason = f"{reason}. {engine_error}".strip(". ")
            details = target_summary
            if reason:
                details = f"{details}. {reason}."
            if extra:
                details = f"{details}{extra}"
            results.append({
                "name": "Arcane Engine",
                "status": status,
                "details": details.strip(),
            })

        # 4. Naming conflicts
        try:
            # Networks, volumes, and projects are skipped when the name
            # already exists. A container is left in place only after the
            # user accepts same-engine reuse. Otherwise create still runs.
            left_in_place = []
            containers_created = []
            for kind, source_key, label in (
                ("projects", "stacks", "stack"),
                ("networks", "networks", "network"),
                ("volumes", "volumes", "volume"),
                ("containers", "standalone_containers", "container"),
            ):
                taken = self._target_names.get(kind, set())
                items = self.discovery.get(source_key, {}).get("data", []) or []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if kind == "containers":
                        item_name = self._resource_name(
                            item, "Names", "names", "Name", "name"
                        )
                    elif kind == "volumes":
                        item_name = item.get("Name") or item.get("name") or ""
                    else:
                        item_name = item.get("Name") or item.get("name") or ""
                    if not item_name or item_name.lower() not in taken:
                        continue
                    entry = f"{label} {item_name}"
                    if kind == "containers" and not self.same_engine:
                        containers_created.append(entry)
                    else:
                        left_in_place.append(entry)
            details_parts = []
            if left_in_place:
                details_parts.append(
                    "Already on Arcane, will be left in place: "
                    + ", ".join(left_in_place)
                )
            if containers_created:
                details_parts.append(
                    "Still created, because in-place reuse is off: "
                    + ", ".join(containers_created)
                )
            if details_parts:
                results.append({
                    "name": "Naming Conflicts",
                    "status": "warn",
                    "details": ". ".join(details_parts),
                })
            else:
                results.append({
                    "name": "Naming Conflicts",
                    "status": "pass",
                    "details": "No naming conflicts detected",
                })
        except Exception as exc:
            results.append({
                "name": "Naming Conflicts",
                "status": "warn",
                "details": f"Could not check naming conflicts: {exc}",
            })

        # 4. Disk space
        try:
            backup_parent = Path(self.config.backup_dir).parent
            backup_parent.mkdir(parents=True, exist_ok=True)
            usage = shutil.disk_usage(str(backup_parent))
            free_gb = usage.free / (1024 ** 3)
            if free_gb < 1.0:
                results.append({
                    "name": "Disk Space",
                    "status": "warn",
                    "details": f"Low disk space: {free_gb:.2f} GB free",
                })
            else:
                results.append({
                    "name": "Disk Space",
                    "status": "pass",
                    "details": f"{free_gb:.1f} GB free",
                })
        except Exception as exc:
            results.append({
                "name": "Disk Space",
                "status": "warn",
                "details": f"Could not check disk space: {exc}",
            })

        return results

    # ------------------------------------------------------------------
    # Task 12: Main orchestrator
    # ------------------------------------------------------------------

    def run(self, args=None):
        """Run the full migration wizard."""
        # Set once the report is saved and every phase is complete, so a
        # later display error cannot relabel a finished migration as failed
        # or rewrite the checkpoint.
        migration_finished = False
        exit_code = 0
        stopped_reason = ""
        try:
            # ── Phase 0: Welcome ──────────────────────────────────
            self.ui.banner()

            # Check for existing checkpoint
            cp = self.config.checkpoint_file
            if os.path.isfile(cp):
                if args and getattr(args, "resume", False):
                    resume = True
                else:
                    resume = Confirm.ask(
                        "[yellow]Existing checkpoint found.[/] Resume previous migration?",
                        default=True,
                    )
                if not resume:
                    try:
                        os.remove(cp)
                    except FileNotFoundError:
                        pass
                    self.state = self._load_state()
                    self.ui.info("Starting fresh migration")
                else:
                    self.ui.info("Resuming from checkpoint")

            # ── Check for --import-dir mode ──────────────────────
            import_dir = getattr(args, "import_dir", None) if args else None

            if import_dir:
                # ── Import mode: skip Portainer, load from disk ───
                self.config.import_mode = True
                self.config.strategy = "live"  # importing means push to Arcane
                self.config.backup_dir = import_dir  # read compose files from here

                self.ui.phase_header("1", self.PHASE_TOTAL, "Connection Setup (Import Mode)")
                self.ui.info(f"Import mode: loading from {import_dir}")
                self.ui.info("Portainer connection skipped (not needed in import mode)")

                # Arcane connection (still required)
                self.ui.ask_arcane_connection()
                self.arcane = ArcaneClient(self.config, self.logger)

                if self.config.arcane_username and self.config.arcane_password:
                    try:
                        self.arcane.login(
                            self.config.arcane_username,
                            self.config.arcane_password,
                        )
                        self.ui.success("Authenticated with Arcane")
                    except Exception as exc:
                        self.ui.error(f"Arcane login failed: {exc}")
                        return

                try:
                    version_info = self.arcane.get_version()
                    version_str = (
                        version_info
                        if isinstance(version_info, str)
                        else version_info.get("displayVersion", version_info.get("currentVersion", "unknown"))
                        if isinstance(version_info, dict)
                        else str(version_info)
                    )
                    self.ui.success(f"Connected to Arcane v{version_str}")
                except Exception as exc:
                    self.ui.diagnose_connection_error(
                        "Arcane", self.config.arcane_url, exc
                    )
                    return

                # Select Arcane environment
                try:
                    arcane_envs = self.arcane.list_environments()
                    self.config.arcane_environment_id = self.ui.select_arcane_environment(
                        arcane_envs
                    )
                except Exception as exc:
                    self.logger.debug("Could not list Arcane environments: %s", exc)
                    self.config.arcane_environment_id = "0"
                    self.ui.info("Using default Arcane environment (0)")

                # Reload the checkpoint now that the Arcane environment is known.
                # Saving earlier would replace the file with an empty-connection hash.
                self._attach_checkpoint()
                self._mark_phase("portainer_backup", "completed")

                # ── Phase 2: Discovery from disk ──────────────────
                self.ui.phase_header(2, self.PHASE_TOTAL, "Discovery (Import Mode)")
                try:
                    self.discovery = self._import_from_directory(import_dir)
                except Exception as exc:
                    self.ui.error(f"Failed to import from directory: {exc}")
                    return

                # Source kind comes from the export. Arcane is classified live.
                try:
                    self._load_engine_sides()
                except Exception as exc:
                    self.logger.warning("Engine detection failed: %s", exc)

                # Mark EE-only phases as completed on CE
                if not self._is_ee():
                    for phase in ["ee_rbac_export", "ee_audit_export"]:
                        if self._phase_status(phase) == "pending":
                            self._mark_phase(phase, "completed")

            else:
                # ── Normal mode: connect to Portainer ─────────────

                # ── Phase 1: Connection Setup ─────────────────────
                self.ui.phase_header("1", self.PHASE_TOTAL, "Connection Setup")

                # Portainer connection
                self.ui.ask_portainer_connection()
                self.portainer = PortainerClient(self.config, self.logger)

                try:
                    self.portainer.test_connection()
                    self.ui.success(f"Connected to Portainer at {self.config.portainer_url}")
                except Exception as exc:
                    self.ui.diagnose_connection_error(
                        "Portainer", self.config.portainer_url, exc
                    )
                    return

                try:
                    self.portainer.detect_edition()
                    self.ui.show_edition_panel(
                        self.config.portainer_edition,
                        self.config.portainer_version,
                    )
                    self.ui.success(
                        f"Portainer {self.config.portainer_edition} "
                        f"v{self.config.portainer_version} detected"
                    )
                except Exception as exc:
                    self.ui.error(f"Cannot detect Portainer edition: {exc}")
                    return

                try:
                    endpoints = self.portainer.list_endpoints()
                except Exception as exc:
                    self.ui.error(f"Cannot list Portainer endpoints: {exc}")
                    return
                if not endpoints:
                    self.ui.error("No Portainer endpoints found. Cannot continue.")
                    return

                self.config.portainer_endpoint_id = self.ui.select_endpoint(endpoints)
                self.portainer = PortainerClient(self.config, self.logger)

                # Arcane connection
                self.ui.ask_arcane_connection()
                self.arcane = ArcaneClient(self.config, self.logger)

                if self.config.arcane_username and self.config.arcane_password:
                    try:
                        self.arcane.login(
                            self.config.arcane_username,
                            self.config.arcane_password,
                        )
                        self.ui.success("Authenticated with Arcane")
                    except Exception as exc:
                        self.ui.error(f"Arcane login failed: {exc}")
                        return

                try:
                    version_info = self.arcane.get_version()
                    version_str = (
                        version_info
                        if isinstance(version_info, str)
                        else version_info.get("displayVersion", version_info.get("currentVersion", "unknown"))
                        if isinstance(version_info, dict)
                        else str(version_info)
                    )
                    self.ui.success(f"Connected to Arcane v{version_str}")
                except Exception as exc:
                    self.ui.diagnose_connection_error(
                        "Arcane", self.config.arcane_url, exc
                    )
                    return

                # Select Arcane environment
                try:
                    arcane_envs = self.arcane.list_environments()
                    self.config.arcane_environment_id = self.ui.select_arcane_environment(
                        arcane_envs
                    )
                except Exception as exc:
                    self.logger.debug("Could not list Arcane environments: %s", exc)
                    self.config.arcane_environment_id = "0"
                    self.ui.info("Using default Arcane environment (0)")

                try:
                    self._load_engine_sides()
                except Exception as exc:
                    self.logger.warning("Engine detection failed: %s", exc)

                # Reload the checkpoint now that both endpoints are known.
                # The load at startup ran before the URLs existed.
                self._attach_checkpoint()
                # Mark EE-only phases as completed on CE so all-done check works
                if not self._is_ee():
                    for phase in ["ee_rbac_export", "ee_audit_export"]:
                        if self._phase_status(phase) == "pending":
                            self._mark_phase(phase, "completed")

                # ── Phase 1.5: Portainer Backup ───────────────────
                skip_backup = args and getattr(args, "skip_backup", False)
                if not skip_backup:
                    self.ui.phase_header("1.5", self.PHASE_TOTAL, "Portainer Backup")
                    do_backup = Confirm.ask(
                        "Create a Portainer backup before proceeding?",
                        default=True,
                    )
                    if do_backup:
                        try:
                            self._portainer_backup()
                        except Exception as exc:
                            self.ui.error(f"Portainer backup failed: {exc}")
                            if not Confirm.ask("Continue without backup?", default=False):
                                return
                    else:
                        self.ui.warning("Skipping Portainer backup (user choice)")
                        self._mark_phase("portainer_backup", "completed")

                # ── Phase 2: Discovery ────────────────────────────
                self.discovery = self.discover()

            # ── Phase 3: Strategy Selection ───────────────────────
            self.ui.phase_header(3, self.PHASE_TOTAL, "Strategy Selection")
            if self.config.import_mode:
                self.config.strategy = "live"
                self.ui.info("Import mode: strategy forced to 'live' (push to Arcane)")
                self.ui.info(f"Backup directory: {self.config.backup_dir}")
            else:
                self.ui.ask_strategy()

            # Enforce --export-only regardless of user selection
            if not self.config.import_mode and args and getattr(args, "export_only", False):
                self.config.strategy = "export"
                self.ui.info("--export-only flag set: forcing export strategy")

            selected = self.ui.ask_scope_confirmation(
                self.discovery,
                self.config.portainer_edition,
            )
            if not selected:
                self.ui.warning("No items selected for migration. Exiting.")
                return
            self.ui.show_migration_plan(self.config)

            # ── Phase 4: Pre-Flight Checks ────────────────────────
            if self.config.strategy == "live":
                self.ui.phase_header(4, self.PHASE_TOTAL, "Pre-Flight Checks")
                results = self.preflight_checks()
                if not self.ui.show_preflight_results(results):
                    return

            # ── Phase 5: Execution ────────────────────────────────
            self.ui.phase_header(5, self.PHASE_TOTAL, "Execution")

            # Export first (skip in import mode -- data already on disk)
            if not self.config.import_mode:
                self._export_to_disk()
            else:
                self.ui.info("Import mode: skipping export (data already on disk)")

            if self.config.strategy == "live":
                # Discovery is loaded by now, so same-engine adoption can see
                # the source names. Preflight may have done this already.
                try:
                    self._refresh_target_engine()
                except Exception as exc:
                    self.logger.warning("Engine detection failed: %s", exc)
                # Ask before the progress bar. The default is to skip.
                self._skip_management_apps()
                # Build phase list dynamically
                core_phases = [
                    ("5a: Registries", self._migrate_registries),
                    ("5b: Git Repos", self._migrate_git_repos),
                    ("5c: Networks", self._migrate_networks),
                    ("5d: Volumes", self._migrate_volumes),
                    ("5e: Stacks", self._migrate_stacks),
                    ("5f: GitOps Syncs", self._migrate_gitops_syncs),
                    ("5g: Containers", self._migrate_containers),
                    ("5h: Templates", self._migrate_templates),
                    ("5i: Users", self._migrate_users),
                ]
                ee_phases: list = []
                if self._is_ee():
                    ee_phases = [
                        ("5j: Webhooks", self._migrate_webhooks),
                        ("5k: EE RBAC Export", self._export_ee_rbac),
                        ("5l: EE Audit Export", self._export_ee_audit),
                    ]
                else:
                    ee_phases = [
                        ("5j: Webhooks", self._migrate_webhooks),
                    ]
                phases = core_phases + ee_phases

                with self.ui.create_progress() as progress:
                    task = progress.add_task(
                        "Migrating...", total=len(phases)
                    )
                    for label, fn in phases:
                        progress.update(task, description=f"[cyan]{label}[/]")
                        try:
                            fn()
                        except MigrationStopped as exc:
                            # The panel was already shown. Do not ask to
                            # continue: later project creates fail the same way.
                            stopped_reason = str(exc)
                            self.logger.error(
                                "Migration stopped during %s: %s", label, exc
                            )
                            self._save_state()
                            break
                        except Exception as exc:
                            self.ui.error(f"{label} failed: {exc}")
                            self.logger.exception("Phase %s failed", label)
                            self._save_state()
                            if not Confirm.ask(
                                "Continue with remaining phases?",
                                default=True,
                            ):
                                break
                        progress.advance(task)

            # ── Phase 6: Verification & Report ────────────────────
            self.ui.phase_header(6, self.PHASE_TOTAL, "Verification & Report")
            report_file = self.report.save_report()
            self.report.report["report_file"] = report_file
            rollback_file = self.report.save_rollback_script()
            self.ui.show_final_report(
                self.report.report, self.config.portainer_edition
            )

            # Check if all phases completed before any closing instructions.
            # Those instructions are display-only. A failure there must not
            # turn a finished migration into "Migration failed".
            all_done = all(
                status == "completed"
                for status in self.state.get("phases", {}).values()
            )
            if all_done:
                try:
                    os.remove(self.config.checkpoint_file)
                except FileNotFoundError:
                    pass
                self.ui.success("Migration completed!")
                migration_finished = True
            elif stopped_reason:
                exit_code = 1
                self.ui.warning(
                    "Migration stopped. Fix the projects directory permissions "
                    "on the Arcane host, then run with --resume."
                )
            else:
                self.ui.warning(
                    "Some phases incomplete. Run with --resume to continue."
                )

            if rollback_file:
                self.ui.show_rollback_instructions(rollback_file)

        except KeyboardInterrupt:
            self._save_state()
            self.ui.warning(
                "Migration interrupted. Run with --resume to continue."
            )
        except Exception as exc:
            self.logger.exception("Unhandled error in migration engine")
            if migration_finished:
                self.ui.warning(
                    "Migration already finished. "
                    f"The closing message failed: {exc}"
                )
            else:
                self.ui.error(f"Migration failed: {exc}")
                self._save_state()
        finally:
            # Close HTTP sessions so connections aren't held open during
            # the terminal restoration that follows a Rich alternate-screen
            # teardown.
            for client in (self.portainer, self.arcane):
                try:
                    client.session.close()
                except Exception:
                    pass
        return exit_code


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="migrate",
        description="Portainer-to-Arcane Migration Tool",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume a previously interrupted migration",
    )
    parser.add_argument(
        "--import-dir",
        metavar="PATH",
        help="Import from a previously exported migration directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the migration without making changes",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Only export from Portainer; do not import into Arcane",
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip the Portainer backup step",
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        help="Path to a JSON configuration file",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser.parse_args()


def setup_logging(config: Config) -> logging.Logger:
    """Configure file (DEBUG) + console (INFO) logging. Returns the logger."""
    logger = logging.getLogger("migrate")
    logger.setLevel(logging.DEBUG)

    # Rich console handler -- INFO and above
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
    )
    rich_handler.setLevel(logging.INFO)
    logger.addHandler(rich_handler)

    # File handler -- DEBUG and above (if log_file is set)
    if config.log_file:
        fh = logging.FileHandler(config.log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(fh)

    return logger


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = parse_args()
    config = Config()
    config.detect_platform()

    if args.dry_run:
        config.dry_run = True
    if args.export_only:
        config.strategy = "export"
    if args.config:
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                cfg_data = json.load(f)
            SAFE_CONFIG_KEYS = {
                "portainer_url", "portainer_api_key", "portainer_endpoint_id", "portainer_ssl_verify",
                "arcane_url", "arcane_api_key", "arcane_username", "arcane_password",
                "arcane_environment_id", "arcane_ssl_verify",
                "strategy", "dry_run", "backup_dir", "log_file",
            }
            for key, value in cfg_data.items():
                if key in SAFE_CONFIG_KEYS:
                    setattr(config, key, value)
                else:
                    console.print(f"[yellow]Ignoring unknown config key: {key}[/]")
        except Exception as e:
            console.print(f"[red]Error loading config: {e}[/]")
            sys.exit(1)

    logger = setup_logging(config)
    logger.info("Migration tool v%s starting on %s", __version__, config.platform_name)

    try:
        engine = MigrationEngine(config, logger)
        code = engine.run(args=args)
        if code:
            sys.exit(code)
    except KeyboardInterrupt:
        console.print("\n[yellow]Migration interrupted. Run with --resume to continue.[/]")
        sys.exit(130)
    except Exception as e:
        logger.exception("Unhandled error")
        console.print(f"\n[red]Fatal error: {e}[/]")
        console.print(f"[dim]Check log file for details[/]")
        sys.exit(1)
