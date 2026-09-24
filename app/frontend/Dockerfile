# Vite dev server for the canvas. The production build is `npm run build`,
# which emits static files that any web server can host; this image exists so
# `docker compose up` brings the whole system online.
FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# --host binds 0.0.0.0 so the port is reachable from outside the container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
