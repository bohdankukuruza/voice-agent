#!/bin/bash
# One-time bootstrap: creates a dummy cert so nginx can start, requests the
# real Let's Encrypt cert via the HTTP-01 webroot challenge, then reloads nginx.
# Run this once on the server after `docker compose up -d nginx app` prerequisites
# are in place (see DEPLOY.md).

set -e

if [ -z "$DOMAIN" ]; then
  echo "Set DOMAIN in .env first (e.g. DOMAIN=example.com)."
  exit 1
fi

if [ -z "$LETSENCRYPT_EMAIL" ]; then
  echo "Set LETSENCRYPT_EMAIL in .env first (used for renewal notices)."
  exit 1
fi

data_path="./certbot"
domain_path="$data_path/conf/live/$DOMAIN"

echo "### Creating dummy certificate for $DOMAIN ..."
mkdir -p "$domain_path"
docker compose run --rm --entrypoint "\
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout '$domain_path/privkey.pem' \
    -out '$domain_path/fullchain.pem' \
    -subj '/CN=localhost'" certbot

echo "### Starting nginx ..."
docker compose up -d nginx

echo "### Deleting dummy certificate ..."
docker compose run --rm --entrypoint "\
  rm -rf /etc/letsencrypt/live/$DOMAIN && \
  rm -rf /etc/letsencrypt/archive/$DOMAIN && \
  rm -rf /etc/letsencrypt/renewal/$DOMAIN.conf" certbot

echo "### Requesting real Let's Encrypt certificate for $DOMAIN ..."
docker compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    --email $LETSENCRYPT_EMAIL -d $DOMAIN \
    --rsa-key-size 2048 --agree-tos --non-interactive" certbot

echo "### Reloading nginx ..."
docker compose exec nginx nginx -s reload

echo "Done. https://$DOMAIN should now be serving a valid certificate."
