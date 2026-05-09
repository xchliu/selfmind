FROM python:3.11-slim

LABEL description="SelfMind — Memory Evolution Server"
LABEL version="2.5.0"

# Pure Python stdlib — no pip install needed
# Honcho data fetched via API fallback (no psql required)
# Honcho is optional — if HONCHO_ENABLED=false, SelfMind skips it gracefully

WORKDIR /app

COPY server.py .
COPY selfmind_app/ ./selfmind_app/
COPY static/ ./static/
COPY index.html .
COPY assets/ ./assets/

# Create data directory (bind-mounted at runtime for persistence)
RUN mkdir -p /app/data

EXPOSE 3002

# Runtime configuration via environment variables
# All paths are resolved inside the container via volume mounts
# HERMES_HOME controls memory/skills paths; SELFMIND_WIKI_PATH controls wiki
# HONCHO_API_URL points to Honcho on the host via host.docker.internal
# HONCHO_ENABLED can disable Honcho data source entirely
ENV SELFMIND_SOURCE_MODE=auto
ENV SELFMIND_PROFILE=hermes
ENV HERMES_HOME=/hermes
ENV SELFMIND_WIKI_PATH=/hermes/wiki
ENV HONCHO_ENABLED=true
ENV HONCHO_API_URL=http://host.docker.internal:8000/v3
ENV HONCHO_WORKSPACE=hermes

CMD ["python3", "server.py"]