"""
Tests for dataset_search module.
"""

import pytest
from unittest.mock import patch, MagicMock
from mcq_generator.dataset_search import search_datasets, get_dataset_info


class TestSearchDatasets:
    """Test suite for search_datasets function."""

    @patch("mcq_generator.dataset_search.list_datasets")
    def test_search_datasets_success(self, mock_list):
        """Test successful dataset search."""
        mock_ds = MagicMock()
        mock_ds.id = "test/dataset"
        mock_ds.downloads = 1000
        mock_ds.likes = 100
        mock_ds.tags = ["text", "classification"]
        mock_ds.private = False
        mock_ds.author = "testuser"
        mock_ds.sha = "abc123"

        mock_list.return_value = [mock_ds]

        results = search_datasets(query="test", limit=10)

        assert len(results) == 1
        assert results[0]["id"] == "test/dataset"
        assert results[0]["downloads"] == 1000

    @patch("mcq_generator.dataset_search.list_datasets")
    def test_search_datasets_with_offset(self, mock_list):
        """Test search with offset."""
        mock_ds1 = MagicMock()
        mock_ds1.id = "first"
        mock_ds1.downloads = 1000
        mock_ds1.likes = 100
        mock_ds1.tags = []
        mock_ds1.private = False
        mock_ds1.author = ""
        mock_ds1.sha = ""

        mock_ds2 = MagicMock()
        mock_ds2.id = "second"
        mock_ds2.downloads = 500
        mock_ds2.likes = 50
        mock_ds2.tags = []
        mock_ds2.private = False
        mock_ds2.author = ""
        mock_ds2.sha = ""

        mock_list.return_value = [mock_ds1, mock_ds2]

        results = search_datasets(query="test", limit=10, offset=1)

        assert len(results) == 1
        assert results[0]["id"] == "second"

    @patch("mcq_generator.dataset_search.list_datasets")
    def test_search_datasets_error(self, mock_list):
        """Test search handles errors gracefully."""
        mock_list.side_effect = Exception("API Error")

        results = search_datasets(query="test")

        assert results == []

    @patch("mcq_generator.dataset_search.list_datasets")
    def test_search_datasets_empty_query(self, mock_list):
        """Test search with empty query."""
        mock_ds = MagicMock()
        mock_ds.id = "test"
        mock_ds.downloads = 100
        mock_ds.likes = 10
        mock_ds.tags = []
        mock_ds.private = False
        mock_ds.author = ""
        mock_ds.sha = ""

        mock_list.return_value = [mock_ds]

        results = search_datasets()

        assert len(results) >= 1


class TestGetDatasetInfo:
    """Test suite for get_dataset_info function."""

    @patch("mcq_generator.dataset_search.list_datasets")
    def test_get_dataset_info_found(self, mock_list):
        """Test getting info for existing dataset."""
        mock_ds = MagicMock()
        mock_ds.id = "stanfordnlp/imdb"
        mock_ds.downloads = 50000
        mock_ds.likes = 5000
        mock_ds.tags = ["text", "sentiment"]
        mock_ds.private = False
        mock_ds.author = "stanfordnlp"
        mock_ds.sha = "xyz789"

        mock_list.return_value = [mock_ds]

        info = get_dataset_info("stanfordnlp/imdb")

        assert info is not None
        assert info["id"] == "stanfordnlp/imdb"
        assert info["downloads"] == 50000

    @patch("mcq_generator.dataset_search.list_datasets")
    def test_get_dataset_info_case_insensitive(self, mock_list):
        """Test dataset info lookup is case insensitive."""
        mock_ds = MagicMock()
        mock_ds.id = "Test/Dataset"
        mock_ds.downloads = 100
        mock_ds.likes = 10
        mock_ds.tags = []
        mock_ds.private = False
        mock_ds.author = ""
        mock_ds.sha = ""

        mock_list.return_value = [mock_ds]

        info = get_dataset_info("test/dataset")

        assert info is not None

    @patch("mcq_generator.dataset_search.list_datasets")
    def test_get_dataset_info_not_found(self, mock_list):
        """Test getting info for nonexistent dataset."""
        mock_ds = MagicMock()
        mock_ds.id = "other/dataset"
        mock_ds.downloads = 100
        mock_ds.likes = 10
        mock_ds.tags = []
        mock_ds.private = False
        mock_ds.author = ""
        mock_ds.sha = ""

        mock_list.return_value = [mock_ds]

        info = get_dataset_info("nonexistent/dataset")

        assert info is None

    @patch("mcq_generator.dataset_search.list_datasets")
    def test_get_dataset_info_error(self, mock_list):
        """Test get_dataset_info handles errors gracefully."""
        mock_list.side_effect = Exception("API Error")

        info = get_dataset_info("test/dataset")

        assert info is None
