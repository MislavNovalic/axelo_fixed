#!/bin/sh
set -e

# BACKEND_URL is injected by DO App Platform as the backend private service URL.
# Falls back to docker-compose service name for local dev.
BACKEND_URL="${BACKEND_URL:-http://backend:8000}"

echo "Starting nginx — BACKEND_URL=${BACKEND_URL}"

# Replace the placeholder with the actual backend URL.
# We use a simple string placeholder (BACKEND_URL_PLACEHOLDER) instead of
# ${BACKEND_URL} because envsubst would also replace nginx variables like
# $host, $remote_addr, etc. which must stay as-is.
sed "s|BACKEND_URL_PLACEHOLDER|${BACKEND_URL}|g" \
    /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

echo "nginx config written:"
grep "proxy_pass" /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"
