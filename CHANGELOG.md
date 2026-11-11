# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.1] - 2026-11-10

### Added
- **Same-engine adoption, including Podman, only when an ID matches.**
  In-place reuse runs only after a full 64-character container or network ID
  is present on both Portainer and Arcane, or both Docker info IDs are equal.
  Matching container names are not treated as the same server. Podman's info
  ID changes on every query, so a mismatch there is ignored. When the IDs do
  match, the wizard asks before reusing containers, networks, and volumes.
  The answer is stored in the checkpoint, so `--resume` keeps it.
  Adopted resources are not copied and are not added to the rollback script.
  Podman is recognized when the engine root is `/var/lib/containers`.

### Changed
- **Portainer and Arcane's own apps are skipped unless you say otherwise.**
  One prompt lists a container or stack that is Portainer (`portainer/portainer`,
  `portainer/agent`, or the exact name `portainer`) or Arcane
  (`getarcaneapp/arcane`, or the exact name `arcane`). The default is to
  skip them, so pressing Enter leaves those management apps out of the
  migration. Answering no migrates them with the workloads. A name that
  only contains those words, such as `portainer-proxy`, is still migrated.
  The answer is stored in the checkpoint. Arcane's containers already
  running on the destination are not in the Portainer inventory, so they
  are not recreated.
- **Portainer and Arcane engines are detected separately.** Each server's
  `/info` is classified as Docker or Podman. The wizard prints both after
  the connections succeed, and the preflight table has a row for each.
  When the kinds differ, container mounts are translated for the Arcane
  engine: a Podman socket becomes `/var/run/docker.sock` on Docker, and a
  Docker socket becomes `/run/podman/podman.sock` on Podman. When both
  servers are the same kind, the socket path is left as it is. A volume
  `_data` directory from either engine is mounted by volume name. The
  export records the Portainer engine so a later import still knows it.
  The banner line "Local Docker CLI" is the wizard machine, used for
  volume backup, and is separate from either server.
- **Connection prompts default to localhost.** Portainer defaults to
  `https://localhost:9443/` and Arcane defaults to `http://localhost:3552/`.
- **SSL verification defaults to no for a private address.** When the
  Portainer URL host is a private, loopback, or link-local IP, "Verify SSL
  certificate?" defaults to no. A hostname still defaults to yes. Pressing
  Enter accepts the shown default.
- **Dependencies install into `.venv`.** `migrate.py` and `migrate.sh` create
  a virtual environment next to the script instead of pip-installing into
  system Python. When the `venv` module is missing, they tell you to install
  `python3-venv` (Debian/Ubuntu) or the `dnf` equivalent.

### Fixed
- **Podman bind modes are accepted by Docker.** Podman records kernel mount
  flags such as `rbind`, `nosuid`, and `nodev` on `HostConfig.Binds`.
  Docker rejects the whole string with `invalid mode`. Container creates
  now keep only the modes Docker accepts. Propagation stays on a host
  path and is omitted from a named volume, which rejects `BindOptions`.
  A Podman socket bind is rewritten to `/var/run/docker.sock` when Arcane
  is Docker and Portainer is Podman, or when the Portainer engine was not
  detected. A Docker socket is rewritten to the Podman socket when Arcane
  is Podman. When both servers are the same kind, the socket path stays.
  Named volumes are mounted by volume name, not by the source host path
  under `/var/lib/containers` or `/var/lib/docker`.
- **A name that already exists is left in place.** A fresh Arcane install
  already has its own `arcane_default` network. Creating it again returned
  409 and was counted as a failed network. The wizard skips networks,
  volumes, and projects that are already on Arcane, does not add a
  rollback delete for them, and the preflight naming check lists those
  names. A container is listed as left in place only when in-place reuse
  is on. Otherwise the preflight row says that container will still be created.
- **A projects-directory permission error stops the migration.** When
  Arcane cannot create a project because its projects directory (often
  `/opt/docker`) is not writable by the Arcane user, the wizard records
  that stack, prints the ownership fix, and stops. Later stacks,
  containers, and users are not attempted. The stacks phase stays
  incomplete, so `--resume` retries it after the directory is writable.
  The report and rollback script are still written for resources already
  created. The process exits with status 1.
- **A resumed run keeps the checkpoint.** The wizard asks for URLs before
  it can tell which file belongs to this connection. It used to save a new
  checkpoint from that empty start and overwrite the real one, so `--resume`
  repeated finished work and asked the in-place question again. The saved
  file is loaded once the Portainer endpoint and Arcane environment are
  known, when its connection hash matches.
- **Unverified HTTPS no longer prints a warning on every request.**
  Answering no to "Verify SSL certificate?" silences urllib3's
  `InsecureRequestWarning`. Certificate verification stays off for that
  connection.
- **A finished migration was reported as failed.** After the report and
  `rollback.sh` were written, the wizard printed rollback instructions
  through `MigrationEngine.console`, which does not exist. The resources
  had already been migrated, and the rollback script was not executed.
  The instructions now go through the wizard UI and say the script was
  only written. A display error after every phase is complete no longer
  prints "Migration failed" or rewrites the checkpoint.
- **Arcane 2.17 user create rejected `roles`.** `POST /users` returns
  `422 unexpected property` for a `roles` field, so every Portainer user
  failed at the end of an otherwise in-place migration. The account is
  created without that field, then the administrator or editor role is
  applied with `PUT /users/{id}/role-assignments`.
- **Arcane 2.x project create is multipart.** `POST /environments/{id}/projects`
  rejects an `application/json` body with `422 cannot read multipart form`.
  Stacks are now sent as the `project` and `manifest` form parts Arcane's UI
  uses, so compose projects are actually created. Creating a project does not
  redeploy it. When the compose project name matches containers already
  running on that engine, Arcane attaches the project to them.

## [0.4.0] - 2026-04-21

### Fixed
- **Arcane registry payload now includes AWS fields on every registry
  type**. `CreateContainerRegistryRequest` marks `awsAccessKeyId`,
  `awsSecretAccessKey`, and `awsRegion` as required fields for every
  registry type, not just ECR. `_transform_registry` previously omitted
  them for Docker Hub / Quay / Azure ACR / GitLab / custom registries,
  so every non-ECR POST violated the schema. The three fields are now
  always present — populated from Portainer's `Ecr` block for ECR,
  empty strings otherwise.
- **Credentials no longer leak to the debug log**. `ArcaneClient._request`
  and `MigrationEngine._execute_or_log` previously logged request bodies
  verbatim, echoing registry passwords, user passwords, git tokens, and
  AWS keys into the on-disk log file. Both paths now redact any value
  under a secret-looking key.
- **Checkpoint writes are atomic**. `_save_state` now writes to a sibling
  temp file, fsyncs, and `os.replace`s. The previous non-atomic write
  could be truncated by an interrupt, which combined with the silent
  reset below caused every already-migrated item to be re-created on
  `--resume`.
- **A corrupt checkpoint fails loud** instead of silently falling back
  to fresh state. The old behaviour produced duplicate Arcane resources.
- **Portainer backup streams to disk** with a 600s timeout. The previous
  in-memory `resp.content` at 120s OOM'd or timed out on real-world
  installs.
- **Arcane volume-backup upload timeout scales to file size** (10-minute
  floor, 4-hour cap) instead of a fixed 60s that silently truncated
  multi-GB tarballs.
- **Every Arcane list endpoint now paginates**. Arcane's default page
  size is 20; previously the tool silently stopped at 20 items per
  resource type. Added `_list_paginated` that loops through the
  start/limit response shape and wires it into `list_environments`,
  `list_registries`, `list_git_repos`, `list_projects`, `list_networks`,
  `list_volumes`, `list_containers`, `list_users`, `list_webhooks`,
  `list_templates`.
- **Silent stack compose-file fetch failures are now reported**. Previous
  bare `except Exception` wrote an empty `docker-compose.yml` with no
  warning. Now logs, records a migration failure, and warns the user.
- **Volume-backup upload failures and container-start failures** are now
  recorded as migration failures so the final report surfaces them.
  Previously both were only warnings, producing reports that claimed
  success for resources whose data or runtime state was actually missing.
- **Transient Portainer errors retry with exponential backoff**.
  `PortainerClient._get` retries `ConnectionError` / `Timeout` up to
  three times (1s / 2s / 4s). HTTP 4xx/5xx are not retried.
- **Discovery tolerates per-resource failure**. `MigrationEngine.discover`
  records a "discovery failed" marker for a single flaky endpoint
  instead of aborting the whole phase.
- **403 on Portainer is surfaced as a warning** rather than silently
  degrading to empty like 404 (which only means "EE-only endpoint
  missing on CE"). A 403 usually means the API key is missing permission
  and the data would otherwise be invisibly incomplete.
- **Endpoint/environment pickers no longer clamp invalid input** — they
  loop until a valid row number is entered. Clamping a destructive target
  selection to the first/last row was a foot-gun.
- **Dependency bootstrap no longer hides pip errors**. Dropped
  `--quiet`, caught `EOFError` on non-TTY stdin, and replaced `os.execv`
  with a subprocess spawn (Windows semantics for `os.execv` differ).
- **Reverse-proxy HTML error pages now raise a clear message** instead
  of an opaque `JSONDecodeError`.
- **HTTP sessions close in a `finally` block** so connections don't
  linger through Rich's terminal teardown.
- **Checkpoint cleanup TOCTOU** — `os.remove(cp)` paths guard against
  `FileNotFoundError`.

### Changed
- **`migrate.sh` Python detection** now probes
  `/opt/homebrew/bin/python3`, `/usr/local/bin/python3`, `/usr/bin/python3`,
  and `py -3` in addition to `PATH` entries. Previously a fresh macOS
  without Homebrew's shims on `PATH` failed with "Python not found".
- **`migrate.sh` pip failures are visible** (no more `--quiet`). Adds a
  PEP 668 ("externally-managed-environment") hint when pip install fails,
  so Ubuntu 24.04 / modern Homebrew users know to reach for a venv.
- **`migrate.sh` Docker probe** distinguishes "Docker CLI missing" from
  "daemon not running" from "socket permission denied" and prints the
  relevant fix for each.
- **Phase headers show a persistent [DRY RUN] or [EXPORT-ONLY] badge**
  so the active mode is visible on every phase, not just at launch.
- **Connection errors print targeted hints** (SSL, DNS, connection
  refused, 401/403, timeout, http:// scheme) via a new
  `WizardUI.diagnose_connection_error` helper.
- **Rollback script instructions** surface in the final report so users
  know to paste their Arcane API key in place of `YOUR_API_KEY_HERE`
  before running `rollback.sh`.

## [0.3.0] - 2026-04-11

### Added
- `--import-dir PATH` feature: import from a previously exported migration directory
  - Skips Portainer connection entirely (no Portainer URL/API key needed)
  - Reads discovery data from exported JSON files and manifest.json
  - Reads compose files from disk instead of calling Portainer API
  - Reads container inspect data from standalone.json instead of Portainer API
  - Reads custom template content from exported data instead of Portainer API
  - Forces strategy to "live" (push to Arcane)
  - Still requires Arcane connection for the target environment
- `config.import_mode` flag on Config dataclass

## [0.2.0] - 2026-04-11

### Added
- `migrate.sh` launcher script
  - `--help` with full usage, options, examples, and prerequisites
  - `--check-only` to validate environment without launching
  - Checks Python 3.8+ availability across `python3` and `python` candidates
  - Checks and installs pip via `ensurepip` if missing
  - Auto-installs `rich` and `requests` from `requirements.txt`
  - Detects Docker availability and reports mode (local vs API-only)
  - Passes all CLI args through to `migrate.py` (strips launcher-only flags)
  - Color output with graceful degradation on non-TTY
  - Platform-specific install guidance (macOS/Linux/Windows)
- `WizardUI`: Rich TUI wizard with phase headers, progress bars, tables, edition panels
- `ReportGenerator`: JSON migration report, rollback shell script generation
- `MigrationEngine`: Full orchestrator with checkpoint/resume, discovery, transforms, export, live migration
  - 13 migration phases (portainer backup, registries, git repos, networks, volumes, stacks, GitOps syncs, containers, templates, users, webhooks, EE RBAC export, EE audit export)
  - Export-to-disk with full directory structure
  - Edition-aware CE/EE branching throughout
  - Pre-flight checks (Arcane health, naming conflicts, disk space)
  - Full-fidelity container transform (capabilities, health checks, devices, DNS, resource limits, mount modes)
- Main entry point wiring with config file loading and error handling
- `.gitignore` for Python cache, runtime artifacts, env files
- `docs/plans/` with complete implementation plan (design, UI/UX wireframes, API mappings)
- `README.md`, `CHANGELOG.md`, `CLAUDE.md` documentation

## [0.1.0] - 2026-04-11

### Added
- Initial project scaffold (`migrate.py`, `requirements.txt`)
- `Config` dataclass with Portainer CE/EE + Arcane connection settings, platform detection
- CLI argument parsing (`--resume`, `--import-dir`, `--dry-run`, `--export-only`, `--skip-backup`, `--config`)
- Dual logging: Rich console (INFO) + file (DEBUG)
- `PortainerClient` with all CE+EE read-only API methods
  - Edition auto-detection via `GET /api/status`
  - `_safe_get()` for graceful 404 handling on EE-only endpoints
  - Docker proxy methods (containers, images, volumes, networks)
  - Portainer backup trigger (`POST /api/backup`)
  - EE-only: webhooks, teams, roles, resource controls, edge stacks
- `ArcaneClient` with all read/write API methods
  - Dual auth: API key (`X-API-Key`) or JWT Bearer token
  - Full CRUD: environments, registries, git repos, projects, GitOps syncs,
    networks, volumes (+ backup upload), containers, users, webhooks,
    notifications, settings, templates
- `DockerLocal` for local Docker socket operations
  - Volume backup via `docker run alpine tar czf`
  - Volume size estimation
  - Compose container listing by project label
