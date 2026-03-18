FROM mcr.microsoft.com/playwright/python:v1.50.0-noble

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml ./
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini ./

# Install dependencies
RUN uv pip install --system .

# Install Playwright Chromium
RUN playwright install chromium

# Create data directory
RUN mkdir -p data

# Copy entrypoint
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

ENTRYPOINT ["card-retrieval"]
CMD ["list-adapters"]
