"""
Week 2 — Tool definitions.

Each tool has two parts:
1. A JSON schema (tells the model what the tool does and what arguments it takes)
2. A Python function that actually executes it

The model never runs code itself — it just outputs "I want to call calculator
with expression='2+2'", and OUR code executes that and feeds the result back.
"""

import ast
import operator

from ddgs import DDGS


# ---------- Tool 1: Calculator ----------
# Using ast.literal_eval-style safe evaluation instead of eval() — never eval()
# raw model output directly, even for "just math". Models can be tricked into
# producing malicious expressions.

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        op_func = _ALLOWED_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Operator not allowed: {type(node.op)}")
        return op_func(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op_func = _ALLOWED_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Operator not allowed: {type(node.op)}")
        return op_func(_safe_eval(node.operand))
    raise ValueError(f"Unsupported expression: {node}")


def calculator(expression: str) -> str:
    """Safely evaluate a basic arithmetic expression like '12 * (3 + 4)'."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {e}"


# ---------- Tool 2: Read a local file ----------
# Restricted to a specific folder so the model can't be tricked into reading
# arbitrary files on your system (e.g. via prompt injection from a search result).

import os

READABLE_DIR = os.path.abspath("./agent_files")
os.makedirs(READABLE_DIR, exist_ok=True)


def read_file(filename: str) -> str:
    """Read a text file's contents. Only files inside ./agent_files are allowed."""
    target = os.path.abspath(os.path.join(READABLE_DIR, filename))
    if not target.startswith(READABLE_DIR):
        return "Error: access outside agent_files directory is not allowed."
    if not os.path.isfile(target):
        return f"Error: file '{filename}' not found in agent_files/."
    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return content[:3000]  # cap to keep context manageable
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(filename: str, content: str) -> str:
    """Write text content to a file. Only files inside ./agent_files are allowed."""
    target = os.path.abspath(os.path.join(READABLE_DIR, filename))
    if not target.startswith(READABLE_DIR):
        return "Error: access outside agent_files directory is not allowed."
    try:
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {filename}"
    except Exception as e:
        return f"Error writing file: {e}"


# ---------- Tool 3: Web search ----------

def web_search(query: str, max_results: int = 3) -> str:
    """Search the web and return a few short result snippets."""
    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return "No results found."
        formatted = []
        for r in results:
            formatted.append(f"- {r['title']}: {r['body'][:400]} (source: {r['href']})")
        return "\n".join(formatted)
    except Exception as e:
        return f"Error during search: {e}"


# ---------- Tool registry ----------
# This is what gets sent to the model so it knows what tools exist and how to call them.
# Format follows Ollama's tool-calling schema (same shape as OpenAI's function-calling).

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a basic arithmetic expression (numbers, + - * / ^, parentheses).",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The math expression to evaluate, e.g. '12 * (3 + 4)'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a text file located in the agent_files directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the file to read, e.g. 'notes.txt'",
                    }
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write text content to a file in the agent_files directory. Use this to save research output, summaries, or reports.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the file to write, e.g. 'summary.md'",
                    },
                    "content": {
                        "type": "string",
                        "description": "The text content to write to the file",
                    },
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information and return short result snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    }
                },
                "required": ["query"],
            },
        },
    },
]

# Maps tool name -> actual Python function, used to execute whatever the model requests
TOOL_FUNCTIONS = {
    "calculator": calculator,
    "read_file": read_file,
    "write_file": write_file,
    "web_search": web_search,
}