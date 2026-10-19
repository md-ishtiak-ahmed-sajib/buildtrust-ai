FROM node:24-bookworm-slim AS ui
WORKDIR /source/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /source
RUN pip install --no-cache-dir uv
COPY backend/ ./backend/
RUN uv sync --project backend --locked --no-dev
COPY --from=ui /source/frontend/dist ./frontend/dist
COPY scripts/container_start.sh ./scripts/container_start.sh
ENV BUILDTRUST_DATA_DIR=/source/data
EXPOSE 8000
CMD ["sh", "scripts/container_start.sh"]
