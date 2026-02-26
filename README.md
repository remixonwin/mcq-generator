 # MCQ Generator

High-Performance MCQ Generator with Intelligent Caching and State Management

## Overview

The MCQ Generator is a powerful FastAPI-based service for generating multiple-choice questions from datasets. It features intelligent caching, pause/resume capabilities, and support for multiple export formats.

## Features

- **Dataset Search**: Search and filter datasets from HuggingFace Hub
- **Job Management**: Create, monitor, and manage generation jobs with pause/resume support
- **Multiple Export Formats**: JSON, CSV, Markdown, and PDF exports
- **Intelligent Caching**: Redis-based caching for improved performance
- **Async Processing**: Celery-powered background task processing
- **Real-time Metrics**: Monitor system performance and job statistics
- **API Documentation**: Auto-generated OpenAPI documentation
- **Multiple LLM Providers**: Support for OpenAI, Groq, Gemini, and more

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Redis server
- API keys for LLM providers

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd mcq-generator
   ```

2. **Install dependencies**:
   ```bash
   pip install -e .
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Start Redis**:
   ```bash
   redis-server
   ```

5. **Run the application**:
   ```bash
   uvicorn mcq_generator.asgi:app --reload --host 0.0.0.0 --port 8000
   ```

### Using Docker

1. **Build and run with Docker Compose**:
   ```bash
   docker-compose up --build
   ```

2. **Access the API**:
   - API: http://localhost:8000
   - Documentation: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# API Keys (required)
HF_TOKEN=your_huggingface_token
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
GEMINI_API_KEY=your_gemini_api_key

# Optional Configuration
LLM_MODEL=gpt-4  # Default model to use
PROVIDER_URL=http://localhost:7330  # Custom provider URL
CORS_ORIGINS=http://localhost:3000,http://localhost:5173  # CORS origins

# Performance Tuning
CONSECUTIVE_FAILURE_LIMIT=100  # Max consecutive failures before backoff
BACKOFF_INITIAL_SECONDS=30
BACKOFF_MULTIPLIER=2
BACKOFF_MAX_SECONDS=1800
BACKOFF_TRIGGER=50

# Content Processing
TEXT_COLUMN_WHITELIST=title,headline,summary,abstract,text,content
MAX_SYNTH_COLUMNS=6
CONTENT_FAILURE_LIMIT=200
DUMP_RETENTION=200
```

### API Keys Setup

1. **HuggingFace Token**: Get from https://huggingface.co/settings/tokens
2. **Groq API Key**: Get from https://console.groq.com/keys
3. **OpenRouter API Key**: Get from https://openrouter.ai/keys
4. **Gemini API Key**: Get from https://aistudio.google.com/app/apikey

## API Usage

### Base URL
```
http://localhost:8000
```

### Main Endpoints

#### Health Check
```bash
GET /health
```

#### Search Datasets
```bash
GET /api/v1/datasets/search?query=science&limit=10
```

#### Create Generation Job
```bash
POST /api/v1/jobs
{
  "dataset_id": "your-dataset-id",
  "config": {
    "num_questions": 50,
    "difficulty": "medium"
  }
}
```

#### Get Job Status
```bash
GET /api/v1/jobs/{job_id}
```

#### Export Results
```bash
GET /api/v1/exports/{job_id}?format=json
GET /api/v1/exports/{job_id}?format=csv
GET /api/v1/exports/{job_id}?format=markdown
GET /api/v1/exports/{job_id}?format=pdf
```

#### Get Metrics
```bash
GET /metrics
```

### Interactive Documentation

Visit http://localhost:8000/docs for interactive API documentation with examples.

## Development

### Project Structure

```
src/mcq_generator/
├── api/                    # FastAPI application
│   ├── routers/           # API route handlers
│   ├── services/          # Business logic
│   └── schemas.py         # Pydantic models
├── generator/             # Core MCQ generation logic
├── exporters/            # Export functionality
├── storage/              # State management
├── cache_manager.py      # Caching logic
├── config.py            # Configuration management
└── tasks.py             # Celery tasks
```

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=mcq_generator
```

### Code Quality

```bash
# Linting
ruff check .

# Formatting
ruff format .

# Type checking
mypy src/
```

### Development Server

```bash
# Start API server
uvicorn mcq_generator.asgi:app --reload --port 8000

# Start Celery worker (in separate terminal)
celery -A mcq_generator.celery_app worker --loglevel=info
```

## Deployment

### Docker Production

1. **Build image**:
   ```bash
   docker build -t mcq-generator .
   ```

2. **Run with environment variables**:
   ```bash
   docker run -d \
     -p 8000:8000 \
     -e HF_TOKEN=your_token \
     -e GROQ_API_KEY=your_key \
     --name mcq-generator \
     mcq-generator
   ```

### Environment Variables for Production

- Set `CORS_ORIGINS` to your frontend domain
- Use secure Redis configuration
- Set appropriate log levels
- Configure monitoring and alerting

## Monitoring

### Health Endpoints

- `/health` - Basic health check
- `/metrics` - Application metrics

### Logging

The application uses structured logging with the following levels:
- INFO: General operation information
- WARNING: Recoverable issues
- ERROR: Serious problems requiring attention

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**:
   - Ensure Redis is running: `redis-server`
   - Check Redis configuration in environment

2. **API Key Errors**:
   - Verify all required API keys are set in `.env`
   - Check API key permissions and quotas

3. **Memory Issues**:
   - Reduce `MAX_SYNTH_COLUMNS` in configuration
   - Monitor Redis memory usage
   - Consider increasing system RAM

4. **Slow Performance**:
   - Check Redis connection
   - Monitor LLM provider response times
   - Consider reducing concurrent job limits

### Debug Mode

Enable debug mode by setting:
```bash
export DEBUG=1
uvicorn mcq_generator.asgi:app --reload
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Create an issue on GitHub
- Check the API documentation at `/docs`
- Review the troubleshooting section above
