"""
Manager Agent - The intelligent orchestrator that communicates with users
and delegates tasks to the Worker agent.

Uses LiteLLM for LLM communication with tool/function calling support.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

import litellm
from litellm import completion

from .config import Settings, get_settings
from .worker import AgentWorker, TaskResult, TaskStatus

logger = logging.getLogger(__name__)

# Suppress litellm debug logs
litellm.set_verbose = False
litellm.suppress_debug_info = True


class MessageRole(Enum):
    """Message roles in the conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """A message in the conversation."""
    role: MessageRole
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    name: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to LiteLLM message format."""
        msg = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name:
            msg["name"] = self.name
        return msg


# Tool definition for the Worker delegation
WORKER_TOOL = {
    "type": "function",
    "function": {
        "name": "delegate_to_worker",
        "description": (
            "Delegate a coding/engineering task to the Worker Agent (Mini-SWE-GOCore). "
            "Use this when the user needs code written, files created/modified, "
            "terminal commands executed, or any software engineering task. "
            "The Worker is an autonomous coding agent that can execute shell commands "
            "and modify files. Provide a clear, detailed task description."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task_description": {
                    "type": "string",
                    "description": (
                        "A detailed description of the task for the Worker to execute. "
                        "Be specific about what needs to be done, including file paths, "
                        "expected behavior, and any constraints."
                    ),
                },
                "context": {
                    "type": "string",
                    "description": (
                        "Optional additional context from the conversation that might "
                        "help the Worker understand the task better."
                    ),
                },
            },
            "required": ["task_description"],
        },
    },
}

# System prompt for the Manager Agent
MANAGER_SYSTEM_PROMPT = """You are GOrchestrator, a Senior Software Architect and Project Manager AI.

## Your Role
- You are the intelligent interface between the user and a powerful coding agent called "Worker"
- You communicate with users to understand and clarify their requirements
- You decide when to delegate tasks to the Worker agent
- You review and explain the Worker's output to the user

## Your Capabilities
1. **Conversation**: Chat naturally with users, answer questions, clarify requirements
2. **Task Delegation**: Use the `delegate_to_worker` tool to have the Worker execute coding tasks
3. **Review & Explain**: Analyze Worker results and provide clear explanations to users

## When to Use the Worker
- Writing or modifying code
- Creating files or directories
- Running terminal commands
- Debugging or fixing issues
- Any software engineering task

## When NOT to Use the Worker
- Simple questions that don't require code changes
- Clarifying requirements or discussing approaches
- Explaining concepts or providing advice
- Greeting the user or casual conversation

## Guidelines
1. **Clarify First**: If a request is ambiguous, ask for clarification before delegating
2. **Be Specific**: When delegating, provide clear, detailed task descriptions
3. **Review Results**: Always analyze Worker output and explain what was done
4. **Be Helpful**: Suggest improvements or next steps when appropriate
5. **Stay Professional**: Be concise, clear, and focused on the user's goals

## Response Style
- Be conversational but professional
- Use markdown for formatting when helpful
- Keep responses focused and actionable
- Acknowledge what the user wants before taking action
"""


@dataclass
class ManagerResponse:
    """Response from the Manager Agent."""
    content: str
    tool_calls: list[dict] | None = None
    worker_results: list[TaskResult] = field(default_factory=list)
    thinking: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class ManagerAgent:
    """
    The Manager Agent - an LLM-powered orchestrator that communicates
    with users and delegates tasks to the Worker agent.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        on_worker_output: Callable[[str], None] | None = None,
        on_thinking: Callable[[str], None] | None = None,
    ):
        """
        Initialize the Manager Agent.

        Args:
            settings: Application settings.
            on_worker_output: Callback for Worker output streaming.
            on_thinking: Callback for Manager thinking/status updates.
        """
        self.settings = settings or get_settings()
        self.worker = AgentWorker(self.settings)
        self.messages: list[Message] = []
        self.on_worker_output = on_worker_output
        self.on_thinking = on_thinking

        # Initialize with system prompt
        self._add_system_message()

    def _add_system_message(self):
        """Add the system prompt to messages."""
        self.messages.append(Message(
            role=MessageRole.SYSTEM,
            content=MANAGER_SYSTEM_PROMPT,
        ))

    def _notify_thinking(self, text: str):
        """Notify about Manager thinking/status."""
        if self.on_thinking:
            self.on_thinking(text)

    def _call_llm(self, include_tools: bool = True) -> dict:
        """
        Call the LLM with current messages.

        Args:
            include_tools: Whether to include tool definitions.

        Returns:
            LLM response dictionary.
        """
        config = self.settings.get_orchestrator_config()

        kwargs = {
            "model": config["model"],
            "messages": [msg.to_dict() for msg in self.messages],
            "api_base": config["api_base"],
            "api_key": config["api_key"],
            "max_tokens": 4096,
        }

        if include_tools:
            kwargs["tools"] = [WORKER_TOOL]
            kwargs["tool_choice"] = "auto"

        try:
            response = completion(**kwargs)
            return response
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _execute_worker_task(self, task_description: str, context: str = "") -> TaskResult:
        """
        Execute a task using the Worker agent.

        Args:
            task_description: The task to execute.
            context: Optional additional context.

        Returns:
            TaskResult from the Worker.
        """
        # Build full task with context if provided
        full_task = task_description
        if context:
            full_task = f"Context: {context}\n\nTask: {task_description}"

        self._notify_thinking("Delegating to Worker Agent...")

        result = self.worker.run_task(
            task=full_task,
            model=self.settings.WORKER_MODEL,
            on_output=self.on_worker_output,
        )

        return result

    def _handle_tool_calls(self, tool_calls: list[dict]) -> list[TaskResult]:
        """
        Handle tool calls from the LLM response.

        Args:
            tool_calls: List of tool call objects.

        Returns:
            List of TaskResults from Worker executions.
        """
        results = []

        for tool_call in tool_calls:
            function = tool_call.get("function", {})
            name = function.get("name")
            arguments = function.get("arguments", "{}")
            call_id = tool_call.get("id", "unknown")

            if name == "delegate_to_worker":
                try:
                    args = json.loads(arguments)
                    task_description = args.get("task_description", "")
                    context = args.get("context", "")

                    result = self._execute_worker_task(task_description, context)
                    results.append(result)

                    # Add tool response to messages
                    tool_response = self._format_worker_result(result)
                    self.messages.append(Message(
                        role=MessageRole.TOOL,
                        content=tool_response,
                        tool_call_id=call_id,
                        name=name,
                    ))

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse tool arguments: {e}")
                    self.messages.append(Message(
                        role=MessageRole.TOOL,
                        content=f"Error: Failed to parse arguments: {e}",
                        tool_call_id=call_id,
                        name=name,
                    ))
                except Exception as e:
                    logger.error(f"Worker execution failed: {e}")
                    self.messages.append(Message(
                        role=MessageRole.TOOL,
                        content=f"Error: Worker execution failed: {e}",
                        tool_call_id=call_id,
                        name=name,
                    ))

        return results

    def _format_worker_result(self, result: TaskResult) -> str:
        """Format a TaskResult for the LLM to understand."""
        status = "SUCCESS" if result.is_success else "FAILED"

        # Get last N lines of output
        output_lines = result.output_lines[-50:] if result.output_lines else []
        output_text = "\n".join(output_lines)

        return f"""Worker Agent Result:
Status: {status}
Exit Code: {result.exit_code}
Steps Executed: {result.step_count}
Cost: ${result.total_cost:.4f}
Duration: {result.duration_seconds:.1f}s

Output (last 50 lines):
{output_text}

{"Error: " + result.error_message if result.error_message else ""}
"""

    def chat(self, user_message: str) -> ManagerResponse:
        """
        Process a user message and generate a response.

        This may involve multiple LLM calls if tool use is required.

        Args:
            user_message: The user's input message.

        Returns:
            ManagerResponse with content and any worker results.
        """
        # Add user message
        self.messages.append(Message(
            role=MessageRole.USER,
            content=user_message,
        ))

        self._notify_thinking("Manager is thinking...")

        worker_results = []
        max_iterations = 5  # Prevent infinite loops

        for iteration in range(max_iterations):
            # Call LLM
            response = self._call_llm()
            choice = response.choices[0]
            message = choice.message

            # Extract content and tool calls
            content = message.content or ""
            tool_calls = getattr(message, "tool_calls", None)

            # Add assistant message to history
            assistant_msg = Message(
                role=MessageRole.ASSISTANT,
                content=content,
                tool_calls=[tc.model_dump() for tc in tool_calls] if tool_calls else None,
            )
            self.messages.append(assistant_msg)

            # If no tool calls, we're done
            if not tool_calls:
                return ManagerResponse(
                    content=content,
                    worker_results=worker_results,
                )

            # Handle tool calls
            self._notify_thinking("Executing Worker tasks...")
            results = self._handle_tool_calls(
                [tc.model_dump() for tc in tool_calls]
            )
            worker_results.extend(results)

            # Continue loop to get final response after tool execution

        # If we hit max iterations, return what we have
        return ManagerResponse(
            content="I encountered an issue processing your request. Please try again.",
            worker_results=worker_results,
        )

    def get_history(self) -> list[dict]:
        """Get conversation history as list of dicts."""
        return [
            {
                "role": msg.role.value,
                "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content,
                "timestamp": msg.timestamp,
                "has_tool_calls": bool(msg.tool_calls),
            }
            for msg in self.messages
            if msg.role != MessageRole.SYSTEM
        ]

    def clear_history(self):
        """Clear conversation history (keep system prompt)."""
        self.messages = []
        self._add_system_message()

    def export_history(self) -> list[dict]:
        """Export full conversation history for persistence."""
        return [
            {
                "role": msg.role.value,
                "content": msg.content,
                "timestamp": msg.timestamp,
                "tool_calls": msg.tool_calls,
                "tool_call_id": msg.tool_call_id,
                "name": msg.name,
            }
            for msg in self.messages
        ]

    def import_history(self, history: list[dict]):
        """Import conversation history from persistence."""
        self.messages = []
        for entry in history:
            role = MessageRole(entry.get("role", "user"))
            # Skip old system prompts - we'll add the current one
            if role == MessageRole.SYSTEM:
                continue
            self.messages.append(Message(
                role=role,
                content=entry.get("content", ""),
                timestamp=entry.get("timestamp", datetime.now().isoformat()),
                tool_calls=entry.get("tool_calls"),
                tool_call_id=entry.get("tool_call_id"),
                name=entry.get("name"),
            ))

        # Always prepend the current system prompt
        self.messages.insert(0, Message(
            role=MessageRole.SYSTEM,
            content=MANAGER_SYSTEM_PROMPT,
        ))
