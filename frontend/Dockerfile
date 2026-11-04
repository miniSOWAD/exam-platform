FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm install
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_URL=/api/v1
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ARG API_INTERNAL_URL=https://examflow-api.fastapicloud.dev
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL API_INTERNAL_URL=$API_INTERNAL_URL
RUN npm run build
FROM node:20-alpine AS runner
WORKDIR /app
ARG API_INTERNAL_URL=https://examflow-api.fastapicloud.dev
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 API_INTERNAL_URL=$API_INTERNAL_URL
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node","server.js"]
