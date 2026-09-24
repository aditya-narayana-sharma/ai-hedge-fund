FROM python:3.11-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry==1.7.1

# Copy only dependency files first for better caching
COPY pyproject.toml poetry.lock* /app/

# Configure Poetry to not use a virtual environment.
# --no-root is required here: pyproject declares packages = [src, app], which
# do not exist yet at this layer. Installing them is deferred until after the
# source copy so the dependency layer stays cacheable.
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy rest of the source code
COPY . /app/

RUN poetry install --no-interaction --no-ansi --only-root

# Default command (will be overridden by Docker Compose)
CMD ["python", "src/main.py"] 