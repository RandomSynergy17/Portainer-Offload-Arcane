<p align="center">
  <h1 align="center">Portainer to Arcane Migration Tool</h1>
  <p align="center">
    Move your entire Docker management setup from Portainer CE/EE to
    <a href="https://getarcane.app">Arcane</a> — stacks, containers, volumes,
    registries, users, and everything in between.
  </p>
  <p align="center">
    <a href="https://github.com/RandomSynergy17/Portainer-Offload-Arcane/actions/workflows/ci.yml"><img src="https://github.com/RandomSynergy17/Portainer-Offload-Arcane/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
    <a href="https://github.com/RandomSynergy17/Portainer-Offload-Arcane/releases/latest"><img src="https://img.shields.io/github/v/release/RandomSynergy17/Portainer-Offload-Arcane?style=flat-square&color=blue" alt="Latest Release"></a>
    <img src="https://img.shields.io/badge/python-3.8%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.8+">
    <img src="https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-lightgrey?style=flat-square" alt="Platform">
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License"></a>
    <img src="https://img.shields.io/badge/portainer-CE%20%2B%20EE-13BEF9?style=flat-square&logo=portainer&logoColor=white" alt="Portainer CE + EE">
    <img src="https://img.shields.io/badge/target-Arcane-blueviolet?style=flat-square" alt="Arcane">
  </p>
</p>

---

## Why Arcane?

[Arcane](https://getarcane.app) is a modern Docker management platform built
for teams who've outgrown Portainer's limitations. It ships with GitOps syncs,
built-in vulnerability scanning, volume browsing, image builds, and a UI that
doesn't fight you. If you've been eyeing the switch, this tool makes it painless.

## What This Tool Does

A single Python file (`migrate.py`) that walks you through a guided,
interactive migration wizard. It connects to your Portainer instance, discovers
every resource, and either exports them for review or pushes them straight into
Arcane — your choice.

No downtime required. No manual YAML copying. Just run it and follow the
prompts.

---

## Quick Start

```bash
./migrate.sh
```

That's it. The launcher checks your Python version, installs dependencies
if needed, detects Docker availability, and drops you into the wizard.
It asks for your Portainer URL, API key, and Arcane credentials, then
does the rest.

> **Alternative:** `python migrate.py` does the same. When `rich` and
> `requests` are missing it creates a `.venv` next to the script and
> installs them there. On Debian/Ubuntu, install `python3-venv` first
> if Python reports that the venv module is missing.

---

## What Gets Migrated

Everything that matters:

| Resource | From Portainer | To Arcane | Edition |
|----------|---------------|-----------|---------|
| Compose Stacks | Stacks + `.env` files | Projects | CE + EE |
| Git-based Stacks | Git stack configs | GitOps Syncs | CE + EE |
| Standalone Containers | Full container inspect | Containers | CE + EE |
| Docker Volumes | Volumes + data backup | Volumes + restore | CE + EE |
| Networks | User-created networks | Networks | CE + EE |
| Container Registries | All registry types | Registries | CE + EE |
| Custom Templates | Templates + compose | Templates | CE + EE |
| Users | Accounts + roles | Users | CE + EE |
| Webhooks | Webhook configs | Webhooks | CE + EE |
| Teams / Roles / ACLs | RBAC config | Reference export | EE |
| Settings | Full config | Reference export | CE + EE |

The tool also creates a **full Portainer backup** before touching anything, so
you always have a way back.

---

## How It Works

The wizard runs through 6 phases:

```
  1. Connect       Portainer + Arcane credentials, edition detection
  2. Discover      Scan all resources, show summary table
  3. Plan          Choose strategy (export-only, live, dry-run)
  4. Pre-flight    Check Arcane health, naming conflicts, disk space
  5. Execute       Export to disk, then import to Arcane
  6. Report        Summary table, JSON report, rollback script
```

Each phase has a progress bar, colored status indicators, and clear error
messages. If something goes wrong mid-migration, checkpoint/resume picks up
exactly where you left off.

---

## Usage

All options pass through the shell launcher — it handles Python, pip, and
dependency checks automatically, then forwards everything to `migrate.py`:

```bash
# Interactive wizard (recommended)
./migrate.sh

# Export only — save everything to disk, don't touch Arcane
./migrate.sh --export-only

# Dry run — simulate the full migration, change nothing
./migrate.sh --dry-run

# Resume — pick up an interrupted migration
./migrate.sh --resume

# Import — push a previous export into Arcane (no Portainer needed)
./migrate.sh --import-dir ./migration_export

# Config file — skip the prompts
./migrate.sh --config my-config.json

# Skip backup — if you've already backed up Portainer
./migrate.sh --skip-backup

# Launcher-only: check prerequisites without starting
./migrate.sh --check-only

# Launcher-only: show help
./migrate.sh --help
```

> **Direct Python:** Every command above also works with `python migrate.py`.
> Missing packages are installed into `.venv` beside the script.

---

## Requirements

| Requirement | Notes |
|-------------|-------|
| Python 3.8+ | Auto-detected by the launcher |
| `rich` + `requests` | Installed into `.venv` on first run if missing |
| Portainer API key | Generate in Portainer > My Account > Access Tokens |
| Arcane API key or login | Admin credentials for the target instance |
| Docker CLI *(optional)* | Enables volume data backup when running on the host |

---

## Migration Modes

### Export-Only

Saves all Portainer data to `./migration_export/` without touching Arcane.
Great for auditing what you have, planning the migration, or creating a
portable backup of your entire Portainer configuration.

### Live Migration

Exports first (safety net), then imports everything into Arcane. Compose
stacks become Arcane projects, standalone containers are rebuilt with full
config fidelity, and volume data is backed up and restored.

### Dry Run

Runs the entire migration end-to-end — reads, transforms, API calls — but
skips all writes. Shows you exactly what *would* happen. Perfect for a
pre-flight check before the real thing.

### Import from Export

Already ran `--export-only`? Use `--import-dir` to push that export into
Arcane without needing a live Portainer connection. Useful when Portainer
has already been decommissioned.

---

## Features

- **Edition-aware** — auto-detects Portainer CE vs EE, adjusts available
  features, and handles graceful fallbacks for EE-only endpoints
- **Interactive wizard** — rich TUI with progress bars, colored tables,
  phase indicators, and clear prompts at every step
- **Checkpoint/resume** — interrupted mid-migration? Run `--resume` and
  pick up exactly where you left off
- **Full container fidelity** — port bindings, restart policies, resource
  limits, environment variables, volume mounts with mode preservation
- **Volume data backup** — when Docker CLI is available, backs up actual
  volume data as `.tar.gz` archives and restores them on the target
- **Portainer backup** — triggers a full Portainer backup before any
  changes, saved locally as your safety net
- **Rollback script** — generates a `rollback.sh` with the exact API
  calls to undo every resource created in Arcane
- **Security hardened** — credentials masked in logs and exports, shell
  injection protection in generated scripts, config file allowlist
- **Cross-platform** — Windows, Linux, macOS. Path handling, Docker
  socket detection, and terminal colors all adapt automatically

---

## Config File

Skip the interactive prompts by providing a JSON config:

```json
{
    "portainer_url": "https://portainer.example.com:9443",
    "portainer_api_key": "ptr_...",
    "portainer_endpoint_id": 1,
    "arcane_url": "https://arcane.example.com:3552",
    "arcane_api_key": "...",
    "arcane_environment_id": "0",
    "strategy": "live",
    "dry_run": false,
    "backup_dir": "./migration_export",
    "log_file": "./migration.log"
}
```

---

## Export Directory

When you run `--export-only` or as part of any live migration, the tool
creates a structured export:

```
migration_export/
├── manifest.json                    # What was exported, when, from where
├── portainer_backup/
│   └── portainer_backup.tar.gz      # Full Portainer backup
├── stacks/
│   ├── my-app/
│   │   ├── docker-compose.yml       # Compose file
│   │   ├── .env                     # Environment variables
│   │   └── metadata.json            # Stack metadata from Portainer
│   └── monitoring/
│       ├── docker-compose.yml
│       ├── .env
│       └── metadata.json
├── containers/
│   └── standalone.json              # Full inspect data for each container
├── registries/
│   └── registries.json              # Registry configs (credentials masked)
├── networks/
│   └── networks.json
├── volumes/
│   ├── volumes.json
│   └── backups/                     # Actual volume data (when Docker available)
│       ├── postgres_data.tar.gz
│       └── redis_data.tar.gz
├── templates/
│   └── custom_templates.json
├── users/
│   └── users.json                   # Accounts (passwords not included)
├── webhooks/
│   └── webhooks.json
├── settings/
│   └── portainer_settings.json      # Full settings (secrets masked)
└── ee_reference/                    # EE only
    ├── teams.json
    ├── team_memberships.json
    ├── roles.json
    └── resource_controls.json
```

---

## FAQ

**Will this cause downtime?**
No. The tool reads from Portainer and writes to Arcane. Your running
containers are not stopped or restarted during migration.

**Can I test it first?**
Yes. Use `--dry-run` to simulate everything without making changes, or
`--export-only` to just save your data locally.

**What if something goes wrong?**
The tool creates a full Portainer backup before starting. It also
generates a `rollback.sh` script that can undo every resource it
created in Arcane. And checkpoint/resume means you never lose progress.

**Does it work with Portainer CE and EE?**
Both. The tool auto-detects your edition and adjusts accordingly.
EE-specific features (webhooks, teams, roles) are handled when
available and gracefully skipped on CE.

**Can I migrate from an export without a live Portainer?**
Yes. Run `--export-only` while Portainer is still up, then later use
`--import-dir ./migration_export` to push into Arcane — no Portainer
connection needed.

---

## Versioning

This project uses [Semantic Versioning](https://semver.org/).
See [CHANGELOG.md](CHANGELOG.md) for release history.

## License

MIT

---

<p align="center">
  <sub>Built for the move from Portainer to <a href="https://getarcane.app">Arcane</a>.</sub>
  <br>
  <sub>A <a href="http://randomsynergy.com">RandomSynergy Productions</a> project.</sub>
</p>
