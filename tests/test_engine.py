"""Tests for the Session Engine module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from src.core.engine import SessionEngine, SessionMode


class TestSessionEngine:
    """Tests for SessionEngine."""

    @pytest.fixture(autouse=True)
    def _mock_write_env(self):
        """Prevent tests from modifying the real .env file."""
        with patch("src.core.engine.write_env_value"):
            yield

    def _make_engine(self, tmp_path):
        settings = MagicMock()
        settings.ORCHESTRATOR_MODEL = "test-model"
        settings.ORCHESTRATOR_API_BASE = "http://localhost:8045"
        settings.ORCHESTRATOR_API_KEY = "sk-test"
        settings.WORKER_MODEL = "test-model"
        settings.WORKER_PROFILE = "live"
        settings.MANAGER_PROFILE = ""  # Empty to use ORCHESTRATOR_* fallback
        settings.get_manager_config.return_value = {
            "model": "test-model",
            "api_base": "http://localhost:8045",
            "api_key": "sk-test",
            "system_prompt": None,
            "temperature": None,
            "max_tokens": None,
            "thinking": None,
        }
        settings.get_orchestrator_config = settings.get_manager_config  # Legacy alias
        settings.AGENT_PATH = "../test"
        settings.PROXY_URL = "http://localhost:8045"
        settings.PROXY_KEY = "sk-test"
        settings.BYPASS_KEY = "sk-test"
        settings.VERBOSE_WORKER = False
        settings.MAX_WORKER_ITERATIONS = 5
        settings.WORKER_TIMEOUT = 600
        settings.agent_path_resolved = Path("../test")
        settings.validate_config.return_value = []

        engine = SessionEngine(settings=settings)
        engine.SESSIONS_DIR = tmp_path / "sessions"
        engine.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        engine._LAST_SESSION_FILE = tmp_path / "last_session_id"
        # Isolate worker registry to tmp_path
        from src.core.worker_registry import WorkerRegistry
        engine.worker_registry = WorkerRegistry(tmp_path / "workers.json")
        engine.worker_registry.ensure_default(
            model=settings.WORKER_MODEL, profile=settings.WORKER_PROFILE,
        )
        return engine

    def test_save_and_load_session(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()

        path = engine.save_session("test_session")
        assert path.exists()

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["version"] == "3.0"
        assert "manager_history" in data
        assert "session_id" in data
        assert data["session_name"] == "test_session"

    def test_new_session_creates_unique_id(self, tmp_path):
        engine = self._make_engine(tmp_path)
        sid1 = engine._new_session("First")
        sid2 = engine._new_session("Second")
        assert sid1 != sid2
        assert engine.session_name == "Second"

    def test_list_sessions(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()

        engine._new_session("session_a")
        engine.save_session("session_a")
        sid_a = engine.session_id

        engine._new_session("session_b")
        engine.save_session("session_b")
        sid_b = engine.session_id

        sessions = engine.list_sessions()
        ids = [s["session_id"] for s in sessions]
        assert sid_a in ids
        assert sid_b in ids

    def test_load_nonexistent_session(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine.load_session("does_not_exist")
        assert result is False

    def test_load_restores_session_identity(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()
        engine._new_session("My Session")
        engine.save_session()
        saved_id = engine.session_id

        # Create a new engine and load the session
        engine2 = self._make_engine(tmp_path)
        engine2._init_manager()
        assert engine2.load_session(saved_id)
        assert engine2.session_id == saved_id
        assert engine2.session_name == "My Session"

    def test_last_session_id_persists(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()
        engine._new_session("Persist Test")
        engine.save_session()
        saved_id = engine.session_id

        # New engine should find the last session ID
        engine2 = self._make_engine(tmp_path)
        assert engine2._get_last_session_id() == saved_id

    def test_handle_slash_command_help(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/help")
        assert result is True

    def test_handle_slash_command_verbose(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/verbose")
        assert result is True
        assert engine.mode == SessionMode.VERBOSE
        assert engine.ui.verbose_worker is True

    def test_handle_slash_command_quiet(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._handle_slash_command("/verbose")
        result = engine._handle_slash_command("/quiet")
        assert result is True
        assert engine.mode == SessionMode.AUTO
        assert engine.ui.verbose_worker is False

    def test_handle_slash_command_unknown(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/nonexistent")
        assert result is False

    def test_handle_slash_command_clear(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()
        engine._new_session()
        engine.manager.messages.append(
            MagicMock(role=MagicMock(value="user"), content="test")
        )
        result = engine._handle_slash_command("/clear")
        assert result is True
        assert len(engine.manager.messages) == 1

    def test_handle_slash_command_new(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()
        engine._new_session("Old Session")
        old_id = engine.session_id
        result = engine._handle_slash_command("/new My New Session")
        assert result is True
        assert engine.session_id != old_id
        assert engine.session_name == "My New Session"

    # ================================================================
    # Model / Config / Confirm tests
    # ================================================================

    def test_handle_slash_command_model_show(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/model")
        assert result is True

    def test_handle_slash_command_model_change_manager(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/model manager gpt-4o")
        assert result is True
        assert engine.settings.ORCHESTRATOR_MODEL == "gpt-4o"

    def test_handle_slash_command_model_change_worker(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/model worker gpt-4o-mini")
        assert result is True
        assert engine.settings.WORKER_MODEL == "gpt-4o-mini"

    def test_handle_slash_command_model_change_default(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/model claude-3-opus")
        assert result is True
        assert engine.settings.ORCHESTRATOR_MODEL == "claude-3-opus"

    def test_handle_slash_command_config_show(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/config show")
        assert result is True

    def test_handle_slash_command_config_validate(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/config validate")
        assert result is True

    def test_handle_slash_command_config_no_arg(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/config")
        assert result is True

    def test_handle_slash_command_confirm_on_off(self, tmp_path):
        engine = self._make_engine(tmp_path)
        assert engine._confirm_mode is False

        result = engine._handle_slash_command("/confirm on")
        assert result is True
        assert engine._confirm_mode is True

        result = engine._handle_slash_command("/confirm off")
        assert result is True
        assert engine._confirm_mode is False

    def test_handle_slash_command_confirm_status(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/confirm")
        assert result is True

    def test_handle_slash_command_undo_no_checkpoints(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/undo")
        assert result is True

    def test_handle_slash_command_checkpoints(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/checkpoints")
        assert result is True

    def test_command_alias_save(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()
        result = engine._handle_slash_command("/s")
        assert result is True
        sessions = engine.list_sessions()
        assert len(sessions) > 0

    def test_command_alias_list(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/l")
        assert result is True

    def test_command_alias_help(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/h")
        assert result is True

    def test_session_metadata_in_save(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()
        path = engine.save_session("meta_test")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "summary" in data
        assert "message_count" in data
        assert "saved_at" in data
        assert "session_id" in data
        assert "created_at" in data

    def test_list_sessions_returns_metadata(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()
        engine.save_session("detail_test")
        sessions = engine.list_sessions()
        assert len(sessions) == 1
        s = sessions[0]
        assert "session_id" in s
        assert "name" in s
        assert "saved_at" in s
        assert "summary" in s
        assert "messages" in s

    def test_load_corrupted_session(self, tmp_path):
        engine = self._make_engine(tmp_path)
        # Write invalid JSON in session directory format
        corrupt_dir = engine.SESSIONS_DIR / "corrupt_session"
        corrupt_dir.mkdir(parents=True, exist_ok=True)
        (corrupt_dir / "session.json").write_text("{invalid json", encoding="utf-8")
        result = engine.load_session("corrupt_session")
        assert result is False

    def test_auto_save_uses_session_id(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()
        engine._new_session("Auto Test")
        engine._auto_save()
        session_dir = engine.SESSIONS_DIR / engine.session_id
        assert (session_dir / "session.json").exists()

    # ================================================================
    # /clearterminal test
    # ================================================================

    def test_handle_slash_command_clearterminal(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()
        engine._new_session("Keep Me")
        old_id = engine.session_id
        result = engine._handle_slash_command("/clearterminal")
        assert result is True
        # Session should NOT change
        assert engine.session_id == old_id

    def test_command_alias_clearterminal(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/ct")
        assert result is True

    # ================================================================
    # /new random name test
    # ================================================================

    def test_new_session_random_name(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._new_session()  # no name given
        assert engine.session_name != ""
        # Random name should be "Adjective Noun" format
        assert " " in engine.session_name

    # ================================================================
    # /load by name test
    # ================================================================

    def test_load_session_by_name(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()
        engine._new_session("My Cool Project")
        engine.save_session()
        saved_id = engine.session_id

        engine2 = self._make_engine(tmp_path)
        engine2._init_manager()
        assert engine2.load_session("My Cool Project")
        assert engine2.session_id == saved_id
        assert engine2.session_name == "My Cool Project"

    def test_load_session_by_name_case_insensitive(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()
        engine._new_session("Alpha Bravo")
        engine.save_session()
        saved_id = engine.session_id

        engine2 = self._make_engine(tmp_path)
        engine2._init_manager()
        assert engine2.load_session("alpha bravo")
        assert engine2.session_id == saved_id

    # ================================================================
    # /history full content test
    # ================================================================

    def test_handle_slash_command_history(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._init_manager()
        result = engine._handle_slash_command("/history")
        assert result is True

    # ================================================================
    # /worker tests
    # ================================================================

    def test_handle_slash_command_worker_list(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/worker list")
        assert result is True

    def test_handle_slash_command_worker_add_remove(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/worker add coder gemini-pro live")
        assert result is True
        wc = engine.worker_registry.get("coder")
        assert wc is not None
        assert wc.model == "gemini-pro"
        assert wc.profile == "live"

        result = engine._handle_slash_command("/worker remove coder")
        assert result is True
        assert engine.worker_registry.get("coder") is None

    def test_handle_slash_command_worker_set_active(self, tmp_path):
        engine = self._make_engine(tmp_path)
        engine._handle_slash_command("/worker add second claude-3 live")
        result = engine._handle_slash_command("/worker set second active")
        assert result is True
        wc = engine.worker_registry.get("second")
        assert wc is not None
        assert wc.active is True
        # Multi-worker: default should STILL be active
        default = engine.worker_registry.get("default")
        assert default is not None
        assert default.active is True
        # Both should be in active workers list
        active = engine.worker_registry.get_active_workers()
        active_names = [w.name for w in active]
        assert "default" in active_names
        assert "second" in active_names

    def test_handle_slash_command_worker_show(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/worker show default")
        assert result is True

    def test_command_alias_worker(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/w list")
        assert result is True

    # ================================================================
    # /config set test
    # ================================================================

    def test_handle_slash_command_config_set(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/config set")
        assert result is True  # Should show usage, not crash

    # ================================================================
    # Worker model/profile update tests
    # ================================================================

    def test_worker_registry_update_model(self, tmp_path):
        engine = self._make_engine(tmp_path)
        assert engine.worker_registry.update_model("default", "gpt-4o") is True
        wc = engine.worker_registry.get("default")
        assert wc.model == "gpt-4o"

    def test_worker_registry_update_profile(self, tmp_path):
        engine = self._make_engine(tmp_path)
        assert engine.worker_registry.update_profile("default", "swebench") is True
        wc = engine.worker_registry.get("default")
        assert wc.profile == "swebench"

    def test_worker_registry_update_model_nonexistent(self, tmp_path):
        engine = self._make_engine(tmp_path)
        assert engine.worker_registry.update_model("ghost", "gpt-4o") is False

    def test_worker_registry_update_profile_nonexistent(self, tmp_path):
        engine = self._make_engine(tmp_path)
        assert engine.worker_registry.update_profile("ghost", "swebench") is False

    def test_handle_slash_command_worker_model(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/worker model default gpt-4o")
        assert result is True
        wc = engine.worker_registry.get("default")
        assert wc.model == "gpt-4o"
        # Active worker should propagate to settings
        assert engine.settings.WORKER_MODEL == "gpt-4o"

    def test_handle_slash_command_worker_profile(self, tmp_path):
        engine = self._make_engine(tmp_path)
        result = engine._handle_slash_command("/worker profile default swebench")
        assert result is True
        wc = engine.worker_registry.get("default")
        assert wc.profile == "swebench"
        # Active worker should propagate to settings
        assert engine.settings.WORKER_PROFILE == "swebench"

    def test_model_worker_syncs_registry(self, tmp_path):
        """When /model worker <model> is used, active worker registry entry should update."""
        engine = self._make_engine(tmp_path)
        engine._handle_slash_command("/model worker new-model-x")
        assert engine.settings.WORKER_MODEL == "new-model-x"
        active = engine.worker_registry.get_active()
        assert active is not None
        assert active.model == "new-model-x"

    def test_worker_add_shows_list(self, tmp_path, capsys):
        """After /worker add, worker list table should be printed."""
        engine = self._make_engine(tmp_path)
        engine._handle_slash_command("/worker add coder2 gpt-4o live")
        captured = capsys.readouterr()
        assert "coder2" in captured.out

    def test_worker_remove_shows_list(self, tmp_path, capsys):
        """After /worker remove, worker list table should be printed."""
        engine = self._make_engine(tmp_path)
        engine._handle_slash_command("/worker add temp claude-3 live")
        engine._handle_slash_command("/worker remove temp")
        captured = capsys.readouterr()
        assert "temp" not in captured.out.split("removed")[-1]

    # ================================================================
    # Multi-worker tests
    # ================================================================

    def test_multiple_active_workers(self, tmp_path):
        """Multiple workers can be active simultaneously."""
        engine = self._make_engine(tmp_path)
        engine._handle_slash_command("/worker add coder gpt-4o swebench")
        engine._handle_slash_command("/worker set coder active")
        active = engine.worker_registry.get_active_workers()
        assert len(active) == 2
        names = [w.name for w in active]
        assert "default" in names
        assert "coder" in names

    def test_get_primary_returns_first_active(self, tmp_path):
        """Primary worker is the first active worker in registry order."""
        engine = self._make_engine(tmp_path)
        primary = engine.worker_registry.get_primary()
        assert primary is not None
        assert primary.name == "default"

    def test_set_primary_reorders_workers(self, tmp_path):
        """set_primary moves worker to front of registry."""
        engine = self._make_engine(tmp_path)
        engine._handle_slash_command("/worker add coder gpt-4o swebench")
        engine._handle_slash_command("/worker set coder active")
        engine._handle_slash_command("/worker set coder primary")
        primary = engine.worker_registry.get_primary()
        assert primary.name == "coder"
        # Settings should reflect primary worker
        assert engine.settings.WORKER_MODEL == "gpt-4o"

    def test_set_primary_inactive_worker_fails(self, tmp_path):
        """Cannot set an inactive worker as primary."""
        engine = self._make_engine(tmp_path)
        engine._handle_slash_command("/worker add coder gpt-4o swebench")
        # coder is inactive by default
        result = engine.worker_registry.set_primary("coder")
        assert result is False

    def test_worker_set_inactive_keeps_others_active(self, tmp_path):
        """Setting one worker inactive doesn't affect others."""
        engine = self._make_engine(tmp_path)
        engine._handle_slash_command("/worker add coder gpt-4o swebench")
        engine._handle_slash_command("/worker set coder active")
        engine._handle_slash_command("/worker set default inactive")
        active = engine.worker_registry.get_active_workers()
        assert len(active) == 1
        assert active[0].name == "coder"

    def test_remove_active_worker_no_active_left_activates_first(self, tmp_path):
        """If all active workers are removed, first remaining gets activated."""
        engine = self._make_engine(tmp_path)
        engine._handle_slash_command("/worker add backup gpt-4o live")
        engine._handle_slash_command("/worker set default inactive")
        # No active workers -> first should auto-activate
        active = engine.worker_registry.get_active_workers()
        # backup should be auto-activated since no active workers remain
        # Actually default is inactive and backup was added as inactive
        # So remove default which is inactive, backup should auto-activate
        engine._handle_slash_command("/worker remove default")
        active = engine.worker_registry.get_active_workers()
        assert len(active) == 1
        assert active[0].name == "backup"

    def test_manager_gets_worker_registry(self, tmp_path):
        """Manager should receive worker_registry on init."""
        engine = self._make_engine(tmp_path)
        engine._init_manager()
        assert engine.manager.worker_registry is engine.worker_registry

    def test_refresh_manager_tools_after_worker_change(self, tmp_path):
        """Manager system prompt should update after worker registry changes."""
        engine = self._make_engine(tmp_path)
        engine._init_manager()
        prompt_before = engine.manager.messages[0].content
        engine._handle_slash_command("/worker add coder gpt-4o swebench")
        engine._handle_slash_command("/worker set coder active")
        prompt_after = engine.manager.messages[0].content
        assert "coder" in prompt_after
        assert prompt_before != prompt_after

    # ================================================================
    # Per-Worker API Tests
    # ================================================================

    def test_worker_config_api_fields_default_none(self, tmp_path):
        """WorkerConfig api_base and api_key default to None."""
        from src.core.worker_registry import WorkerConfig
        wc = WorkerConfig(name="test", model="gpt-4o", profile="live")
        assert wc.api_base is None
        assert wc.api_key is None

    def test_worker_config_api_fields_set(self, tmp_path):
        """WorkerConfig stores api_base and api_key."""
        from src.core.worker_registry import WorkerConfig
        wc = WorkerConfig(
            name="test", model="gpt-4o", profile="live",
            api_base="https://api.z.ai", api_key="sk-zai123",
        )
        assert wc.api_base == "https://api.z.ai"
        assert wc.api_key == "sk-zai123"

    def test_worker_registry_update_api(self, tmp_path):
        """update_api sets per-worker API base and key."""
        engine = self._make_engine(tmp_path)
        result = engine.worker_registry.update_api(
            "default", "https://api.z.ai", "sk-key",
        )
        assert result is True
        wc = engine.worker_registry.get("default")
        assert wc.api_base == "https://api.z.ai"
        assert wc.api_key == "sk-key"

    def test_worker_registry_update_api_nonexistent(self, tmp_path):
        """update_api returns False for nonexistent worker."""
        engine = self._make_engine(tmp_path)
        result = engine.worker_registry.update_api("ghost", "https://x.ai")
        assert result is False

    def test_worker_api_persisted_to_json(self, tmp_path):
        """Per-worker API settings are persisted in workers.json."""
        engine = self._make_engine(tmp_path)
        engine.worker_registry.update_api(
            "default", "https://api.z.ai", "sk-key123",
        )
        from src.core.worker_registry import WorkerRegistry
        reg2 = WorkerRegistry(tmp_path / "workers.json")
        wc = reg2.get("default")
        assert wc.api_base == "https://api.z.ai"
        assert wc.api_key == "sk-key123"

    def test_worker_api_command(self, tmp_path):
        """/worker api sets per-worker API."""
        engine = self._make_engine(tmp_path)
        engine._handle_slash_command("/worker api default https://api.z.ai sk-key")
        wc = engine.worker_registry.get("default")
        assert wc.api_base == "https://api.z.ai"
        assert wc.api_key == "sk-key"

    def test_worker_api_command_without_key(self, tmp_path):
        """/worker api without key only sets api_base."""
        engine = self._make_engine(tmp_path)
        engine._handle_slash_command("/worker api default https://api.z.ai")
        wc = engine.worker_registry.get("default")
        assert wc.api_base == "https://api.z.ai"
        assert wc.api_key is None

    def test_worker_show_includes_api_and_tool(self, tmp_path, capsys):
        """/worker show displays Tool and API fields."""
        engine = self._make_engine(tmp_path)
        engine.worker_registry.update_api("default", "https://api.z.ai", "sk-key12345678")
        engine._handle_slash_command("/worker show default")
        captured = capsys.readouterr().out
        assert "delegate_to_default" in captured
        assert "https://api.z.ai" in captured
        assert "****...5678" in captured

    def test_worker_list_has_api_column(self, tmp_path, capsys):
        """Worker list table includes API column."""
        engine = self._make_engine(tmp_path)
        engine.worker_registry.update_api("default", "https://api.z.ai")
        engine._show_worker_list()
        captured = capsys.readouterr().out
        assert "API" in captured
        assert "https://api.z.ai" in captured

    def test_slash_command_tree_includes_api(self, tmp_path):
        """COMMAND_TREE worker 'set' includes api functionality via /worker set <name> api."""
        from src.commands.parser import CommandParser
        worker_actions = CommandParser.COMMAND_TREE.get("worker", [])
        assert "set" in worker_actions  # api is accessed via /worker set <name> api

    def test_worker_name_sanitized_on_add(self, tmp_path):
        """Worker names with invalid chars should be sanitized."""
        engine = self._make_engine(tmp_path)
        engine._handle_slash_command("/worker add z.ai test-model live")
        # Name should be sanitized: z.ai -> z-ai
        assert engine.worker_registry.get("z-ai") is not None
        assert engine.worker_registry.get("z.ai") is None

    def test_worker_name_sanitize_static(self, tmp_path):
        """WorkerRegistry.sanitize_name replaces invalid chars."""
        from src.core.worker_registry import WorkerRegistry
        assert WorkerRegistry.sanitize_name("z.ai") == "z-ai"
        assert WorkerRegistry.sanitize_name("my worker!") == "my-worker-"
        assert WorkerRegistry.sanitize_name("valid-name_123") == "valid-name_123"
        assert WorkerRegistry.sanitize_name("dots...here") == "dots---here"
