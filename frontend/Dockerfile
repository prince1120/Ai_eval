# syntax=docker/dockerfile:1
# Node 24 to match the version this project is developed against.
FROM node:24-alpine AS deps
# Next's SWC binaries are glibc-linked; alpine needs the compat shim.
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json package-lock.json ./
# Same idea as pip above: persist npm's download cache between builds so a
# single dependency change does not re-fetch the whole tree.
RUN --mount=type=cache,target=/root/.npm npm ci


FROM node:24-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Telemetry would otherwise phone home during every image build.
ENV NEXT_TELEMETRY_DISABLED=1
# NEXT_PUBLIC_* values are inlined at build time, not read at runtime. Left
# unset on purpose: lib/api.ts falls back to `http://<current-host>:8000/api/v1`,
# which works whether the app is opened on localhost or over the LAN. Override
# with --build-arg NEXT_PUBLIC_API_URL=... when deploying behind a real domain.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build


FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3001 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# standalone/server.js does not bundle public/ or .next/static; both have to be
# copied alongside it or the app serves HTML with no CSS, JS or images.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "require('http').get('http://127.0.0.1:3001/login',r=>process.exit(r.statusCode<500?0:1)).on('error',()=>process.exit(1))"

CMD ["node", "server.js"]
