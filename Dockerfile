FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Copy requirements first so we can leverage caching
COPY requirements.txt ./

# Upgrade pip and install all dependencies via requirements
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the source code
COPY . .

# Set PYTHONPATH so the package can be imported from source
ENV PYTHONPATH=/app/src

# Make sure our helper scripts are executable if they exist
RUN if [ -f ./scripts/run_api.sh ]; then chmod +x ./scripts/run_api.sh; fi

# Expose default port (documentation only)
EXPOSE 8000

# Default command (override with docker-compose or docker run)
CMD ["bash"]
