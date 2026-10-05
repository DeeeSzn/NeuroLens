FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

ARG NEUROLENS_BACKEND_URL=http://backend:8000
ENV NEUROLENS_BACKEND_URL=$NEUROLENS_BACKEND_URL
COPY next.config.js tsconfig.json next-env.d.ts postcss.config.* .eslintrc.json ./
COPY src/ src/
COPY public/ public/
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
