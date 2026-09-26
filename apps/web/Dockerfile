FROM node:24-slim AS deps
RUN corepack enable
WORKDIR /srv
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml .npmrc ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile

FROM node:24-slim AS build
RUN corepack enable
WORKDIR /srv
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY apps/web ./apps/web
COPY --from=deps /srv/node_modules ./node_modules
COPY --from=deps /srv/apps/web/node_modules ./apps/web/node_modules
RUN pnpm -C apps/web build

FROM node:24-slim
RUN corepack enable
WORKDIR /srv
COPY --from=build /srv/apps/web/.next ./apps/web/.next
COPY --from=build /srv/apps/web/public ./apps/web/public
COPY --from=build /srv/apps/web/package.json ./apps/web/package.json
# next.config.ts holds the /api/* rewrite — `next start` loads it at runtime.
COPY --from=build /srv/apps/web/next.config.ts ./apps/web/next.config.ts
COPY --from=build /srv/node_modules ./node_modules
COPY --from=build /srv/apps/web/node_modules ./apps/web/node_modules
COPY pnpm-workspace.yaml package.json ./
EXPOSE 3000
CMD ["pnpm", "-C", "apps/web", "start"]
