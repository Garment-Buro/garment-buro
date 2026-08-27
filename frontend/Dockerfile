FROM node:24-alpine AS dependencies

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24-alpine AS builder

WORKDIR /app

ARG NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=false
ARG NEXT_PUBLIC_CATALOG_WRITES_ENABLED=false
ARG NEXT_PUBLIC_CRM_CABINET_ENABLED=false
ARG NEXT_PUBLIC_YANDEX_MAPS_API_KEY=

ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_USE_MOCK_DATA=false
ENV NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED=$NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED
ENV NEXT_PUBLIC_CATALOG_WRITES_ENABLED=$NEXT_PUBLIC_CATALOG_WRITES_ENABLED
ENV NEXT_PUBLIC_CRM_CABINET_ENABLED=$NEXT_PUBLIC_CRM_CABINET_ENABLED
ENV NEXT_PUBLIC_YANDEX_MAPS_API_KEY=$NEXT_PUBLIC_YANDEX_MAPS_API_KEY
ENV INTERNAL_API_URL=http://backend:8000

COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24-alpine AS runner

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    INTERNAL_API_URL=http://backend:8000

WORKDIR /app

RUN addgroup --system --gid 10001 nodejs \
    && adduser --system --uid 10001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=6 \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
