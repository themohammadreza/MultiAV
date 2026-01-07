# Admin frontend build
FROM node:20-alpine AS builder
ARG API_PROXY_TARGET
ENV API_PROXY_TARGET=${API_PROXY_TARGET}
ENV NEXT_PUBLIC_API_PROXY_TARGET=${API_PROXY_TARGET}
WORKDIR /app
COPY package.json package-lock.json* pnpm-lock.yaml* yarn.lock* ./
RUN npm ci
COPY . .
RUN npm run build

# Runtime image
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3001
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3001
CMD ["node", "server.js"]
