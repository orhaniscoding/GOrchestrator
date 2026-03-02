"""Tests for the Team Registry module."""

import json
from pathlib import Path

import pytest

from src.core.team import TeamConfig, TeamRegistry


class TestTeamRegistry:
    """Tests for TeamRegistry CRUD and persistence."""

    def test_add_and_list(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        tc = reg.add("alpha", "default", sub_manager_names=["arch", "sec"])
        assert tc.name == "alpha"
        assert tc.main_manager_profile == "default"
        assert tc.sub_manager_names == ["arch", "sec"]
        assert tc.active is False
        assert len(reg.list_all()) == 1

    def test_add_duplicate_raises(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        reg.add("alpha", "default")
        with pytest.raises(ValueError, match="already exists"):
            reg.add("alpha", "other")

    def test_add_empty_name_raises(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        with pytest.raises(ValueError, match="cannot be empty"):
            reg.add("", "default")

    def test_add_defaults(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        tc = reg.add("beta", "default")
        assert tc.sub_manager_names == []
        assert tc.description == ""
        assert tc.active is False

    def test_get(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        reg.add("alpha", "default")
        assert reg.get("alpha") is not None
        assert reg.get("alpha").name == "alpha"
        assert reg.get("nonexistent") is None

    def test_remove(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        reg.add("alpha", "default")
        assert reg.remove("alpha") is True
        assert reg.remove("nonexistent") is False
        assert len(reg.list_all()) == 0

    def test_activate_deactivates_others(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        reg.add("alpha", "default")
        reg.add("beta", "default")
        assert reg.activate("alpha") is True
        assert reg.get("alpha").active is True
        assert reg.get("beta").active is False
        # Activate beta - alpha should deactivate
        assert reg.activate("beta") is True
        assert reg.get("alpha").active is False
        assert reg.get("beta").active is True

    def test_activate_nonexistent(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        assert reg.activate("nonexistent") is False

    def test_get_active(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        reg.add("alpha", "default")
        reg.add("beta", "default")
        assert reg.get_active() is None
        reg.activate("alpha")
        assert reg.get_active().name == "alpha"

    def test_deactivate_specific(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        reg.add("alpha", "default")
        reg.activate("alpha")
        assert reg.deactivate("alpha") is True
        assert reg.get("alpha").active is False

    def test_deactivate_nonexistent(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        assert reg.deactivate("nonexistent") is False

    def test_deactivate_all(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        reg.add("alpha", "default")
        reg.add("beta", "default")
        reg.activate("alpha")
        assert reg.deactivate() is True
        assert reg.get("alpha").active is False
        assert reg.get("beta").active is False

    def test_update_main_manager(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        reg.add("alpha", "default")
        assert reg.update_main_manager("alpha", "architect") is True
        assert reg.get("alpha").main_manager_profile == "architect"
        assert reg.update_main_manager("nonexistent", "x") is False

    def test_add_sub_manager(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        reg.add("alpha", "default")
        assert reg.add_sub_manager("alpha", "sec") is True
        assert "sec" in reg.get("alpha").sub_manager_names
        # Adding again should be idempotent (no duplicate)
        reg.add_sub_manager("alpha", "sec")
        assert reg.get("alpha").sub_manager_names.count("sec") == 1

    def test_add_sub_manager_nonexistent_team(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        assert reg.add_sub_manager("nonexistent", "sec") is False

    def test_remove_sub_manager(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        reg.add("alpha", "default", sub_manager_names=["sec", "arch"])
        assert reg.remove_sub_manager("alpha", "sec") is True
        assert "sec" not in reg.get("alpha").sub_manager_names
        assert "arch" in reg.get("alpha").sub_manager_names

    def test_remove_sub_manager_not_in_list(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        reg.add("alpha", "default")
        assert reg.remove_sub_manager("alpha", "nonexistent") is False

    def test_remove_sub_manager_nonexistent_team(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        assert reg.remove_sub_manager("nonexistent", "sec") is False

    def test_persistence(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        reg.add("alpha", "default", sub_manager_names=["arch"], description="Test team")
        reg.activate("alpha")
        # Create a new registry from the same file
        reg2 = TeamRegistry(registry_file)
        assert len(reg2.list_all()) == 1
        tc = reg2.get("alpha")
        assert tc.name == "alpha"
        assert tc.main_manager_profile == "default"
        assert tc.sub_manager_names == ["arch"]
        assert tc.description == "Test team"
        assert tc.active is True

    def test_persistence_json_structure(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        reg.add("alpha", "default", sub_manager_names=["arch"])
        with open(registry_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "alpha" in data
        assert data["alpha"]["name"] == "alpha"
        assert data["alpha"]["main_manager_profile"] == "default"
        assert data["alpha"]["sub_manager_names"] == ["arch"]

    def test_load_corrupted_file(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        registry_file.write_text("not valid json", encoding="utf-8")
        reg = TeamRegistry(registry_file)
        assert len(reg.list_all()) == 0

    def test_load_nonexistent_file(self, tmp_path):
        registry_file = tmp_path / "teams.json"
        reg = TeamRegistry(registry_file)
        assert len(reg.list_all()) == 0
