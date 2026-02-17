"""
Tests for provider_client module.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from mcq_generator.provider_client import ProviderClient, CircuitBreakerOpen, BatchProcessor


class TestProviderClient:
    """Test suite for ProviderClient."""

    def test_initialization(self):
        """Test ProviderClient initialization."""
        client = ProviderClient(base_url="http://localhost:7543")

        assert client.base_url == "http://localhost:7543"
        assert client.circuit_state == "closed"
        assert client.total_requests == 0

    def test_initialization_with_custom_params(self):
        """Test ProviderClient with custom parameters."""
        client = ProviderClient(
            base_url="http://custom:8000",
            timeout=60.0,
            max_connections=20,
            circuit_breaker_threshold=10,
        )

        assert client.base_url == "http://custom:8000"
        assert client.circuit_breaker_threshold == 10

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health check when service is healthy."""
        client = ProviderClient()

        with patch.object(client.client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = await client.health_check()

        assert result is True
        await client.close()

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check when service is down."""
        client = ProviderClient()

        with patch.object(client.client, "get") as mock_get:
            mock_get.side_effect = httpx.HTTPError("Connection failed")

            result = await client.health_check()

        assert result is False
        await client.close()

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test successful generation."""
        client = ProviderClient()

        with patch.object(client.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Test response"}}]
            }
            mock_post.return_value = mock_response

            result = await client.generate(messages=[{"role": "user", "content": "Hello"}])

        assert "choices" in result
        assert client.successful_requests == 1
        await client.close()

    @pytest.mark.asyncio
    async def test_generate_updates_stats(self):
        """Test that generation updates statistics."""
        client = ProviderClient()

        with patch.object(client.client, "post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"choices": [{"message": {"content": "test"}}]}
            mock_post.return_value = mock_response

            await client.generate(messages=[{"role": "user", "content": "test"}])

        assert client.total_requests == 1
        assert client.successful_requests == 1

    @pytest.mark.asyncio
    async def test_generate_failure(self):
        """Test generation failure handling."""
        client = ProviderClient()

        with patch.object(client.client, "post") as mock_post:
            mock_post.side_effect = httpx.HTTPError("Request failed")

            with pytest.raises(httpx.HTTPError):
                await client.generate(messages=[{"role": "user", "content": "test"}])

        assert client.failed_requests >= 1

    def test_get_stats(self):
        """Test getting client statistics."""
        client = ProviderClient()
        client.total_requests = 10
        client.successful_requests = 8
        client.failed_requests = 2

        stats = client.get_stats()

        assert stats["total_requests"] == 10
        assert stats["successful_requests"] == 8
        assert stats["failed_requests"] == 2
        assert stats["success_rate"] == 80.0
        assert stats["circuit_state"] == "closed"

    def test_get_stats_zero_requests(self):
        """Test getting stats with zero requests."""
        client = ProviderClient()

        stats = client.get_stats()

        assert stats["total_requests"] == 0
        assert stats["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_remote_stats(self):
        """Test getting remote provider stats."""
        client = ProviderClient()

        with patch.object(client.client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"requests": 100}
            mock_get.return_value = mock_response

            stats = await client.get_remote_stats()

        assert stats["requests"] == 100
        await client.close()

    @pytest.mark.asyncio
    async def test_get_remote_stats_failure(self):
        """Test getting remote stats on failure."""
        client = ProviderClient()

        with patch.object(client.client, "get") as mock_get:
            mock_get.side_effect = httpx.HTTPError("Failed")

            stats = await client.get_remote_stats()

        assert stats == {}
        await client.close()

    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker starts closed."""
        client = ProviderClient()
        assert client.circuit_state == "closed"
        assert client.failure_count == 0

    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after threshold failures."""
        client = ProviderClient(circuit_breaker_threshold=3)

        client._handle_failure(Exception("Error 1"))
        assert client.circuit_state == "closed"

        client._handle_failure(Exception("Error 2"))
        assert client.circuit_state == "closed"

        client._handle_failure(Exception("Error 3"))
        assert client.circuit_state == "open"

    def test_circuit_breaker_close(self):
        """Test manually closing circuit breaker."""
        client = ProviderClient()
        client.circuit_state = "half-open"

        client._close_circuit()

        assert client.circuit_state == "closed"
        assert client.failure_count == 0
        assert client.circuit_opened_at is None

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test ProviderClient as async context manager."""
        async with ProviderClient() as client:
            assert client is not None


class TestBatchProcessor:
    """Test suite for BatchProcessor."""

    def test_initialization(self):
        """Test BatchProcessor initialization."""
        client = ProviderClient()
        processor = BatchProcessor(client, batch_size=5)

        assert processor.batch_size == 5
        assert processor.client is client

    def test_create_batch_prompt(self):
        """Test creating batch prompt."""
        client = ProviderClient()
        processor = BatchProcessor(client)

        documents = ["Doc 1", "Doc 2"]
        prompt = processor._create_batch_prompt(documents, "Generate MCQ for: {document}")

        assert "DOCUMENT 1:" in prompt
        assert "DOCUMENT 2:" in prompt
        assert "Doc 1" in prompt
        assert "Doc 2" in prompt

    def test_parse_batch_response(self):
        """Test parsing batch response."""
        client = ProviderClient()
        processor = BatchProcessor(client)

        response = {
            "choices": [
                {
                    "message": {
                        "content": """MCQ 1:
Question 1
A) Option
CORRECT: A

MCQ 2:
Question 2
B) Option
CORRECT: B
"""
                    }
                }
            ]
        }

        results = processor._parse_batch_response(response, 2)

        assert len(results) == 2

    def test_parse_single_response(self):
        """Test parsing single response."""
        client = ProviderClient()
        processor = BatchProcessor(client)

        response = {"choices": [{"message": {"content": "Test content"}}]}

        result = processor._parse_single_response(response)

        assert "raw" in result


class TestCircuitBreakerOpen:
    """Test suite for CircuitBreakerOpen exception."""

    def test_exception_message(self):
        """Test CircuitBreakerOpen exception message."""
        msg = "Circuit is open"
        exc = CircuitBreakerOpen(msg)

        assert str(exc) == msg
        assert issubclass(CircuitBreakerOpen, Exception)
