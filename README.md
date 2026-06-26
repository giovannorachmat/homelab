# Homelab

This is a personal homelab running on a mini PC at home. I use it to learn Docker, networking, reverse proxies, monitoring, and everything else a good DevOps engineer should know (though at the time of this writing, I'm not a DevOps engineer). Everything runs on a single machine behind a Cloudflare DNS, accessible from anywhere via subdomains on `giografi.my.id`.

**Current status:**
- 8 services running (AdGuardHome, NPM, Ollama, Open WebUI, Traefik, crawl4ai, 9router, tika)
- 5 services defined but not started (n8n, drawio, floci, monitoring)
- All behind NPM reverse proxy with Let's Encrypt SSL

---

## Table of Contents

- [Hardware](#hardware)
- [Services](#services)
- [Directory Layout](#directory-layout)
- [Quick Start](#quick-start)
- [Architecture & Design Decisions](#architecture--design-decisions)
- [Operations](#operations)
- [Reference](#reference)
- [Troubleshooting](#troubleshooting)

---

## Hardware

| Spec | Value |
|------|-------|
| **Machine** | Lenovo M715q (mini PC) |
| **CPU** | AMD Ryzen 5 2400GE, 3.2 GHz, 4 cores / 8 threads |
| **RAM** | 16 GB |
| **Storage** | 128 GB SSD |
| **OS** | Ubuntu 24.04.4 LTS (Noble Numbat) |
| **Hostname** | `lenovo-m715q` |

This is not a beefy server. Every service has strict resource limits. If you add something heavy, you will run out of memory or disk. Check `docker stats` and `df -h` regularly.

**Disk usage:** Root filesystem at 81% (88GB / 115GB used, 22GB free). Be careful with log files, model downloads, and Docker images.

---

## Services

| Service | Image | Host Ports | CPU / RAM Limits | Purpose | Status |
|---------|-------|-----------|------------------|---------|--------|
| **AdGuardHome** | `adguard/adguardhome:latest` | 53 (DNS) | 0.5 / 250M | DNS ad-blocker | Running |
| **NPM** | `jc21/nginx-proxy-manager:2.15.1` | 80, 81, 443 | 0.5 / 250M | Reverse proxy + SSL | Running |
| **Ollama** | `ollama/ollama:latest` | 11434 | 0.5 / 256M | LLM inference (cloud proxy) | Running |
| **Open WebUI** | `ghcr.io/open-webui/open-webui:main-slim` | (internal only) | 1 / 1G | Chat interface for LLMs | Running |
| **Traefik** | `traefik:latest` | 9080, 9443 | 0.25 / 128M | Reverse proxy (learning) | Running |
| **n8n** | `docker.n8n.io/n8nio/n8n` | 5678 | 1 / 1G | Workflow automation | Not started |
| **Drawio** | `jgraph/drawio` | (none) | 0.5 / 256M | Diagramming tool | Not started |
| **Floci** | `floci/floci:latest` | 4566 | 0.5 / 256M | Local AWS emulator | Not started |
| **Tika** | `apache/tika:latest` | 9998 | 1 / 2G | Content extraction framework | Running |
| **Monitoring** | Multiple | 3030, 9090, 9091, 9100, 3100 | ~2.5G total | Grafana + Prometheus + Loki | Not started |
| **9router** | Build from local source | 20128 | 1 / 1G | API routing & proxy | Running |
| **crawl4ai** | `unclecode/crawl4ai:latest` + proxy | (internal only) | 1.5 / 3G | Web crawling & content extraction | Running |

**Total resources if everything runs:** ~13 GB RAM, ~9 CPU cores. On a 16GB / 8-thread machine, the machine is at capacity — not everything can run simultaneously.

---

## Directory Layout

```
/home/giografi/homelab/
├── services/                  # Docker Compose files + configs (what to run)
│   ├── 9router/
│   │   └── docker-compose.yml
│   ├── adguardhome/
│   │   └── docker-compose.yml
│   ├── crawl4ai/
│   │   └── docker-compose.yml
│   ├── drawio/
│   │   └── docker-compose.yml
│   ├── floci/
│   │   └── docker-compose.yml
│   ├── tika/
│   │   └── docker-compose.yml
│   ├── monitoring/
│   │   ├── config/            # Prometheus, Grafana, Promtail configs
│   │   └── docker-compose.yml
│   ├── n8n/
│   │   └── docker-compose.yml
│   ├── npm/
│   │   └── docker-compose.yml
│   ├── ollama/
│   │   └── docker-compose.yml
│   ├── open-webui/
│   │   └── docker-compose.yml
│   └── traefik/
│       └── docker-compose.yml
│
└── runtime/                   # Persistent data for containers (what to keep)
    ├── 9router/
    │   ├── .env               # JWT secret, API keys, cloud sync config
    │   └── data/
    ├── adguardhome/
    │   ├── conf/              # AdGuardHome config (AdGuardHome.yaml)
    │   └── work/              # AdGuardHome runtime data
    ├── certs/                 # TLS certificates (Tailscale, home.lan wildcard)
    ├── crawl4ai/
    │   ├── .env               # API token
    │   └── data/
    ├── floci/
    │   ├── data/
    │   └── .env               # AWS credentials (test)
    ├── tika/
    │   └── data/
    ├── monitoring/
    │   ├── config/
    │   └── .env
    ├── n8n/
    │   └── data/
    ├── npm/
    │   ├── data/              # NPM database, logs, nginx configs
    │   └── letsencrypt/       # SSL certificates from Let's Encrypt
    ├── ollama/
    │   └── .env               # Cloud API key
    └── open-webui/
        ├── data/              # SQLite DB, uploads, vector DB
        └── .env               # API keys for AI providers
```

**Why two folders?** `services/` = code (version controlled, shared). `runtime/` = state (backed up, picked up on re-create). See [Architecture & Design Decisions](#why-bind-mounts-instead-of-docker-volumes) for why bind mounts instead of Docker volumes.

---

## Quick Start

### Prerequisites

1. **Docker + Docker Compose**
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER   # log out and back in after
   ```

2. **A domain name** — I use `giografi.my.id`. Point an A record to your server's public IP.

3. **Cloudflare (or similar DNS)** — set SSL mode to "Full (Strict)" and enable proxy (orange cloud) for subdomains.

4. **Basic terminal comfort** — you should be comfortable with `cd`, `ls`, `cat`, `nano`/`vim`.

### Steps

```bash
# 1. Create directories
mkdir -p /home/giografi/homelab/{services,runtime}

# 2. Create the shared Docker network
docker network create private-net

# 3. Create .env files
mkdir -p runtime/open-webui runtime/ollama

cat > runtime/open-webui/.env << 'EOF'
OPENAI_API_KEY=your-openai-key-here
OPENROUTER_API_KEY=your-openrouter-key-here
HF_TOKEN=your-huggingface-token-here
ANTHROPIC_API_KEY=your-anthropic-key-here
DEEPSEEK_API_KEY=your-deepseek-key-here
EOF

cat > runtime/ollama/.env << 'EOF'
OLLAMA_API_KEY=your-ollama-cloud-key-here
EOF

# 4. Start core services (NPM first — it binds port 80/443)
docker compose -f services/npm/docker-compose.yml up -d
docker compose -f services/adguardhome/docker-compose.yml up -d
docker compose -f services/ollama/docker-compose.yml up -d
docker compose -f services/open-webui/docker-compose.yml up -d

# 5. Verify
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

You should see `adguardhome`, `npm`, `ollama`, and `open-webui` (health: starting → healthy after ~30s).

### DNS Setup

In Cloudflare, create A records:

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | `@` | `YOUR.SERVER.IP` | Yes |
| A | `adguard` | `YOUR.SERVER.IP` | Yes |
| A | `npm` | `YOUR.SERVER.IP` | Yes |
| A | `ai` | `YOUR.SERVER.IP` | Yes |

### NPM Proxy Hosts

1. Open `http://YOUR.SERVER.IP:81` → login with `admin@example.com` / `changeme` → **change immediately**
2. Go to **Proxy Hosts** → **Add Proxy Host**
3. For each service:

| Domain | Forward Host | Forward Port | WebSocket |
|--------|-------------|-------------|-----------|
| `adguard.giografi.my.id` | `adguardhome` | `80` | No |
| `npm.giografi.my.id` | `npm` | `81` | No |
| `ai.giografi.my.id` | `open-webui` | `8080` | **Yes** |

4. Enable **SSL** → Let's Encrypt → Request new certificate → **Force SSL**

### Verify

- `https://adguard.giografi.my.id` → AdGuardHome admin
- `https://npm.giografi.my.id` → NPM admin
- `https://ai.giografi.my.id` → Open WebUI chat

### Sync .env templates for Git

After editing any `.env` file, regenerate the templates:

```bash
./scripts/generate-env-examples.sh
```

Only `.env.example` files are committed — real `.env` files are ignored by `.gitignore`.

---

## Architecture & Design Decisions

### Networking

#### The private-net

All containers share a single Docker bridge network called `private-net`. This lets them talk to each other by container name (e.g., Open WebUI connects to Ollama via `http://ollama:11434`).

```
                    ┌─────────────────────────────────────┐
                    │           private-net                │
                    │                                      │
  Client ──→ NPM ──┤──→ adguardhome:80                    │
  (internet)       │──→ open-webui:8080                    │
                    │──→ ollama:11434                       │
                    │──→ traefik:80                         │
                    │                                      │
                    └─────────────────────────────────────┘
```

#### Port mapping

When you see `ports: "9080:80"` in a compose file:

```
host_port : container_port
```

- `9080` = port on the host machine (what you access from outside)
- `80` = port inside the container (what the app listens on)

**Common mistake:** NPM forwards to the **container port**, not the host port.

#### NPM reverse proxy flow

When you visit `https://ai.giografi.my.id`:

1. Browser sends HTTPS request to `YOUR.SERVER.IP:443`
2. NPM receives it on port 443
3. NPM matches domain `ai.giografi.my.id` to a proxy host
4. NPM forwards to `open-webui:8080` (container name + container port)
5. Open WebUI responds
6. NPM sends the response back to your browser

#### Why AdGuardHome admin port is commented out

I commented out `8080:80` in the AdGuardHome compose file. This means you **cannot** access the admin panel directly via `http://YOUR.IP:8080` — you must go through NPM at `https://adguard.giografi.my.id`. This ensures all admin access goes through HTTPS with authentication.

#### Why drawio has no host ports

Drawio's container listens on port 8080 internally, same as AdGuardHome's commented-out port. If I exposed both, they'd conflict. I access drawio only through NPM at `https://drawio.giografi.my.id`.

#### Traefik vs NPM

I run both reverse proxies. NPM on standard ports (80/443) for production. Traefik on alt ports (9080/9443) for learning. Check port availability before starting a new proxy:

```bash
ss -tlnp | grep -E ':(80|443|9080|9443) '
```

### Why a single Docker network?

I'm a beginner. A single `private-net` is simpler to manage, debug, and reason about. I can split it later (e.g., `monitoring-net`, `ai-net`, `proxy-net`) when I outgrow it. For now, `docker network inspect private-net` shows everything in one place.

### Why NPM instead of just Traefik?

NPM has a web UI for managing proxy hosts — I can add domains, SSL certs, and advanced configs without editing YAML. Traefik auto-discovers containers, but I want to learn the manual way first.

### Why bind mounts instead of Docker volumes?

Docker volumes are opaque — you need `docker volume inspect` to find where data lives. Bind mounts put everything in a predictable path I can `ls`, `cat`, and `tar`. Easier to manage and back up for a homelab.

### Why cloud-only Ollama?

I don't have a GPU. Running LLMs locally on CPU would be painfully slow. Ollama supports cloud models (like `gemma4:31b-cloud`) that run on Ollama's servers but use the same API. I get the Ollama experience without the hardware.

### Why AdGuardHome uses two ports (3000 and 80)?

Port 3000 is for the first-launch setup wizard only. After setup completes, it switches to port 80. The container maps both — `3000:3000` during setup, and (commented out) `8080:80` after setup. Complete the wizard first, then access via NPM.

### Open WebUI provider fallback

Open WebUI supports multiple AI providers via `OPENAI_API_BASE_URLS` and `OPENAI_API_KEYS` (semicolon-separated lists). It also supports single-provider fallback via `OPENAI_API_BASE_URL` and `OPENAI_API_KEY`. I have both configured because the multi-provider vars had DB corruption issues — the single-provider vars work as a fallback.

---

## Operations

### Start everything

```bash
# Core services
docker compose -f services/npm/docker-compose.yml up -d
docker compose -f services/adguardhome/docker-compose.yml up -d
docker compose -f services/ollama/docker-compose.yml up -d
docker compose -f services/open-webui/docker-compose.yml up -d

# Optional: Traefik (learning)
docker compose -f services/traefik/docker-compose.yml up -d

# Optional services
docker compose -f services/9router/docker-compose.yml up -d
docker compose -f services/n8n/docker-compose.yml up -d
docker compose -f services/crawl4ai/docker-compose.yml up -d
docker compose -f services/drawio/docker-compose.yml up -d
docker compose -f services/floci/docker-compose.yml up -d
docker compose -f services/tika/docker-compose.yml up -d
docker compose -f services/monitoring/docker-compose.yml up -d
```

### Stop / restart

```bash
# Stop
docker compose -f services/<service>/docker-compose.yml down

# Restart
docker compose -f services/<service>/docker-compose.yml restart

# Full restart (down + up)
docker compose -f services/<service>/docker-compose.yml down && \
docker compose -f services/<service>/docker-compose.yml up -d
```

### View logs

```bash
# Follow mode
docker logs -f <container_name>

# Last 100 lines
docker logs --tail 100 <container_name>

# Compose-specific
docker compose -f services/<service>/docker-compose.yml logs -f
```

### Health checks

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
docker stats --no-stream
```

### Disk usage

```bash
df -h
du -sh /home/giografi/homelab/runtime/*
```

### Update images

```bash
docker pull <image_name>
docker compose -f services/<service>/docker-compose.yml down
docker compose -f services/<service>/docker-compose.yml up -d
```

### Prune old images

```bash
docker image prune -a
```

### Shell into a container

```bash
docker exec -it <container_name> sh
```

### Adding a new service

1. Copy the [compose template](#compose-template) and fill in the blanks
2. Create the runtime directory: `mkdir -p runtime/<service>`
3. Create `.env` if needed, then run `./scripts/generate-env-examples.sh`
4. Start: `docker compose -f services/<service>/docker-compose.yml up -d`
5. Add NPM proxy host + SSL + Cloudflare DNS A record

### Adding a new subdomain

1. Add DNS A record in Cloudflare: `<subdomain>` → `YOUR.SERVER.IP`
2. Start the service (see above)
3. In NPM admin: add Proxy Host → `<subdomain>.giografi.my.id` → `<container_name>:<port>`
4. Enable SSL + Force SSL

### Adding an AI provider to Open WebUI

Add the provider's base URL and API key to `runtime/open-webui/.env`, then append to the semicolon-separated lists:

```bash
NEW_PROVIDER_BASEURL=https://api.newprovider.com/v1
NEW_PROVIDER_APIKEY=sk-your-key-here

OPENAI_API_BASE_URLS=$OPENAI_BASEURL;$OPENROUTER_BASEURL;$ANTHROPIC_BASEURL;$HF_BASEURL;$DEEPSEEK_BASEURL;$NEW_PROVIDER_BASEURL
OPENAI_API_KEYS=$OPENAI_APIKEY;$OPENROUTER_APIKEY;$ANTHROPIC_APIKEY;$HF_TOKEN;$DEEPSEEK_APIKEY;$NEW_PROVIDER_APIKEY
```

Restart: `docker compose -f services/open-webui/docker-compose.yml restart`

### Environment files

| File | Service | Keys |
|------|---------|------|
| `runtime/open-webui/.env` | Open WebUI | `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `HF_TOKEN`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `WEBUI_SECRET_KEY`, `WEBUI_ADMIN_EMAIL`, `WEBUI_ADMIN_PASSWORD` |
| `runtime/ollama/.env` | Ollama | `OLLAMA_API_KEY` |
| `runtime/floci/.env` | Floci | `AWS_ENDPOINT_URL`, `AWS_DEFAULT_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| `runtime/crawl4ai/.env` | crawl4ai | `CRAWL4AI_API_TOKEN` |
| `runtime/9router/.env` | 9router | `JWT_SECRET`, `INITIAL_PASSWORD`, `DATA_DIR`, `PORT`, `NODE_ENV`, `API_KEY_SECRET`, `BASE_URL`, `CLOUD_URL` |

**Rules:**
1. Never commit `.env` files. Run `./scripts/generate-env-examples.sh` to sync templates for git.
2. Don't put quotes around simple values — Docker reads them literally.
3. Special characters like `;` or `$` can break `env_file` parsing. See [Troubleshooting #4](#4-env-file-quotes-breaking-parsing).
4. Variables can reference other variables on the same file.

### Resource limit guidelines

| Service Type | CPU | RAM | Why |
|-------------|-----|-----|-----|
| Small utility (dns, proxy) | 0.5 | 250M | Minimal work |
| Medium app (n8n, drawio) | 0.5-1 | 256M-1G | Moderate work |
| Heavy app (databases, monitoring) | 0.5-1 | 512M-2G | Depends on data volume |
| AI/ML (Ollama) | Depends | Depends | Cloud = light, Local = heavy |

Start low. If a container gets OOM-killed (`docker inspect <name> | grep OOMKilled`), increase memory by 256M increments.

---

## Reference

### Port Reference

| Port | Protocol | Service | Exposed to Host? | Purpose |
|------|----------|---------|-----------------|---------|
| 22 | TCP | SSH | Yes | Remote access |
| 53 | TCP+UDP | AdGuardHome | Yes | DNS resolution |
| 80 | TCP | NPM | Yes | HTTP (redirects to HTTPS) |
| 81 | TCP | NPM | Yes | NPM admin panel |
| 443 | TCP | NPM | Yes | HTTPS |
| 3000 | TCP | AdGuardHome | No | First-launch wizard only |
| 3030 | TCP | Grafana | No | Monitoring (not started) |
| 4566 | TCP | Floci | No | Local AWS (not started) |
| 5678 | TCP | n8n | No | Workflow automation (not started) |
| 20128 | TCP | 9router | Yes | API routing |
| 9080 | TCP | Traefik | Yes | Traefik HTTP (alt port) |
| 8080 | TCP | AdGuardHome | No | Admin panel (commented out) |
| 8080 | TCP | Open WebUI | No | Internal only |
| 8080 | TCP | Drawio | No | Internal only |
| 9443 | TCP | Traefik | Yes | Traefik HTTPS (alt port) |
| 9998 | TCP | Tika | Yes | Content extraction (not started) |
| 9090 | TCP | Prometheus | No | Metrics (not started) |
| 9091 | TCP | Promtail | No | Log shipping (not started) |
| 9100 | TCP | Node Exporter | No | System metrics (not started) |
| 11434 | TCP | Ollama | Yes | LLM API |
| 3100 | TCP | Loki | No | Log aggregation (not started) |

### Compose Template

Copy and fill in the blanks:

```yaml
services:
  <service-name>:
    container_name: <service-name>
    image: <image:tag>
    restart: unless-stopped

    env_file:
      - ../../runtime/<service>/.env

    environment:
      TZ: "Asia/Jakarta"
      # Add non-sensitive env vars here

    ports:
      - "<host_port>:<container_port>"

    volumes:
      - ../../runtime/<service>/data:/path/inside/container

    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:<port> || exit 1"]
      interval: 1m30s
      timeout: 10s
      retries: 5
      start_period: 10s

    depends_on:
      - <other-service>

    networks:
      - private-net

    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
        reservations:
          cpus: "0.25"
          memory: 128M

networks:
  private-net:
    external: true
```

**Field order rationale:**

| # | Field | Why |
|---|-------|-----|
| 1 | `container_name` | Predictable name for `docker exec` and NPM |
| 2 | `image` | What to pull from Docker Hub |
| 3 | `restart` | `unless-stopped` = auto-restart on crash/reboot, but not if manually stopped |
| 4 | `env_file` | Path to `.env` with secrets |
| 5 | `environment` | Non-sensitive vars (safe in compose) |
| 6 | `ports` | Host-to-container port mapping |
| 7 | `volumes` | Bind mounts for persistent data |
| 8 | `healthcheck` | How Docker knows the service is actually working |
| 9 | `depends_on` | Start order |
| 10 | `networks` | Which Docker network to join |
| 11 | `deploy.resources` | CPU and RAM limits |
| 12 | Top-level `networks:` | Declares the external network (critical — without `external: true`, Docker creates a new isolated network) |

---

## Troubleshooting

### 1. AdGuardHome admin panel unreachable via direct IP

**Symptom:** `http://YOUR.IP:8080` returns "connection refused".

**Cause:** The `8080:80` port mapping is intentionally commented out.

**Fix:** Access through NPM at `https://adguard.giografi.my.id`. If you need direct access temporarily, uncomment the port, do your work, then comment it out again.

---

### 2. AdGuardHome setup wizard vs admin panel

**Symptom:** Port 8080 doesn't load after starting AdGuardHome, but port 3000 works.

**Cause:** AdGuardHome uses port 3000 for the first-launch setup wizard. After setup completes, it switches to port 80.

**Fix:** Complete the setup wizard at `http://YOUR.IP:3000` first. Then the admin panel runs on port 80 (accessible via NPM).

---

### 3. NPM 502 Bad Gateway

**Symptom:** Proxy host returns "502 Bad Gateway".

**Cause:** Wrong forward port — used the host-mapped port instead of the container port.

**Fix:** In NPM, set Forward Host to the container name and Forward Port to the container's internal port. Verify with `docker inspect <container>` under "Ports".

---

### 4. .env file quotes breaking parsing

**Symptom:** Service starts but can't connect to providers. `.env` values have quotes like `HF_TOKEN="hf_abc..."` but the container reads them literally with quotes included.

**Cause:** Docker's `env_file` reads values literally. Quotes become part of the value. Worse, quotes around a value in a semicolon-separated list (like `$HF_TOKEN` in `OPENAI_API_KEYS`) break the entire chain.

**Fix:** Remove all quotes from `.env` values unless the value itself contains spaces.

---

### 5. Open WebUI "Missing Authentication header"

**Symptom:** Open WebUI loads but can't connect to AI providers. "Missing Authentication header" errors.

**Cause:** Wrong environment variable name (e.g., `OPEN_API_KEYS` instead of `OPENAI_API_KEYS`).

**Fix:** Double-check env var names against the official Open WebUI docs. If the DB already stored bad config, either delete `runtime/open-webui/data/webui.db` and re-setup, or manually fix it with SQLite:

```bash
cp runtime/open-webui/data/webui.db runtime/open-webui/data/webui.db.bak
sqlite3 runtime/open-webui/data/webui.db "SELECT * FROM config WHERE key LIKE 'api%';"
sqlite3 runtime/open-webui/data/webui.db "UPDATE config SET value = 'correct_url' WHERE key = 'api_base_url';"
docker compose -f services/open-webui/docker-compose.yml restart
```

---

### 6. Ollama cloud models need authentication

**Symptom:** Local Ollama models (like `llama3`) work, but cloud models (like `gemma4:31b-cloud`) return "unauthorized".

**Cause:** Cloud models require an API key via `ollama login`.

**Fix:**

```bash
docker exec -it ollama sh
ollama login          # paste your API key
exit
curl http://localhost:11434/api/tags   # verify cloud models appear
```

**Note:** Auth is stored in the container. Re-creating the container requires logging in again.

---

### 7. Port conflict between services

**Symptom:** One of two services fails to start — can't bind to a port.

**Cause:** Both services try to map the same host port (e.g., port 9080).

**Fix:** Remove port mappings from one service and access it through NPM. Check existing port usage with: `ss -tlnp | grep :<port>`

**Note:** Port 8080 is reserved for AdGuardHome (admin panel, currently commented out). Port 3000 is reserved for AdGuardHome's first-launch setup wizard. Traefik and Grafana use 9080/9443 and 3030 respectively to avoid conflicts.

---

### 8. Container not connecting to private-net

**Symptom:** Container starts but can't reach other services by name. `docker exec -it <container> ping npm` fails.

**Cause:** Missing the top-level `networks:` declaration with `external: true` in the compose file. Without it, Docker creates a new isolated network with the same name.

**Fix:** Every compose file needs:

```yaml
# Inside the service:
networks:
  - private-net

# At the bottom of the file:
networks:
  private-net:
    external: true
```

---

*Last updated: 2026-06-19. Written by giografi, for anyone who wants to learn from my mistakes.*
