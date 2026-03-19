#!/bin/sh
set -e

echo "Starting nginx (static file server — /api routed by DO load balancer)"

# Copy the template straight to the config — no variable substitution needed
# since we no longer proxy to the backend from nginx.
cp /etc/nginx/templates/default.conf.template /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"
