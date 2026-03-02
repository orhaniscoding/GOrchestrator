"""Tests for the LLM Pool module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.llm_pool import LLMConfig, LLMPool, LLMResponse


class TestLLMPoolCRUD:
    """Tests for LLMPool CRUD operations."""

    def test_add_llm(self):
        pool = LLMPool()
        cfg = pool.add("gpt4", "gpt-4o")
        assert cfg.name == "gpt4"
        assert cfg.model == "gpt-4o"
        assert pool.count() == 1

    def test_add_duplicate_raises(self):
        pool = LLMPool()
        pool.add("gpt4", "gpt-4o")
        with pytest.raises(ValueError, match="already exists"):
            pool.add("gpt4", "gpt-4o-mini")

    def test_remove_llm(self):
        pool = LLMPool()
        pool.add("gpt4", "gpt-4o")
        assert pool.remove("gpt4") is True
        assert pool.count() == 0

    def test_remove_nonexistent_returns_false(self):
        pool = LLMPool()
        assert pool.remove("nonexistent") is False

    def test_update_llm(self):
        pool = LLMPool()
        pool.add("gpt4", "gpt-4o")
        assert pool.update("gpt4", model="gpt-4o-mini") is True
        cfg = pool.get("gpt4")
        assert cfg.model == "gpt-4o-mini"

    def test_list_all(self):
        pool = LLMPool()
        pool.add("gpt4", "gpt-4o")
        pool.add("claude", "claude-3-5-sonnet-20241022")
        all_llms = pool.list_all()
        assert len(all_llms) == 2
        names = {c.name for c in all_llms}
        assert names == {"gpt4", "claude"}

    def test_get(self):
        pool = LLMPool()
        pool.add("gpt4", "gpt-4o")
        cfg = pool.get("gpt4")
        assert cfg is not None
        assert cfg.name == "gpt4"
        assert pool.get("nonexistent") is None

    def test_is_empty(self):
        pool = LLMPool()
        assert pool.is_empty() is True
        pool.add("gpt4", "gpt-4o")
        assert pool.is_empty() is False

    def test_count(self):
        pool = LLMPool()
        assert pool.count() == 0
        pool.add("gpt4", "gpt-4o")
        assert pool.count() == 1
        pool.add("claude", "claude-3-5-sonnet-20241022")
        assert pool.count() == 2

    def test_name_sanitization(self):
        pool = LLMPool()
        cfg = pool.add("my.llm!", "gpt-4o")
        assert cfg.name == "my-llm-"
        assert pool.get("my-llm-") is not None


class TestLLMPoolPersistence:
    """Tests for file-backed persistence."""

    def test_save_and_load(self, tmp_path):
        registry_file = tmp_path / "llms.json"
        pool = LLMPool(registry_file=registry_file)
        pool.add("gpt4", "gpt-4o", api_base="https://api.openai.com/v1")
        pool.add("claude", "claude-3-5-sonnet-20241022")

        # Create new pool from same file
        pool2 = LLMPool(registry_file=registry_file)
        assert pool2.count() == 2
        gpt4 = pool2.get("gpt4")
        assert gpt4 is not None
        assert gpt4.api_base == "https://api.openai.com/v1"

    def test_load_nonexistent_file(self, tmp_path):
        registry_file = tmp_path / "nonexistent.json"
        pool = LLMPool(registry_file=registry_file)
        assert pool.count() == 0


class TestLLMPoolInMemory:
    """Tests for in-memory mode."""

    def test_in_memory_mode(self):
        configs = [
            LLMConfig(name="gpt4", model="gpt-4o"),
            LLMConfig(name="claude", model="claude-3-5-sonnet-20241022"),
        ]
        pool = LLMPool(configs=configs)
        assert pool.count() == 2
        assert pool.get("gpt4") is not None


class TestLLMPoolSerialization:
    """Tests for serialization/deserialization."""

    def test_to_dict_list(self):
        pool = LLMPool()
        pool.add("gpt4", "gpt-4o", api_base="https://api.openai.com/v1")
        result = pool.to_dict_list()
        assert len(result) == 1
        assert result[0]["name"] == "gpt4"
        assert result[0]["model"] == "gpt-4o"
        assert result[0]["api_base"] == "https://api.openai.com/v1"

    def test_from_dict_list(self):
        data = [
            {"name": "gpt4", "model": "gpt-4o"},
            {"name": "claude", "model": "claude-3-5-sonnet-20241022"},
        ]
        pool = LLMPool.from_dict_list(data)
        assert pool.count() == 2
        assert pool.get("claude").model == "claude-3-5-sonnet-20241022"

    def test_roundtrip_serialization(self):
        pool = LLMPool()
        pool.add("gpt4", "gpt-4o", api_base="https://api.openai.com/v1", api_key="sk-test")
        pool.add("claude", "claude-3-5-sonnet-20241022", temperature=0.7, max_tokens=8192)

        data = pool.to_dict_list()
        pool2 = LLMPool.from_dict_list(data)
        assert pool2.count() == 2
        gpt4 = pool2.get("gpt4")
        assert gpt4.api_base == "https://api.openai.com/v1"
        assert gpt4.api_key == "sk-test"
        claude = pool2.get("claude")
        assert claude.temperature == 0.7
        assert claude.max_tokens == 8192


class TestLLMPoolParallelExecution:
    """Tests for parallel LLM execution (mocked call_litellm)."""

    @patch("src.core.llm_pool.call_litellm")
    def test_execute_parallel_single(self, mock_call):
        mock_call.return_value = ("Hello from GPT-4o", 1.5)

        pool = LLMPool()
        pool.add("gpt4", "gpt-4o", api_base="http://localhost:8045", api_key="sk-test")

        results = pool.execute_parallel(
            messages=[{"role": "user", "content": "Hello"}]
        )
        assert len(results) == 1
        assert results[0].name == "gpt4"
        assert results[0].content == "Hello from GPT-4o"
        assert results[0].error is None

    @patch("src.core.llm_pool.call_litellm")
    def test_execute_parallel_multiple(self, mock_call):
        mock_call.return_value = ("Response", 1.0)

        pool = LLMPool()
        pool.add("gpt4", "gpt-4o", api_base="http://localhost:8045", api_key="sk-test")
        pool.add("claude", "claude-3-5-sonnet-20241022", api_base="http://localhost:8045", api_key="sk-test")

        results = pool.execute_parallel(
            messages=[{"role": "user", "content": "Hello"}]
        )
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"gpt4", "claude"}

    @patch("src.core.llm_pool.call_litellm")
    def test_execute_parallel_with_error(self, mock_call):
        mock_call.side_effect = ConnectionError("API down")

        pool = LLMPool()
        pool.add("gpt4", "gpt-4o", api_base="http://localhost:8045", api_key="sk-test")

        results = pool.execute_parallel(
            messages=[{"role": "user", "content": "Hello"}]
        )
        assert len(results) == 1
        assert results[0].error is not None
        assert "API down" in results[0].error

    def test_execute_parallel_empty_pool(self):
        pool = LLMPool()
        results = pool.execute_parallel(
            messages=[{"role": "user", "content": "Hello"}]
        )
        assert results == []

    @patch("src.core.llm_pool.call_litellm")
    def test_on_response_callback(self, mock_call):
        mock_call.return_value = ("Hello", 0.5)

        pool = LLMPool()
        pool.add("gpt4", "gpt-4o", api_base="http://localhost:8045", api_key="sk-test")

        callback_results = []
        def on_response(resp):
            callback_results.append(resp)

        pool.execute_parallel(
            messages=[{"role": "user", "content": "Hello"}],
            on_response=on_response,
        )
        assert len(callback_results) == 1
        assert callback_results[0].name == "gpt4"
