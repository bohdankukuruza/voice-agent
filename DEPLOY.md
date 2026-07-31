# Deploying voice-agent to a server

Prerequisites: a Linux VPS (Ubuntu 22.04+ recommended) and a domain name whose
DNS `A` record points at the VPS's public IP. Twilio requires a `wss://`
(TLS) endpoint, so the domain + certificate are mandatory, not optional.

## 1. Point DNS at the server

Create an `A` record for your domain (e.g. `voice.yourdomain.com`) pointing
to the VPS's public IPv4 address. Wait for it to propagate (`dig +short
voice.yourdomain.com` should return the IP) before continuing.

## 2. Install Docker on the VPS

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# log out and back in for the group change to take effect
```

## 3. Copy the project to the server

```bash
scp -r voice-agent your-user@your-server-ip:~/voice-agent
ssh your-user@your-server-ip
cd voice-agent
```

## 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `DEEPGRAM_API_KEY` — your Deepgram API key
- `DOMAIN` — the domain from step 1 (e.g. `voice.yourdomain.com`)
- `LETSENCRYPT_EMAIL` — your email (Let's Encrypt expiry notices)

## 5. Build the app image

```bash
docker compose build app
```

## 6. Bootstrap the SSL certificate (one-time)

```bash
chmod +x init-letsencrypt.sh
set -a; source .env; set +a
./init-letsencrypt.sh
```

This creates a temporary self-signed cert so nginx can start, requests the
real Let's Encrypt certificate over HTTP-01, then reloads nginx with it.

## 7. Start everything

```bash
docker compose up -d
```

`app` and `nginx` have `restart: always`, and the `certbot` container renews
the certificate automatically every 12 hours — so the whole stack survives
reboots and keeps running indefinitely. Verify with:

```bash
docker compose ps
docker compose logs -f app
```

## 8. Point Twilio at the server

In the Twilio console, set the Media Stream / Voice webhook for your number
to:

```
wss://voice.yourdomain.com/
```

(Replace with whatever path your Twilio setup expects — this project's
`twilio_handler` accepts any path since `websockets.serve` doesn't route on
path here.)

## Updating the app later

```bash
cd voice-agent
git pull   # or re-copy changed files
docker compose build app
docker compose up -d app
```

## Notes

- `ORDERS_DB` / `DRUG_DB` in `pharmacy_functions.py` are in-memory — they
  reset whenever the `app` container restarts. Fine for a prototype; move to
  Postgres for real persistence (see README's "Potential Improvements").
- Logs: `docker compose logs -f app` (Ctrl+C to stop following).
- To check certificate renewal is working: `docker compose logs certbot`.
