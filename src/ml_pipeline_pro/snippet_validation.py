"""Static, closed grammar for one reviewed API request; never execute Python."""

import ast
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from ml_pipeline_pro.conversation_schemas import serialized
from ml_pipeline_pro.snippet_schemas import PROFILE_INPUTS, SNIPPET_BYTES, SnippetRequest


@dataclass(frozen=True)
class _Environment:
    name: str


class _Rejected(Exception):
    pass


def _require(condition: bool):
    if not condition:
        raise _Rejected


def request_shape(request: SnippetRequest) -> tuple[str, str, Any, Any]:
    """Expected HTTP shape from validated inputs, including documented defaults."""
    request = request.normalized()
    values = request.inputs
    if request.profile == "compare_experiments":
        query = [("experiment_id", item) for item in values["experiment_ids"]]
        return "get", "/api/v1/experiments/compare", [*query, ("metric", values["metric"])], None
    if request.profile == "list_experiments":
        return "get", "/api/v1/experiments", values, None
    path = (
        "/api/v1/experiments" if request.profile == "create_experiment" else "/api/v1/tuning-jobs"
    )
    return "post", path, None, values


class _Grammar:
    def __init__(self, request: SnippetRequest):
        self.request = request.normalized()
        self.expected = request_shape(self.request)
        self.variables: dict[str, Any] = {}
        self.assigned: set[str] = set()
        self.used: set[str] = set()
        self.imports: set[str] = set()
        self.client: str | None = None
        self.response: str | None = None
        self.checked = False
        self.inspected = False

    def value(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            _require(type(node.value) in (str, int, float, bool, type(None)))
            return node.value
        if isinstance(node, ast.Name):
            _require(node.id in self.variables)
            self.used.add(node.id)
            return self.variables[node.id]
        if isinstance(node, (ast.List, ast.Tuple)):
            values = [self.value(item) for item in node.elts]
            return tuple(values) if isinstance(node, ast.Tuple) else values
        if isinstance(node, ast.Dict):
            _require(all(key is not None for key in node.keys))
            keys = [self.value(key) for key in node.keys]
            _require(all(type(key) is str for key in keys) and len(set(keys)) == len(keys))
            return {key: self.value(value) for key, value in zip(keys, node.values, strict=True)}
        if isinstance(node, ast.Subscript) and ast.unparse(node.value) == "os.environ":
            _require("os" in self.imports)
            key = self.value(node.slice)
            _require(
                key in ("MLPP_API_ORIGIN", "MLPP_PROJECT_ID", "MLPP_API_KEY", "MLPP_SUBMISSION_KEY")
            )
            return _Environment(key)
        raise _Rejected

    def keywords(self, node: ast.Call) -> dict[str, Any]:
        keys = [item.arg for item in node.keywords]
        _require(None not in keys and len(set(keys)) == len(keys))
        return {item.arg: self.value(item.value) for item in node.keywords}

    def assignment(self, node: ast.Assign, *, inside: bool):
        _require(len(node.targets) == 1 and isinstance(node.targets[0], ast.Name))
        name = node.targets[0].id
        _require(name not in self.assigned and name not in self.imports and name != self.client)
        self.assigned.add(name)
        if inside and isinstance(node.value, ast.Call):
            call = node.value
            _require(isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name))
            owner, method = call.func.value.id, call.func.attr
            if owner == self.client:
                _require(self.response is None)
                expected_method, path, query, body = self.expected
                _require(method == expected_method and len(call.args) == 1)
                _require(self.value(call.args[0]) == path)
                keywords = self.keywords(call)
                expected = {"params": query} if query is not None else {"json": body}
                _require(serialized(keywords) == serialized(expected))
                if body is not None:
                    # Check both API contract and exact supplied budgets/identifiers.
                    validated = PROFILE_INPUTS[self.request.profile].model_validate(
                        keywords["json"]
                    )
                    _require(serialized(validated.model_dump(mode="json")) == serialized(body))
                self.response = name
                return
            _require(owner == self.response and method == "json" and self.checked)
            _require(not call.args and not call.keywords and not self.inspected)
            self.inspected = True
            # Result values cannot flow into further calls or destinations.
            return
        self.variables[name] = self.value(node.value)

    def client_block(self, node: ast.With):
        _require(self.client is None and len(node.items) == 1)
        item = node.items[0]
        _require(isinstance(item.optional_vars, ast.Name))
        self.client = item.optional_vars.id
        _require(self.client not in self.variables and self.client not in self.imports)
        call = item.context_expr
        _require(isinstance(call, ast.Call) and ast.unparse(call.func) == "httpx.Client")
        _require("httpx" in self.imports and not call.args)
        keywords = self.keywords(call)
        _require(
            set(keywords) == {"base_url", "headers", "timeout", "follow_redirects", "trust_env"}
        )
        _require(keywords["base_url"] == _Environment("MLPP_API_ORIGIN"))
        headers = {
            "X-Project-ID": _Environment("MLPP_PROJECT_ID"),
            "X-API-Key": _Environment("MLPP_API_KEY"),
        }
        if self.expected[0] == "post":
            headers["Idempotency-Key"] = _Environment("MLPP_SUBMISSION_KEY")
        _require(keywords["headers"] == headers)
        timeout = keywords["timeout"]
        _require(type(timeout) in (int, float) and 0 < timeout <= 30)
        _require(keywords["follow_redirects"] is False and keywords["trust_env"] is False)
        for statement in node.body:
            if isinstance(statement, ast.Assign):
                self.assignment(statement, inside=True)
            elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
                call = statement.value
                _require(self.response is not None and not self.checked)
                _require(ast.unparse(call.func) == f"{self.response}.raise_for_status")
                _require(not call.args and not call.keywords)
                self.checked = True
            else:
                raise _Rejected
        _require(self.response is not None and self.checked and self.inspected)

    def check(self, tree: ast.Module):
        for statement in tree.body:
            if isinstance(statement, ast.Import):
                _require(self.client is None)
                for alias in statement.names:
                    _require(alias.name in ("os", "json", "httpx") and alias.asname is None)
                    _require(alias.name not in self.imports and alias.name not in self.variables)
                    self.imports.add(alias.name)
            elif isinstance(statement, ast.Assign) and self.client is None:
                self.assignment(statement, inside=False)
            elif isinstance(statement, ast.With):
                self.client_block(statement)
            else:
                raise _Rejected
        _require(self.client is not None)
        _require(set(self.variables) <= self.used)


def validate_snippet(code: str, request: SnippetRequest) -> list[str]:
    """Fixed issues reveal no model text, secrets, or Python exception details."""
    if not code.strip() or len(code.encode("utf-8")) > SNIPPET_BYTES:
        return ["snippet_size_invalid"]
    try:
        tree = ast.parse(code)
        _Grammar(request).check(tree)
    except (SyntaxError, ValueError, TypeError, RecursionError, ValidationError, _Rejected):
        return ["snippet_grammar_or_api_invalid"]
    return []
