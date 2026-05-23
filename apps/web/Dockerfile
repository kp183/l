# ── AgentLens Web — development image ────────────────────────────────────────
FROM node:20-slim

WORKDIR /app

# Copy package manifest first for layer caching
COPY package.json .

RUN npm install

# Source is mounted as a volume at runtime for hot reload
COPY . .

CMD ["npm", "run", "dev"]
