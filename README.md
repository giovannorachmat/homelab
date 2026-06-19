# I built this homelab to learn DevOps/SRE

This is a personal homelab running on a mini PC at home. I use it to learn Docker, networking, reverse proxies, monitoring, and everything else a good SRE should know. Everything runs on a single machine behind a Cloudflare DNS, accessible from anywhere via subdomains on `giografi.my.id`.

**Current status:**
- 5 services running (AdGuardHome, NPM, Ollama, Open WebUI, Traefik)
- 4 services defined but not started (n8n, drawio, floci, monitoring)
- All behind NPM reverse proxy with Let's Encrypt SSL

---

## 1. Hardware

| Spec | Value |
|------|-------|
| **Machine** | Lenovo M715q (mini PC) |
| **CPU** | AMD Ryzen 5 2400GE, 3.2 GHz, 4 cores / 8 threads |
| **RAM** | 16 GB |
| **Storage** | 128 GB SSD |
| **OS** | Ubuntu 24.04.4 LTS (Noble Numbat) |
| **Hostname** | `lenovo-m715q` |

**Why this matters:** This is not a beefy server. Every service has strict resource limits. If you add something heavy, you will run out of memory or disk. Check `docker stats` and `df -h` regularly.

**Disk usage warning:** As of writing, root filesystem is at 81% (88GB / 115GB used, 22GB free). Be careful with log files, model downloads, and Docker images.

---

## 2. Directory Layout

```
/home/giografi/homelab/
├── services/                  # Docker Compose files + configs (what to run)
│   ├── adguardhome/
│   │   └── docker-compose.yml
│   ├── drawio/
│   │   └── docker-compose.yml
│   ├── floci/
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
    ├── adguardhome/
    │   ├── conf/              # AdGuardHome config (AdGuardHome.yaml)
    │   └── work/              # AdGuardHome runtime data
    ├── certs/                 # TLS certificates (Tailscale, home.lan wildcard)
    ├── floci/
    │   ├── data/
    │   └── .env               # AWS credentials (test)
    ├── monitoring/
    │   ├── config/
    │   └── .env               # (unused — values hardcoded in compose)
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

**Why two folders?**

- `services/` = code. I can edit, version control, and share these. The compose files define *what* to run.
- `runtime/` = state. This is where containers store their data. I back this up. If I delete a compose file and re-create it, the container picks up where it left off because the data is still here.

**Why bind mounts instead of Docker volumes?**

Docker volumes are opaque — you need `docker volume inspect` to find where data lives. Bind mounts put everything in a predictable path I can `ls`, `cat`, and `tar`. For a homelab, this is easier to manage and back up.

---

## 3. Prerequisites

Before you start, you need:

1. **Docker + Docker Compose**
   ```bash
   # Install Docker
   curl -fsSL https://get.docker.com | sh
   
   # Add your user to the docker group (log out and back in after)
   sudo usermod -aG docker $USER
   ```

2. **A domain name** — I use `giografi.my.id`. Point an A record to your server's public IP.

3. **Cloudflare (or similar DNS provider)** — for DNS management and SSL. If you use Cloudflare, set SSL mode to "Full (Strict)" and enable proxy (orange cloud) for your subdomains.

4. **Basic terminal knowledge** — you should be comfortable with `cd`, `ls`, `cat`, `nano`/`vim`, and running commands in a terminal.

---

## 4. Quick Start

Here's how I get everything running from scratch:

### Step 1: Create the directory structure

```bash
mkdir -p /home/giografi/homelab
cd /home/giografi/homelab
mkdir -p services runtime
```

### Step 2: Create the Docker network

All services share a single network called `private-net`. Create it once:

```bash
docker network create private-net
```

### Step 3: Create .env files

Each service that needs secrets has a `.env` file. Create them with placeholder values:

```bash
# Open WebUI
mkdir -p runtime/open-webui
cat > runtime/open-webui/.env << 'EOF'
OPENAI_API_KEY=your-openai-key-here
OPENROUTER_API_KEY=your-openrouter-key-here
HF_TOKEN=your-huggingface-token-here
ANTHROPIC_API_KEY=your-anthropic-key-here
DEEPSEEK_API_KEY=your-deepseek-key-here
EOF

# Ollama
mkdir -p runtime/ollama
cat > runtime/ollama/.env << 'EOF'
OLLAMA_API_KEY=your-ollama-cloud-key-here
EOF
```

### Step 4: Start core services

```bash
# Start these in order (NPM first because it binds port 80/443)
docker compose -f services/npm/docker-compose.yml up -d
docker compose -f services/adguardhome/docker-compose.yml up -d
docker compose -f services/ollama/docker-compose.yml up -d
docker compose -f services/open-webui/docker-compose.yml up -d
```

### Step 5: Verify everything is running

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

You should see:
- `adguardhome` — Up, port 53 exposed
- `npm` — Up, ports 80/81/443 exposed
- `ollama` — Up, port 11434 exposed
- `open-webui` — Up (health: starting → healthy after ~30s)

### Step 6: Configure DNS

In Cloudflare (or your DNS provider), create A records:

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | `@` | `YOUR.SERVER.IP` | Yes |
| A | `adguard` | `YOUR.SERVER.IP` | Yes |
| A | `npm` | `YOUR.SERVER.IP` | Yes |
| A | `ai` | `YOUR.SERVER.IP` | Yes |

### Step 7: Set up NPM proxy hosts

1. Open `http://YOUR.SERVER.IP:81` in your browser
2. Login with default credentials:
   - Email: `admin@example.com`
   - Password: `changeme`
   - **Change these immediately!**
3. Go to **Proxy Hosts** → **Add Proxy Host**
4. For each service, create a proxy host:

| Domain | Forward Host | Forward Port | WebSocket |
|--------|-------------|-------------|-----------|
| `adguard.giografi.my.id` | `adguardhome` | `80` | No |
| `npm.giografi.my.id` | `npm` | `81` | No |
| `ai.giografi.my.id` | `open-webui` | `8080` | **Yes** |

5. Enable **SSL** tab → Let's Encrypt → Request new certificate
6. Enable **Force SSL**

### Step 8: Verify access

- `https://adguard.giografi.my.id` → AdGuardHome admin
- `https://npm.giografi.my.id` → NPM admin
- `https://ai.giografi.my.id` → Open WebUI chat

### Step 9: Update .env.example files (for GitHub)

After editing any `.env` file, regenerate the templates so they stay in sync:

```bash
cd /home/giografi/homelab
./scripts/generate-env-examples.sh
```

This reads every `runtime/**/.env` and writes a corresponding `.env.example` with placeholder values. Only `.env.example` files are committed to git — real `.env` files are ignored.

---

## 5. Services Reference

| Service | Image | Host Ports | CPU / RAM Limits | Purpose | Status |
|---------|-------|-----------|------------------|---------|--------|
| **AdGuardHome** | `adguard/adguardhome:latest` | 53 (DNS) | 0.5 / 250M | DNS ad-blocker | Running |
| **NPM** | `jc21/nginx-proxy-manager:2.15.1` | 80, 81, 443 | 0.5 / 250M | Reverse proxy + SSL | Running |
| **Ollama** | `ollama/ollama:latest` | 11434 | 0.5 / 256M | LLM inference (cloud proxy) | Running |
| **Open WebUI** | `ghcr.io/open-webui/open-webui:main-slim` | (internal only) | 1 / 1G | Chat interface for LLMs | Running |
| **Traefik** | `traefik:latest` | 8080, 8443 | 0.25 / 128M | Reverse proxy (learning) | Running |
| **n8n** | `docker.n8n.io/n8nio/n8n` | 5678 | 1 / 1G | Workflow automation | Not started |
| **Drawio** | `jgraph/drawio` | (none) | 0.5 / 256M | Diagramming tool | Not started |
| **Floci** | `floci/floci:latest` | 4566 | 0.5 / 256M | Local AWS emulator | Not started |
| **Monitoring** | Multiple | 3000, 9090, 9091, 9100, 3100 | ~2.5G total | Grafana + Prometheus + Loki | Not started |

**Total resources if everything runs:** ~6.5 GB RAM, ~5.5 CPU cores. On a 16GB / 8-thread machine, this leaves headroom for the OS and bursts.

---

## 6. Networking

### The private-net

All containers connect to a single Docker bridge network called `private-net`. This lets them talk to each other by container name (e.g., Open WebUI connects to Ollama via `http://ollama:11434`).

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

### Port mapping explained

When you see `ports: "8080:80"` in a compose file, it means:

```
host_port : container_port
```

- `8080` = the port on the host machine (what you access from outside)
- `80` = the port inside the container (what the app listens on)

**Common mistake:** Don't confuse host port with container port. When NPM forwards to a service, it uses the **container port**, not the host port.

### Why AdGuardHome admin port is commented out

I commented out `8080:80` in the AdGuardHome compose file. This means you **cannot** access the admin panel directly via `http://YOUR.IP:8080`. You must go through NPM at `https://adguard.giografi.my.id`.

This is intentional — I want all admin access to go through HTTPS with authentication.

### Why drawio has no host ports

Drawio's container listens on port 8080 internally, same as AdGuardHome's commented-out port. If I exposed both, they'd conflict. I access drawio only through NPM at `https://drawio.giografi.my.id`.

### NPM reverse proxy flow

When you visit `https://ai.giografi.my.id`:

```
1. Browser sends HTTPS request to YOUR.SERVER.IP:443
2. NPM receives it on port 443
3. NPM matches the domain "ai.giografi.my.id" to a proxy host
4. NPM forwards the request to "open-webui:8080" (container name + container port)
5. Open WebUI responds
6. NPM sends the response back to your browser
```

---

## 7. Operations Cheat Sheet

### Start everything

```bash
cd /home/giografi/homelab

# Start core services
docker compose -f services/npm/docker-compose.yml up -d
docker compose -f services/adguardhome/docker-compose.yml up -d
docker compose -f services/ollama/docker-compose.yml up -d
docker compose -f services/open-webui/docker-compose.yml up -d

# Optional: start Traefik (learning)
docker compose -f services/traefik/docker-compose.yml up -d
```

### Start optional services

```bash
docker compose -f services/n8n/docker-compose.yml up -d
docker compose -f services/drawio/docker-compose.yml up -d
docker compose -f services/floci/docker-compose.yml up -d
docker compose -f services/monitoring/docker-compose.yml up -d
```

### Stop a specific service

```bash
docker compose -f services/<service>/docker-compose.yml down
```

### Restart a specific service

```bash
docker compose -f services/<service>/docker-compose.yml down && \
docker compose -f services/<service>/docker-compose.yml up -d
```

### View logs (follow mode)

```bash
docker logs -f <container_name>
```

### View last 100 lines of logs

```bash
docker logs --tail 100 <container_name>
```

### Check container health

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Enter a container shell

```bash
docker exec -it <container_name> sh
```

### Check resource usage

```bash
docker stats --no-stream
```

### Check disk usage

```bash
df -h
```

### Check what's using disk

```bash
du -sh /home/giografi/homelab/runtime/*
```

### Update an image

```bash
# Pull the latest image
docker pull <image_name>

# Recreate the container
docker compose -f services/<service>/docker-compose.yml down
docker compose -f services/<service>/docker-compose.yml up -d
```

### Prune old images

```bash
docker image prune -a
```

### Regenerate .env.example files (for GitHub)

After editing any `.env` file, run this to update the templates:

```bash
cd /home/giografi/homelab
./scripts/generate-env-examples.sh
```

This keeps `.env.example` files in sync with your real `.env` files. Only `.env.example` goes to git — real `.env` files are ignored by `.gitignore`.

---

## 8. Adding a New Service

When I add a new service, I follow this process:

### Step 1: Create the compose file

Copy the template from [Section 14](#compose-template) and fill in the blanks.

### Step 2: Create the runtime directory

```bash
mkdir -p /home/giografi/homelab/runtime/<service>
```

### Step 3: Create .env (if needed)

```bash
cat > /home/giografi/homelab/runtime/<service>/.env << 'EOF'
SECRET_KEY=your-secret-here
EOF
```

Then regenerate the template for GitHub:

```bash
./scripts/generate-env-examples.sh
```

### Step 4: Start the service

```bash
docker compose -f services/<service>/docker-compose.yml up -d
```

### Step 5: Add NPM proxy host (if web-accessible)

1. Open NPM admin at `https://npm.giografi.my.id`
2. Add Proxy Host: domain = `<service>.giografi.my.id`, forward to `<container_name>:<container_port>`
3. Enable SSL + Force SSL
4. Add DNS A record in Cloudflare

### Resource limit guidelines

| Service Type | CPU | RAM | Why |
|-------------|-----|-----|-----|
| Small utility (dns, proxy) | 0.5 | 250M | Minimal work |
| Medium app (n8n, drawio) | 0.5-1 | 256M-1G | Moderate work |
| Heavy app (databases, monitoring) | 0.5-1 | 512M-2G | Depends on data volume |
| AI/ML (Ollama) | Depends | Depends | Cloud = light, Local = heavy |

**Rule of thumb:** Start low. If a container keeps getting OOM-killed (`docker inspect <name> | grep OOMKilled`), increase memory by 256M increments.

---

## 9. Environment Files

| File | Service | Keys (descriptions) |
|------|---------|-------------------|
| `runtime/open-webui/.env` | Open WebUI | `OPENAI_API_KEY` (OpenAI), `OPENROUTER_API_KEY` (OpenRouter), `HF_TOKEN` (HuggingFace), `ANTHROPIC_API_KEY` (Anthropic), `DEEPSEEK_API_KEY` (DeepSeek), `WEBUI_SECRET_KEY` (session secret), `WEBUI_ADMIN_EMAIL`, `WEBUI_ADMIN_PASSWORD` |
| `runtime/ollama/.env` | Ollama | `OLLAMA_API_KEY` (cloud model auth) |
| `runtime/floci/.env` | Floci | `AWS_ENDPOINT_URL`, `AWS_DEFAULT_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (test credentials) |

**Important rules for .env files:**

1. **Never commit .env files to git.** The `.gitignore` excludes `runtime/**` but includes `**/.env.example`. Run `./scripts/generate-env-examples.sh` to sync templates.
2. **Don't put quotes around simple values.** Docker reads them literally. `"value"` becomes `"value"` (with quotes).
3. **Special characters need care.** If your password has `;` or `$`, it can break env_file parsing. See [Troubleshooting #5](#5-hftoken-double-quotes-breaking-env-parsing).
4. **Variables can reference other variables.** In the Open WebUI .env, `OPENAI_API_BASE_URLS=$OPENAI_BASEURL;$OPENROUTER_BASEURL` works because Docker resolves them in order.

**Keeping .env.example in sync:**

Every `.env` has a corresponding `.env.example` with placeholder values. After editing any `.env`, run:

```bash
./scripts/generate-env-examples.sh
```

This ensures GitHub always has the latest template with the correct keys.

---

## 10. Troubleshooting

These are all the issues I hit while setting up this homelab, in the order I encountered them.

---

### 1. AdGuardHome admin panel unreachable

**Symptom:** I go to `http://YOUR.IP:8080` and get "connection refused".

**Root cause:** I commented out the `8080:80` port mapping in the compose file. This is intentional.

**What I tried:**
- Uncommented the port → it worked but conflicted with drawio
- Decided to keep it commented out and access via NPM only

**Fix:** Access AdGuardHome admin through NPM at `https://adguard.giografi.my.id`. Make sure you have an NPM proxy host configured for it (forward to `adguardhome:80`).

**Prevention:** If you need to temporarily access the admin panel directly, uncomment the port, do your work, then comment it out again.

---

### 2. AdGuardHome install wizard vs runtime ports

**Symptom:** After installing AdGuardHome, the admin panel at port 8080 doesn't load. But port 3000 works.

**Root cause:** AdGuardHome uses port 3000 for the first-launch setup wizard. After setup completes, it switches to port 80. The container maps both:
- `3000:3000` → only active during first launch
- `8080:80` → only active after setup completes (and currently commented out)

**What I tried:**
- Accessing port 8080 immediately after starting the container → failed
- Accessing port 3000 → showed the setup wizard
- Completed setup, then port 80 started working

**Fix:** Complete the AdGuardHome setup wizard at `http://YOUR.IP:3000` first. After that, the admin panel runs on port 80 (accessible via NPM).

**Prevention:** Always complete the setup wizard before trying to access via NPM.

---

### 3. NPM 502 Bad Gateway

**Symptom:** I set up an NPM proxy host for Open WebUI, but when I visit `https://ai.giografi.my.id`, I get "502 Bad Gateway".

**Root cause:** I entered the wrong forward port. I put the *host-mapped* port (8080) instead of the *container* port (also 8080 in this case, but for other services the ports differ).

**The key concept:** NPM forwards to `container_name:CONTAINER_PORT`, not `container_name:HOST_PORT`. These are often different.

**What I tried:**
- Checked container was running: `docker ps` → yes
- Checked NPM logs: `docker logs npm` → saw "upstream connection error"
- Verified the container port: `docker inspect open-webui | grep -A5 Ports` → internal port is 8080
- Fixed the forward port in NPM from `8080` to `8080` (same in this case, but I had it wrong for another service)

**Fix:** In NPM admin, edit the proxy host. Set Forward Host to the container name (e.g., `open-webui`) and Forward Port to the container's internal port (check `docker inspect <container>` under "Ports").

**Prevention:** Always verify the container port with `docker inspect` before setting up NPM. Don't guess.

---

### 4. Open WebUI "Missing Authentication header"

**Symptom:** Open WebUI loads, but when I try to use it, I get "Missing Authentication header" or "Failed to connect to AI provider".

**Root cause:** I used the wrong environment variable name. I had `OPEN_API_KEYS` instead of `OPENAI_API_KEYS`.

**What I tried:**
- Checked the `.env` file → values looked correct
- Checked the compose file → saw `OPEN_API_KEYS` (missing the `AI` part)
- Fixed it to `OPENAI_API_KEYS`
- Restarted the container → still broken
- Realized the old env var had written bad config to the SQLite database

**Fix:** 
1. Fix the env var name in the compose file
2. If the DB is corrupted, you need to either:
   - Delete `runtime/open-webui/data/webui.db` and re-setup Open WebUI
   - Or manually fix the DB with SQLite commands (what I did — risky, backup first)

**Prevention:** Always double-check env var names against the official docs. Open WebUI's vars start with `OPENAI_`, not `OPEN_`.

---

### 5. HF_TOKEN double quotes breaking env parsing

**Symptom:** Open WebUI starts but can't connect to HuggingFace. The `.env` file has `HF_TOKEN="hf_abc123..."` but the container reads it as `"hf_abc123..."` (with the quotes included).

**Root cause:** Docker's `env_file` directive reads values literally. If you put quotes around a value, the quotes become part of the value. Worse, if the value contains `;` (semicolons), it can break the parsing of subsequent variables on the same line.

In my case, I had:
```
OPENAI_API_KEYS=$OPENAI_APIKEY;$OPENROUTER_APIKEY;$ANTHROPIC_APIKEY;$HF_TOKEN;$DEEPSEEK_APIKEY
```

The `HF_TOKEN` had quotes around it, which broke the semicolon-separated list.

**What I tried:**
- Removed quotes from all `.env` values
- Tested each provider individually
- Found that removing quotes from `HF_TOKEN` fixed the chain

**Fix:** Remove all quotes from `.env` values unless the value itself contains spaces (and even then, be careful). If a value contains special characters like `;`, `$`, or `#`, consider using a different variable structure.

**Prevention:** Don't put quotes around values in `.env` files. Docker reads them literally.

---

### 6. Open WebUI DB corruption from env var issues

**Symptom:** After fixing the env var names, Open WebUI still couldn't connect to providers. The settings in the UI showed wrong base URLs.

**Root cause:** Open WebUI stores API config in `runtime/open-webui/data/webui.db` (SQLite). When I had wrong env vars, the app wrote bad config to the DB. Even after fixing the env vars, the DB still had the old (wrong) values.

**What I tried:**
1. Restarted the container → didn't help (DB persisted)
2. Deleted `webui.db` → fresh setup, worked but lost all chats
3. Decided to manually fix the DB instead (what I did)

**Fix:**
```bash
# Backup the DB first
cp runtime/open-webui/data/webui.db runtime/open-webui/data/webui.db.bak

# Install sqlite3
sudo apt install sqlite3

# Inspect the config
sqlite3 runtime/open-webui/data/webui.db "SELECT * FROM config WHERE key LIKE 'api%';"

# Update the bad values
sqlite3 runtime/open-webui/data/webui.db "UPDATE config SET value = 'correct_url' WHERE key = 'api_base_url';"

# Restart the container
docker compose -f services/open-webui/docker-compose.yml restart
```

**Prevention:** Get the env vars right the first time. If you mess up, delete `webui.db` before the container has a chance to write bad config. It's faster than fixing it manually.

---

### 7. Ollama cloud models need authentication

**Symptom:** I can use local Ollama models (like `llama3`) but cloud models (like `gemma4:31b-cloud`) return "unauthorized".

**Root cause:** Ollama cloud models require an API key. You need to log in inside the container.

**What I tried:**
- Setting `OLLAMA_API_KEY` in `.env` → didn't work (that's for something else)
- Running `ollama login` inside the container → worked

**Fix:**
```bash
# Enter the container
docker exec -it ollama sh

# Log in to Ollama cloud
ollama login
# Paste your API key when prompted

# Exit
exit

# Test
curl http://localhost:11434/api/tags
# Should show cloud models available
```

**Prevention:** After logging in, the auth token is stored in the container. If you recreate the container (`docker compose down && up`), you'll need to log in again. Consider mounting the Ollama auth directory as a volume.

---

### 8. Drawio port 8080 conflict with AdGuardHome

**Symptom:** I start both AdGuardHome and drawio, but one of them can't bind to port 8080.

**Root cause:** Both services were trying to map host port 8080 to their container ports. Docker can't bind the same host port to two different containers.

**What I tried:**
- Changed drawio's host port to 8081 → worked but now I need to remember which port is which
- Decided to remove drawio's host ports entirely → access via NPM only

**Fix:** Drawio's compose file has no `ports` section. It's only accessible through NPM at `https://drawio.giografi.my.id` (forward to `drawio:8080`).

**Prevention:** Before exposing a host port, check if anything else already uses it: `ss -tlnp | grep :8080`

---

### 9. Traefik vs NPM port conflict

**Symptom:** I start Traefik and NPM, but one of them fails because they both want port 80 or 443.

**Root cause:** Both are reverse proxies. If they both bind to port 80/443, only one can run.

**What I tried:**
- Running Traefik on alt ports `8080`/`8443` → worked
- Decided to keep both running: NPM on 80/443 (production), Traefik on 8080/8443 (learning)

**Fix:** Traefik's compose file uses:
```yaml
ports:
  - "8080:80"   # HTTP on alt port
  - "8443:443"  # HTTPS on alt port
```

NPM keeps the standard ports:
```yaml
ports:
  - "80:80"
  - "443:443"
  - "81:81"
```

**Prevention:** Check port availability before starting a new reverse proxy: `ss -tlnp | grep -E ':(80|443|8080|8443) '`

---

### 10. Container not connecting to private-net

**Symptom:** Container starts but can't reach other services by name. `docker exec -it <container> ping npm` fails.

**Root cause:** I forgot to add the `networks` section to the compose file, or I forgot the top-level `networks:` declaration.

**The fix:** Every compose file needs BOTH:

```yaml
# Inside the service definition:
services:
  my-service:
    networks:
      - private-net

# At the bottom of the file:
networks:
  private-net:
    external: true
```

Without the bottom section, Docker creates a *new* network called `private-net` just for that compose file, separate from the shared one.

**What I tried:**
- `docker network ls` → saw two `private-net` networks
- `docker network inspect private-net` → only some containers were listed
- Added the `external: true` declaration → container joined the correct network

**Prevention:** Always include both `networks:` sections. The `external: true` tells Docker "don't create this network, it already exists."

---

## 11. FAQ

### Q: Why single Docker network instead of separate ones?

**A:** I'm a beginner. A single `private-net` is simpler to manage, debug, and reason about. I can split it later (e.g., `monitoring-net`, `ai-net`, `proxy-net`) when I outgrow it. For now, `docker network inspect private-net` shows everything in one place.

### Q: Why NPM instead of just Traefik?

**A:** NPM has a web UI for managing proxy hosts. I can add domains, SSL certs, and advanced configs without editing YAML files. Traefik is great for automation (it auto-discovers containers), but I want to learn the manual way first. I run both — NPM on standard ports for production, Traefik on alt ports for learning.

### Q: Why cloud-only Ollama?

**A:** I don't have a GPU. Running LLMs locally on CPU would be painfully slow. Ollama supports cloud models (like `gemma4:31b-cloud`) that run on Ollama's servers but are accessed through the same API. This way I get the Ollama experience without the hardware requirements.

### Q: Why bind mounts instead of Docker volumes?

**A:** I can see, edit, and back up the data directly. `ls /home/giografi/homelab/runtime/npm/data/` shows me exactly what NPM is storing. Docker volumes require `docker volume inspect` and are stored in `/var/lib/docker/volumes/` which is harder to manage.

### Q: Why comment out AdGuardHome admin port?

**A:** Security. I want all admin access to go through HTTPS (NPM) with SSL. Direct HTTP access on port 8080 has no encryption and no authentication. If I need to temporarily access it, I uncomment the port, do my work, then comment it out again.

### Q: Why does Open WebUI have both multi-provider and single-provider env vars?

**A:** Open WebUI supports multiple AI providers via `OPENAI_API_BASE_URLS` and `OPENAI_API_KEYS` (semicolon-separated lists). But it also supports single-provider fallback via `OPENAI_API_BASE_URL` and `OPENAI_API_KEY`. I have both configured because:
- The multi-provider vars had DB corruption issues (see Troubleshooting #6)
- The single-provider vars work as a fallback
- If I fix the multi-provider setup later, I can remove the single-provider vars

### Q: How do I add a new AI provider to Open WebUI?

**A:** Add the provider's base URL and API key to the `.env` file, then append them to the semicolon-separated lists:

```bash
# In runtime/open-webui/.env
NEW_PROVIDER_BASEURL=https://api.newprovider.com/v1
NEW_PROVIDER_APIKEY=sk-your-key-here

# Update the lists
OPENAI_API_BASE_URLS=$OPENAI_BASEURL;$OPENROUTER_BASEURL;$ANTHROPIC_BASEURL;$HF_BASEURL;$DEEPSEEK_BASEURL;$NEW_PROVIDER_BASEURL
OPENAI_API_KEYS=$OPENAI_APIKEY;$OPENROUTER_APIKEY;$ANTHROPIC_APIKEY;$HF_TOKEN;$DEEPSEEK_APIKEY;$NEW_PROVIDER_APIKEY
```

Restart the container: `docker compose -f services/open-webui/docker-compose.yml restart`

### Q: How do I add a new subdomain?

**A:**
1. Add DNS A record in Cloudflare: `<subdomain>` → `YOUR.SERVER.IP`
2. Start the service: `docker compose -f services/<service>/docker-compose.yml up -d`
3. In NPM admin, add Proxy Host: `<subdomain>.giografi.my.id` → `<container_name>:<port>`
4. Enable SSL + Force SSL
5. Test: `https://<subdomain>.giografi.my.id`

---

## 12. Port Reference

| Port | Protocol | Service | Exposed to Host? | Purpose |
|------|----------|---------|-----------------|---------|
| 22 | TCP | SSH | Yes | Remote access |
| 53 | TCP+UDP | AdGuardHome | Yes | DNS resolution |
| 80 | TCP | NPM | Yes | HTTP (redirects to HTTPS) |
| 81 | TCP | NPM | Yes | NPM admin panel |
| 443 | TCP | NPM | Yes | HTTPS |
| 3000 | TCP | AdGuardHome | No | First-launch wizard only |
| 3000 | TCP | Grafana | No | Monitoring (not started) |
| 4566 | TCP | Floci | No | Local AWS (not started) |
| 5678 | TCP | n8n | No | Workflow automation (not started) |
| 8080 | TCP | Traefik | Yes | Traefik HTTP (alt port) |
| 8080 | TCP | AdGuardHome | No | Admin panel (commented out) |
| 8080 | TCP | Open WebUI | No | Internal only |
| 8080 | TCP | Drawio | No | Internal only |
| 8443 | TCP | Traefik | Yes | Traefik HTTPS (alt port) |
| 9090 | TCP | Prometheus | No | Metrics (not started) |
| 9091 | TCP | Promtail | No | Log shipping (not started) |
| 9100 | TCP | Node Exporter | No | System metrics (not started) |
| 11434 | TCP | Ollama | Yes | LLM API |
| 3100 | TCP | Loki | No | Log aggregation (not started) |

---

## 13. Compose Template

I follow this exact field order for every compose file. Copy this and fill in the blanks:

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

**Field order explained:**

1. `container_name` — predictable name for `docker exec` and NPM
2. `image` — what to pull from Docker Hub
3. `restart` — `unless-stopped` = auto-restart on crash/reboot, but not if you manually stop it
4. `env_file` — path to `.env` with secrets
5. `environment` — non-sensitive env vars (can be in compose directly)
6. `ports` — host-to-container port mapping
7. `volumes` — bind mounts for persistent data
8. `healthcheck` — how Docker knows if the service is actually working
9. `depends_on` — start order (Docker starts dependencies first)
10. `networks` — which Docker network to join
11. `deploy.resources` — CPU and RAM limits (prevents one service from hogging everything)
12. Top-level `networks:` — declares the external network

**Quick reference — start commands:**

```bash
# Start
docker compose -f services/<service>/docker-compose.yml up -d

# Stop
docker compose -f services/<service>/docker-compose.yml down

# Restart
docker compose -f services/<service>/docker-compose.yml restart

# Logs
docker compose -f services/<service>/docker-compose.yml logs -f

# Status
docker ps --format "table {{.Names}}\t{{.Status}}"
```

---

*Last updated: 2026-06-19. Written by giografi, for anyone who wants to learn from my mistakes.*
