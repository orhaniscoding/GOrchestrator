"""
Command Parser Tests
"""

from src.commands.parser import CommandParser, Command
from unittest.mock import MagicMock


class TestCommandParser:
    """Command parser tests."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.parser = CommandParser()
    
    def test_parse_basic_command(self):
        """Test basic command parsing."""
        cmd = self.parser.parse("/manager show")
        assert cmd is not None
        assert cmd.source == "manager"
        assert cmd.action == "show"
        assert cmd.args == []
        assert cmd.options == {}
    
    def test_parse_command_with_args(self):
        """Test command with arguments."""
        cmd = self.parser.parse("/worker add coder claude-opus-4")
        assert cmd is not None
        assert cmd.source == "worker"
        assert cmd.action == "add"
        assert cmd.args == ["coder", "claude-opus-4"]
        assert cmd.options == {}

    def test_parse_command_with_global_option(self):
        """Test command with --global option."""
        cmd = self.parser.parse("/manager set model gpt-4o --global")
        assert cmd is not None
        assert cmd.source == "manager"
        assert cmd.action == "set model"
        assert cmd.args == ["gpt-4o"]
        assert cmd.options == {"--global": ""}
    
    def test_parse_invalid_command(self):
        """Test invalid command parsing."""
        cmd = self.parser.parse("not a command")
        assert cmd is None
    
    def test_parse_empty_command(self):
        """Test empty command parsing."""
        cmd = self.parser.parse("")
        assert cmd is None
    
    def test_parse_without_slash(self):
        """Test command without slash."""
        cmd = self.parser.parse("manager show")
        assert cmd is None
    
    def test_validate_valid_command(self):
        """Test valid command validation."""
        cmd = Command(
            source="manager",
            action="show",
            args=[],
            options={}
        )
        assert self.parser.validate(cmd) == True
    
    def test_validate_invalid_source(self):
        """Test invalid source validation."""
        cmd = Command(
            source="invalid",
            action="show",
            args=[],
            options={}
        )
        assert self.parser.validate(cmd) == False
    
    def test_validate_invalid_action(self):
        """Test invalid action validation."""
        cmd = Command(
            source="manager",
            action="invalid",
            args=[],
            options={}
        )
        assert self.parser.validate(cmd) == False
    
    def test_get_suggestions_root(self):
        """Test root command suggestions."""
        suggestions = self.parser.get_suggestions("/")
        assert len(suggestions) > 0
        assert "/manager" in suggestions
        assert "/worker" in suggestions
        assert "/session" in suggestions
        assert "/system" in suggestions
        assert "/mode" in suggestions
    
    def test_get_suggestions_partial_source(self):
        """Test partial source suggestions."""
        suggestions = self.parser.get_suggestions("/ma")
        assert len(suggestions) > 0
        assert "/manager" in suggestions
    
    def test_get_suggestions_partial_action(self):
        """Test partial action suggestions."""
        suggestions = self.parser.get_suggestions("/manager set")
        assert len(suggestions) > 0
        assert any("set model" in s for s in suggestions)
        assert any("set api" in s for s in suggestions)
