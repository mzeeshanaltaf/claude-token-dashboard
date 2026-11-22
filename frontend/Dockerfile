# Claude Lens frontend (Next.js standalone). Built by the root docker-compose.yml.
# No build-time secrets: BACKEND_URL is read per request at runtime.
# `next/font/google` downloads the fonts during `pnpm build`, so the build needs network.

FROM node:24-slim AS base
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm install -g pnpm@10.5.2
WORKDIR /app

FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM base AS build
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# public/ is empty in git (the favicon is app/icon.svg), so make sure it exists.
RUN mkdir -p public && pnpm build

FROM node:24-slim AS runner
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /app
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/login').then(r => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]

# Not `next start`: it doesn't support output: "standalone".
CMD ["node", "server.js"]
