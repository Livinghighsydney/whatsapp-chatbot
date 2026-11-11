# ---- build ----
FROM node:24-alpine AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Baked into the client bundle at build time — not a secret
ARG VITE_API_BASE_URL=https://web-production-9e95d.up.railway.app
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Override the default Cloudflare Workers target from @lovable.dev/vite-tanstack-config
ENV NITRO_PRESET=node-server

RUN npm run build

# ---- run ----
FROM node:24-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/.output ./.output

EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
