"""Tests for the Sub-Manager Registry module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.sub_manager import SubManagerConfig, SubManagerRegistry, SubManagerResponse


class TestSubManagerRegistry:
    """Tests for SubManagerRegistry CRUD and persistence."""

    def test_add_and_list(self, tmp_path):
        registry_file = tmp_path / "sub_managers.json"
        reg = SubManagerRegistry(registry_file)
        sm = reg.add("architect", "architect", "claude-3-5-sonnet-20241022", description="Architecture advisor")
        assert sm.name == "architect"
        assert sm.profile == "architect"
        assert sm.model == "claude-3-5-sonnet-20241022"
        assert sm.active is False
        all_sms = reg.list_all()
        assert len(all_sms) == 1
        assert all_sms[0].name == "architect"

    def test_remove(self, tmp_path):
        registry_file = tmp_path / "sub_managers.json"
        reg = SubManagerRegistry(registry_file)
        reg.add("architect", "architect", "claude-3-5-sonnet-20241022")
        assert reg.remove("architect") is True
        assert reg.remove("nonexistent") is False
        assert len(reg.list_all()) == 0

    def test_set_active_inactive(self, tmp_path):
        registry_file = tmp_path / "sub_managers.json"
        reg = SubManagerRegistry(registry_file)
        reg.add("architect", "architect", "claude-3-5-sonnet-20241022")
        assert reg.set_active("architect") is True
        assert reg.get("architect").active is True
        assert reg.set_inactive("architect") is True
        assert reg.get("architect").active is False
        # Nonexistent
        assert reg.set_active("nonexistent") is False
        assert reg.set_inactive("nonexistent") is False

    def test_activate_only(self, tmp_path):
        registry_file = tmp_path / "sub_managers.json"
        reg = SubManagerRegistry(registry_file)
        reg.add("architect", "architect", "claude-3-5-sonnet-20241022")
        reg.add("security", "security", "gpt-4o")
        reg.add("reviewer", "reviewer", "gemini-2.0-flash")
        reg.set_active("architect")
        reg.set_active("security")
        reg.set_active("reviewer")

        # Activate only architect and security
        reg.activate_only(["architect", "security"])
        assert reg.get("architect").active is True
        assert reg.get("security").active is True
        assert reg.get("reviewer").active is False

    def test_parallel_llm_crud(self, tmp_path):
        registry_file = tmp_path / "sub_managers.json"
        reg = SubManagerRegistry(registry_file)
        reg.add("architect", "architect", "claude-3-5-sonnet-20241022")

        # Add parallel LLM
        assert reg.add_parallel_llm("architect", "gpt4", "gpt-4o") is True
        llms = reg.list_parallel_llms("architect")
        assert len(llms) == 1
        assert llms[0]["name"] == "gpt4"

        # Duplicate
        assert reg.add_parallel_llm("architect", "gpt4", "gpt-4o-mini") is False

        # Remove
        assert reg.remove_parallel_llm("architect", "gpt4") is True
        llms = reg.list_parallel_llms("architect")
        assert len(llms) == 0

        # Remove nonexistent
        assert reg.remove_parallel_llm("architect", "nonexistent") is False

        # Nonexistent sub-manager
        assert reg.list_parallel_llms("nonexistent") is None
        assert reg.add_parallel_llm("nonexistent", "x", "y") is False
        assert reg.remove_parallel_llm("nonexistent", "x") is False

    def test_persistence(self, tmp_path):
        registry_file = tmp_path / "sub_managers.json"
        reg = SubManagerRegistry(registry_file)
        reg.add("architect", "architect", "claude-3-5-sonnet-20241022", description="Arch advisor")
        reg.set_active("architect")
        reg.update_model("architect", "gpt-4o")
        reg.update_api("architect", "https://api.openai.com/v1", "sk-test")

        # Reload from disk
        reg2 = SubManagerRegistry(registry_file)
        sm = reg2.get("architect")
        assert sm is not None
        assert sm.active is True
        assert sm.model == "gpt-4o"
        assert sm.api_base == "https://api.openai.com/v1"
        assert sm.api_key == "sk-test"
        assert sm.description == "Arch advisor"

    def test_update_model(self, tmp_path):
        registry_file = tmp_path / "sub_managers.json"
        reg = SubManagerRegistry(registry_file)
        reg.add("architect", "architect", "claude-3-5-sonnet-20241022")
        assert reg.update_model("architect", "gpt-4o") is True
        assert reg.get("architect").model == "gpt-4o"
        assert reg.update_model("nonexistent", "gpt-4o") is False

    def test_update_profile(self, tmp_path):
        registry_file = tmp_path / "sub_managers.json"
        reg = SubManagerRegistry(registry_file)
        reg.add("architect", "architect", "claude-3-5-sonnet-20241022")
        assert reg.update_profile("architect", "security") is True
        assert reg.get("architect").profile == "security"
        assert reg.update_profile("nonexistent", "security") is False

    def test_update_description(self, tmp_path):
        registry_file = tmp_path / "sub_managers.json"
        reg = SubManagerRegistry(registry_file)
        reg.add("architect", "architect", "claude-3-5-sonnet-20241022")
        assert reg.update_description("architect", "New description") is True
        assert reg.get("architect").description == "New description"
        assert reg.update_description("nonexistent", "desc") is False

    def test_set_all_inactive(self, tmp_path):
        registry_file = tmp_path / "sub_managers.json"
        reg = SubManagerRegistry(registry_file)
        reg.add("a", "p1", "m1")
        reg.add("b", "p2", "m2")
        reg.set_active("a")
        reg.set_active("b")
        reg.set_all_inactive()
        assert all(not sm.active for sm in reg.list_all())

    def test_name_sanitization(self, tmp_path):
        registry_file = tmp_path / "sub_managers.json"
        reg = SubManagerRegistry(registry_file)
        sm = reg.add("my.advisor!", "profile", "model")
        assert sm.name == "my-advisor-"

    def test_add_duplicate_raises(self, tmp_path):
        registry_file = tmp_path / "sub_managers.json"
        reg = SubManagerRegistry(registry_file)
        reg.add("architect", "architect", "claude-3-5-sonnet-20241022")
        with pytest.raises(ValueError, match="already exists"):
            reg.add("architect", "security", "gpt-4o")

    def test_get_active(self, tmp_path):
        registry_file = tmp_path / "sub_managers.json"
        reg = SubManagerRegistry(registry_file)
        reg.add("a", "p1", "m1")
        reg.add("b", "p2", "m2")
        reg.set_active("b")
        active = reg.get_active()
        assert len(active) == 1
        assert active[0].name == "b"
