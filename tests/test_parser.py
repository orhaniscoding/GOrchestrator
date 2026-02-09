"""Tests for the log parser module."""

import pytest
from src.utils.parser import (
    AgentLogEntry,
    RawLogEntry,
    parse_log_line,
    format_log_entry,
    safe_string,
)


class TestParseLogLine:
    """Tests for parse_log_line function."""

    def test_valid_step_log(self):
        line = '{"type": "step", "step": 1, "message": "Starting..."}'
        entry = parse_log_line(line)
        assert isinstance(entry, AgentLogEntry)
        assert entry.is_step
        assert entry.step_number == 1
        assert entry.message == "Starting..."

    def test_valid_cost_log(self):
        line = '{"type": "cost", "total": 0.0025}'
        entry = parse_log_line(line)
        assert isinstance(entry, AgentLogEntry)
        assert entry.is_cost
        assert entry.cost == 0.0025

    def test_valid_result_log(self):
        line = '{"type": "result", "message": "Task completed"}'
        entry = parse_log_line(line)
        assert isinstance(entry, AgentLogEntry)
        assert entry.is_result
        assert entry.message == "Task completed"

    def test_valid_error_log(self):
        line = '{"type": "error", "message": "Something went wrong"}'
        entry = parse_log_line(line)
        assert isinstance(entry, AgentLogEntry)
        assert entry.is_error
        assert entry.message == "Something went wrong"

    def test_plain_text_returns_raw(self):
        line = "Some plain text output"
        entry = parse_log_line(line)
        assert isinstance(entry, RawLogEntry)
        assert entry.log_type == "raw"
        assert entry.raw == line

    def test_empty_string(self):
        entry = parse_log_line("")
        assert isinstance(entry, RawLogEntry)

    def test_whitespace_only(self):
        entry = parse_log_line("   ")
        assert isinstance(entry, RawLogEntry)

    def test_json_without_type_field(self):
        line = '{"key": "value"}'
        entry = parse_log_line(line)
        assert isinstance(entry, RawLogEntry)

    def test_invalid_json(self):
        line = '{invalid json}'
        entry = parse_log_line(line)
        assert isinstance(entry, RawLogEntry)

    def test_none_input(self):
        entry = parse_log_line(None)
        assert isinstance(entry, RawLogEntry)

    def test_non_string_input(self):
        entry = parse_log_line(12345)
        assert isinstance(entry, RawLogEntry)

    def test_step_without_number(self):
        line = '{"type": "step", "message": "Processing..."}'
        entry = parse_log_line(line)
        assert isinstance(entry, AgentLogEntry)
        assert entry.is_step
        assert entry.step_number is None

    def test_cost_with_cost_key(self):
        line = '{"type": "cost", "cost": 0.005}'
        entry = parse_log_line(line)
        assert entry.cost == 0.005


class TestSafeString:
    """Tests for safe_string function."""

    def test_normal_string(self):
        assert safe_string("hello") == "hello"

    def test_truncation(self):
        long_str = "a" * 300
        result = safe_string(long_str, max_length=100)
        assert len(result) == 103  # 100 + "..."
        assert result.endswith("...")

    def test_unicode(self):
        result = safe_string("Hello \u00e7al\u0131\u015f\u0131yor")
        assert "\u00e7al\u0131\u015f\u0131yor" in result


class TestFormatLogEntry:
    """Tests for format_log_entry function."""

    def test_format_raw(self):
        entry = RawLogEntry(raw="plain text")
        assert format_log_entry(entry) == "plain text"

    def test_format_step(self):
        entry = AgentLogEntry(
            log_type="step",
            data={"type": "step", "step": 3, "message": "Writing file"},
            raw="",
        )
        assert "[Step 3]" in format_log_entry(entry)
        assert "Writing file" in format_log_entry(entry)

    def test_format_cost(self):
        entry = AgentLogEntry(
            log_type="cost",
            data={"type": "cost", "total": 0.0042},
            raw="",
        )
        result = format_log_entry(entry)
        assert "$0.0042" in result

    def test_format_result(self):
        entry = AgentLogEntry(
            log_type="result",
            data={"type": "result", "message": "Done"},
            raw="",
        )
        assert "[Result]" in format_log_entry(entry)

    def test_format_error(self):
        entry = AgentLogEntry(
            log_type="error",
            data={"type": "error", "message": "Fail"},
            raw="",
        )
        assert "[Error]" in format_log_entry(entry)
