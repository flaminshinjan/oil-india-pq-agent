# Frontend — Next.js 14 (app router) standalone build.

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
# package-lock.json is gitignored locally; fall back to install if missing.
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi


FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# BACKEND_URL needs to be present at build time too because rewrites are
# resolved when `next.config.js` is read. We default to the production URL.
ARG BACKEND_URL=https://oil-india-pq-backend.fly.dev
ENV BACKEND_URL=${BACKEND_URL}

RUN npm run build


FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=8080 \
    HOSTNAME=0.0.0.0

# Re-declare so it's available at runtime for next.config.js (rewrites).
ARG BACKEND_URL=https://oil-india-pq-backend.fly.dev
ENV BACKEND_URL=${BACKEND_URL}

RUN addgroup -S nodejs && adduser -S nextjs -G nodejs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 8080
CMD ["node", "server.js"]
