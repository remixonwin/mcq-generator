FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Copy project metadata and requirements first to take advantage of build cache
COPY pyproject.toml requirements.txt ./

# Upgrade pip and install the package along with its dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir .

# Copy the rest of the source code
COPY . .

# Make sure our helper scripts are executable if they exist
RUN if [ -f ./scripts/run_api.sh ]; then chmod +x ./scripts/run_api.sh; fi

# Expose default port (documentation only)
EXPOSE 8000

# Default command (override with docker-compose or docker run)
CMD ["bash"]
