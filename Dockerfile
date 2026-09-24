FROM python:3.11-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry==1.7.1

# Copy only dependency files first for better caching
COPY pyproject.toml poetry.lock* /app/

# Install dependencies only. --no-root matters because pyproject.toml declares
# `packages = [src, app]`, and neither directory has been copied yet at this
# layer; installing the project here would fail or silently install nothing.
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy rest of the source code
COPY . /app/

# Now that the source exists, install the project itself.
RUN poetry install --no-interaction --no-ansi --only-root

# Charts must render without a display inside the container.
ENV MPLBACKEND=Agg

# Default command (will be overridden by Docker Compose)
CMD ["python", "src/main.py"]
