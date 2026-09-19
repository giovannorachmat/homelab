# AGENTS.md

## Repo shape
- Docker Compose homelab, not an app monorepo: `services/*/docker-compose.yml` defines containers; `runtime/` holds persistent/private state.
- Treat compose files as the source of truth when README status/ports/resource numbers disagree (README table is hand-maintained).
- Most services join the external Docker network `private-net`; missing the top-level `networks: private-net: external: true` creates an isolated network and breaks container-name routing.
- Compose service keys differ from container names in a few places: npm's service key is `app` (container `npm`), and monitoring containers carry `monitoring-` prefixes (service `prometheus` → container `monitoring-prometheus`). `docker compose` commands use the service key; NPM proxy hosts and cross-stack DNS use container names (Grafana's datasources use the service-name aliases `prometheus`/`loki`, which survive renames).
- Ollama replaced its native Debian/systemd install (root unit `ollama.service` stopped + disabled, it was squatting 127.0.0.1:11434); port 11434 belongs to the compose service. The compose bind-mounts the host model dir `/usr/share/ollama/.ollama` (25G of existing models), not `runtime/ollama/data` — don't "fix" it back to the runtime convention.

## Commands
- Start/stop/logs one service: `docker compose -f services/<service>/docker-compose.yml up -d` / `down` / `logs -f`
- Verify running containers/resources: `docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"` and `docker stats --no-stream`
- After editing any `runtime/**/.env`, run `./scripts/generate-env-examples.sh` to refresh committed `.env.example` files.
- Validate compose changes without deploying: `docker compose -f services/<service>/docker-compose.yml config`

## Secrets and state
- Never commit real `.env` files, `runtime/**/data/`, `runtime/**/conf/`, `runtime/**/work/`, `runtime/**/letsencrypt/`, `runtime/syncthing/config/`, or `runtime/certs/`; `.gitignore` encodes this split.
- Only `runtime/**/.env.example` is meant for git; the generator replaces values with placeholders but preserves comments/blank lines.
- `runtime/syncthing/config/config.xml` holds secrets (API key, device IDs) plus TLS private keys (`key.pem`, `https-key.pem`). The API key there drives Syncthing's `/rest/config` API, which is how to fix config or GUI auth without restarting the container.

## Compose conventions and gotchas
- NPM is the production reverse proxy on host ports 80/443/81; proxy hosts must forward to container names and container ports, not host-mapped ports.
- `services/9router` builds from sibling repo `../../../9router/`; `services/crawl4ai` builds `crawl4ai-proxy` from `../../../../repo/crawl4ai-proxy` (paths relative to the compose file; both live outside this repo).
- Every service defines `deploy.resources` limits/reservations; follow this pattern for new services (32GB RAM mini PC host).
- Most images float on `:latest`/`main` tags; a re-pull can silently jump major versions (2026-08-29: tika 3.3.1→4.0.0 crash-looped; 2026-09-18: same jump broke Open WebUI PDF uploads until `rag.tika_server_version` was set to 4 — tika is now pinned to `4.0.0` and the pin must stay in sync with that setting). After an image update, `docker compose up -d` can be a no-op because the config-hash still matches — fix with `up -d --force-recreate`.
- Docker `env_file` reads quotes literally; avoid quoting simple values in `.env`, especially semicolon-separated provider lists.
- Monitoring config mounts are mixed: prometheus.yml + Grafana provisioning are tracked under `services/monitoring/config/`, while promtail.yml and loki-config.yaml are mounted from `runtime/monitoring/config/`; check the compose mounts before editing the wrong copy. Monitoring state lives in the `monitoring_*` named volumes (prometheus, grafana, loki storage) — `docker compose down -v` destroys them and there is no backup (2026-09-19 incident: `down -v` during the `monitoring-` rename wiped the Prometheus TSDB and Grafana DB).
- Open WebUI's Admin Panel settings win over its compose env: they live as JSON-encoded rows in the `config` table of `runtime/open-webui/data/webui.db` (400+ keys, e.g. `rag.*`). The container exposes no host port — inspect/change via `docker exec open-webui python` (no sqlite3 CLI, but Python is present), and after a raw DB write restart the container or `POST /api/v1/retrieval/config/update` on localhost:8080, else the running app keeps stale in-memory state (2026-09-19: reranker written to DB only → query-time crash until the update endpoint reloaded it).
- Syncthing is the one exception to the `runtime/` data convention: its data mount is the absolute host path `/home/giografi/syncthing` → `/data`. Folder paths set in the Syncthing GUI must be container paths (`/data/<name>`) to land in `~/syncthing`; host paths like `/home/giografi/...` fail inside the container. Adding a folder never requires editing the compose file.
- Syncthing replaced the native Debian package install (user systemd unit `syncthing.service` stopped + disabled); ports 8384/22000/21027 belong to the compose service. If they conflict, check `systemctl --user status syncthing`.

## Focused validation
- There is no repo-wide test/lint/typecheck setup; `docker compose config` (above) is the verification step.
- For live checks, use published host ports (Prometheus 9090, Loki 3100, Grafana 3030) or container names on the stack's own network; cross-stack routing depends on `private-net`. The Loki image has no shell/`cat` — use `docker cp monitoring-loki:/path/file` to read files from it.
- For port changes, check conflicts with `ss -tlnp | grep -E ':(80|443|9080|9443|<port>) '`.
- README.md's Troubleshooting section documents known incidents (NPM 502, `.env` quotes, private-net isolation, the Tika 3→4 upload break, host hard-resets); check it before debugging those symptoms.
