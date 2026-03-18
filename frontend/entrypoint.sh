#!/bin/sh
set -e

# Digital Ocean App Platform injects BACKEND_URL as the private service URL.
# nginx does not read env vars natively — envsubst substitutes it at startup.
# Falls back to docker-compose service name for local dev.
BACKEND_URL="${BACKEND_URL:-http://backend:8000}"

echo "Starting nginx — BACKEND_URL=${BACKEND_URL}"

envsubst '${BACKEND_URL}' \
    < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"
