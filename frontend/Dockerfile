# ── Stage 1: Build Vue app ───────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies first (better layer caching)
COPY package.json ./
RUN npm install

# Copy source and build
COPY . .
RUN npm run build

# ── Stage 2: Serve with nginx ─────────────────────────────────────────────────
FROM nginx:1.27-alpine

# envsubst (gettext) — substitutes ${BACKEND_URL} in nginx config at startup
RUN apk add --no-cache gettext

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx config template (uses ${BACKEND_URL} placeholder)
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Copy and make entrypoint executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Digital Ocean App Platform requires port 8080 for non-root containers
EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
