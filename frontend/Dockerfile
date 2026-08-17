# Frontend Dockerfile - Next.js 14
# ──────────────────────────────────────────
FROM node:20-alpine AS base

# Dependencias
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# Builder
FROM base AS builder
WORKDIR /app
# NEXT_PUBLIC_API_URL: baked en el bundle del cliente al compilar
# Se usa como fallback solo en desarrollo local
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN mkdir -p public
RUN npm run build

# Runner (producción)
FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
ENV NODE_OPTIONS="--dns-result-order=ipv4first"

# INTERNAL_BACKEND_URL: URL interna del backend en Docker para el proxy /api/*
# Configurar en Dokploy como Environment Variable del servicio Frontend:
#   INTERNAL_BACKEND_URL=http://<nombre-servicio-fastapi-en-dokploy>:8000
ENV INTERNAL_BACKEND_URL=http://ocr-proyecto-fastapi-d5qhym:8000

CMD ["node", "server.js"]
