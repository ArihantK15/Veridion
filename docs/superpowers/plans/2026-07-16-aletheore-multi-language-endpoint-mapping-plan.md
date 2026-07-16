# Aletheore Multi-Language API Endpoint Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Aletheore's static API endpoint mapping to Go (stdlib `net/http`/`gorilla/mux`,
and Gin), Rust (Axum), Java (Spring Boot), Ruby (Rails), PHP (Laravel), and C# (both
attribute-routed Controllers and Minimal API) — 8 extractors across 6 languages.

**Architecture:** Each framework gets its own extraction function in `aletheore/endpoints.py`,
following the exact pattern the four existing extractors (Flask/FastAPI, Django, Express)
already use: walk a tree-sitter parse tree, pattern-match call/decorator/annotation shapes,
return a list of endpoint dicts. `map_api_endpoints` grows new per-extension branches to call
the new extractors. No other file changes — `evidence.py`, `query.py`, `mcp_server.py`,
`history.py` already operate on `repository.api_endpoints` generically and need nothing new.

**Tech Stack:** tree-sitter grammars already installed (`tree-sitter-go`, `tree-sitter-rust`,
`tree-sitter-java`, `tree-sitter-ruby`, `tree-sitter-php`, `tree-sitter-c-sharp` — all imported
into `aletheore/scanner/graph.py` already from the original 7-language module-graph work).

## Global Constraints

- No new dependencies — every grammar needed is already a project dependency.
- Every endpoint entry gains one new field vs. the first pass: `"note": str | None`, defaulting
  to `None`. This applies to **all** frameworks, old and new. Task 1 makes this change and
  updates every existing Phase 1 test that asserts an exact entry dict.
- Entry shape after this plan:
  `{"method": str | None, "path": str, "framework": str, "file": str, "line": int, "handler":
  str, "unresolved": bool, "note": str | None}`.
- Every tree-sitter node type and field name used below was verified against a real parse of
  representative code before this plan was written (not guessed) — see the design spec's
  per-language table for the source reasoning. Where a plan step's code doesn't match what a
  real file produces, trust a fresh live check over this document, the same discipline used for
  every previous language addition in this project.
- Framework tag strings used below (`"go_net_http"`, `"gorilla_mux"`, `"gin"`, `"axum"`,
  `"spring_boot"`, `"rails"`, `"laravel"`, `"aspnet_attribute"`, `"aspnet_minimal"`) are final —
  not placeholders.

---

### Task 1: Add the `note` field across every existing extractor and test

**Files:**
- Modify: `prototype/aletheore/endpoints.py`
- Modify: `prototype/tests/test_endpoints.py`

**Interfaces:**
- Every dict literal built by `_extract_flask_fastapi_routes`, `_django_call_to_entry`, and
  `_extract_express_routes` gains `"note": None`.

- [ ] **Step 1: Update the failing assertions first**

In `prototype/tests/test_endpoints.py`, update the five tests that assert an exact entry dict
(the rest use field-by-field assertions and are unaffected):

```python
# test_extract_fastapi_verb_decorator_labeled_ambiguous
    assert entries == [
        {
            "method": "GET",
            "path": "/items/{item_id}",
            "framework": "flask_or_fastapi",
            "file": "app/api.py",
            "line": 1,
            "handler": "read_item",
            "unresolved": False,
            "note": None,
        }
    ]

# test_extract_django_path_call
    assert entries == [
        {
            "method": "ANY",
            "path": "users/<int:id>/",
            "framework": "django",
            "file": "app/urls.py",
            "line": 2,
            "handler": "views.get_user",
            "unresolved": False,
            "note": None,
        }
    ]

# test_extract_django_include_is_recorded_as_unresolved
    assert entries == [
        {
            "method": None,
            "path": "myapp.urls",
            "framework": "django",
            "file": "project/urls.py",
            "line": 1,
            "handler": "include(...)",
            "unresolved": True,
            "note": None,
        }
    ]

# test_extract_express_get_route_with_named_handler
    assert entries == [
        {
            "method": "GET",
            "path": "/users",
            "framework": "express",
            "file": "server.js",
            "line": 1,
            "handler": "listUsers",
            "unresolved": False,
            "note": None,
        }
    ]

# test_extract_express_mounted_router_is_recorded_as_unresolved
    assert entries == [
        {
            "method": None,
            "path": "/api",
            "framework": "express",
            "file": "server.js",
            "line": 1,
            "handler": "app.use(...)",
            "unresolved": True,
            "note": None,
        }
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -v`
Expected: those 5 tests FAIL (missing `"note"` key in the actual dict); the rest still pass.

- [ ] **Step 3: Add `"note": None` to every entry-construction site in `endpoints.py`**

Add `"note": None,` as the last key to each of the 2 entry-dict templates in
`_extract_flask_fastapi_routes` (the `route` branch's loop — one dict literal, appended once per
method — and the verb-decorator branch), the 2 entry dicts in `_django_call_to_entry` (`include`
and the real-route return), and the 2 entry dicts in `_extract_express_routes` (verb-route and
`use`) — 6 entry-dict sites total across the three existing extractor functions.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -v`
Expected: all pass (22 tests).

- [ ] **Step 5: Commit**

```bash
git add prototype/aletheore/endpoints.py prototype/tests/test_endpoints.py
git commit -m "feat: add note field to endpoint entries (prep for multi-language mapping)"
```

---

### Task 2: Go — stdlib `net/http`/`gorilla/mux`

**Files:**
- Modify: `prototype/aletheore/endpoints.py`
- Test: `prototype/tests/test_endpoints.py`

**Interfaces:**
- Produces: `_extract_go_net_http_routes(root: Node, source: bytes, rel_path: str) -> list[dict]`.

Verified AST: `http.HandleFunc("/path", handler)` is a `call_expression` whose `function` field
is a `selector_expression` (`operand` field = `identifier "http"`, `field` field =
`field_identifier "HandleFunc"`); `arguments` field is an `argument_list` whose named children
are `interpreted_string_literal` (path) then `identifier` (handler). A chained
`.Methods("GET", "POST")` on a `.HandleFunc(...)` call produces an **outer** `call_expression`
whose `function` is a `selector_expression` with `field` `"Methods"` and `operand` equal to the
**inner** `call_expression` (the `HandleFunc` call) — verified via `node.parent` that the inner
call's parent is that `selector_expression` and its parent is the outer `call_expression`, which
is how the walk avoids double-counting the inner call once its methods have been narrowed by the
outer wrapper. `.PathPrefix("/api").Subrouter()` is the unresolved sub-router case — the
`PathPrefix` call itself carries the path and is matched directly (its own `field` is
`"PathPrefix"`), the wrapping `.Subrouter()` call is simply not matched by anything and is
ignored. Go 1.22+'s combined `"GET /users/{id}"` pattern syntax embeds the method in the string.

- [ ] **Step 1: Write the failing tests**

```python
# append to prototype/tests/test_endpoints.py
from aletheore.scanner.graph import GO_LANGUAGE
from aletheore.endpoints import _extract_go_net_http_routes


def parse_go(source: str):
    parser = Parser()
    parser.language = GO_LANGUAGE
    tree = parser.parse(source.encode())
    return tree.root_node, source.encode()


def test_extract_go_stdlib_handlefunc():
    root, source = parse_go(
        'package main\nfunc main() {\n\thttp.HandleFunc("/health", healthHandler)\n}\n'
    )

    entries = _extract_go_net_http_routes(root, source, "main.go")

    assert entries == [
        {
            "method": "ANY",
            "path": "/health",
            "framework": "go_net_http",
            "file": "main.go",
            "line": 3,
            "handler": "healthHandler",
            "unresolved": False,
            "note": None,
        }
    ]


def test_extract_go_stdlib_handlefunc_go122_combined_pattern():
    root, source = parse_go(
        'package main\nfunc main() {\n\thttp.HandleFunc("GET /users/{id}", getUser)\n}\n'
    )

    entries = _extract_go_net_http_routes(root, source, "main.go")

    assert entries[0]["method"] == "GET"
    assert entries[0]["path"] == "/users/{id}"


def test_extract_gorilla_mux_handlefunc_with_chained_methods():
    root, source = parse_go(
        'package main\nfunc main() {\n\tr.HandleFunc("/items", updateItem).Methods("GET", "POST")\n}\n'
    )

    entries = _extract_go_net_http_routes(root, source, "main.go")

    assert len(entries) == 2
    methods = {e["method"] for e in entries}
    assert methods == {"GET", "POST"}
    for e in entries:
        assert e["framework"] == "gorilla_mux"
        assert e["path"] == "/items"
        assert e["handler"] == "updateItem"


def test_extract_gorilla_mux_subrouter_is_unresolved():
    root, source = parse_go(
        'package main\nfunc main() {\n\tapi := r.PathPrefix("/api").Subrouter()\n\t_ = api\n}\n'
    )

    entries = _extract_go_net_http_routes(root, source, "main.go")

    assert entries == [
        {
            "method": None,
            "path": "/api",
            "framework": "gorilla_mux",
            "file": "main.go",
            "line": 3,
            "handler": "Subrouter()",
            "unresolved": True,
            "note": None,
        }
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k go_stdlib -k gorilla -v`
Expected: FAIL with `ImportError: cannot import name '_extract_go_net_http_routes'`

- [ ] **Step 3: Write the implementation**

```python
# append to prototype/aletheore/endpoints.py

_GO_HANDLE_FIELDS = {"HandleFunc", "Handle"}
_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}


def _go_string_literal_text(node: Node, source: bytes) -> str:
    content = next(
        (c for c in node.children if c.type == "interpreted_string_literal_content"), None
    )
    if content is None:
        return ""
    return source[content.start_byte : content.end_byte].decode()


def _split_go_pattern(raw_path: str) -> tuple[str, str]:
    parts = raw_path.split(" ", 1)
    if len(parts) == 2 and parts[0] in _HTTP_METHODS:
        return parts[0], parts[1]
    return "ANY", raw_path


def _go_is_wrapped_by_methods_chain(call_node: Node, source: bytes) -> bool:
    parent = call_node.parent
    if parent is None or parent.type != "selector_expression":
        return False
    grandparent = parent.parent
    if grandparent is None or grandparent.type != "call_expression":
        return False
    outer_field = parent.child_by_field_name("field")
    return (
        outer_field is not None
        and source[outer_field.start_byte : outer_field.end_byte].decode() == "Methods"
    )


def _go_handler_name(args_named: list, source: bytes) -> str:
    if len(args_named) > 1 and args_named[1].type == "identifier":
        return source[args_named[1].start_byte : args_named[1].end_byte].decode()
    return "unknown"


def _extract_go_net_http_routes(root: Node, source: bytes, rel_path: str) -> list[dict]:
    entries: list[dict] = []

    def walk(n: Node) -> None:
        if n.type == "call_expression":
            func = n.child_by_field_name("function")
            if func is not None and func.type == "selector_expression":
                field = func.child_by_field_name("field")
                operand = func.child_by_field_name("operand")
                if field is not None and operand is not None:
                    field_name = source[field.start_byte : field.end_byte].decode()

                    if field_name == "Methods" and operand.type == "call_expression":
                        inner = operand
                        inner_func = inner.child_by_field_name("function")
                        if inner_func is not None and inner_func.type == "selector_expression":
                            inner_field = inner_func.child_by_field_name("field")
                            inner_operand = inner_func.child_by_field_name("operand")
                            inner_field_name = (
                                source[inner_field.start_byte : inner_field.end_byte].decode()
                                if inner_field is not None
                                else ""
                            )
                            if inner_field_name in _GO_HANDLE_FIELDS:
                                inner_args = inner.child_by_field_name("arguments")
                                outer_args = n.child_by_field_name("arguments")
                                if inner_args is not None and outer_args is not None:
                                    inner_named = inner_args.named_children
                                    if (
                                        inner_named
                                        and inner_named[0].type == "interpreted_string_literal"
                                    ):
                                        raw_path = _go_string_literal_text(inner_named[0], source)
                                        _, path = _split_go_pattern(raw_path)
                                        handler = _go_handler_name(inner_named, source)
                                        operand_text = source[
                                            inner_operand.start_byte : inner_operand.end_byte
                                        ].decode()
                                        framework = (
                                            "go_net_http"
                                            if operand_text == "http"
                                            else "gorilla_mux"
                                        )
                                        methods = [
                                            _go_string_literal_text(a, source).upper()
                                            for a in outer_args.named_children
                                            if a.type == "interpreted_string_literal"
                                        ]
                                        line = inner.start_point[0] + 1
                                        for method in methods:
                                            entries.append(
                                                {
                                                    "method": method,
                                                    "path": path,
                                                    "framework": framework,
                                                    "file": rel_path,
                                                    "line": line,
                                                    "handler": handler,
                                                    "unresolved": False,
                                                    "note": None,
                                                }
                                            )

                    elif field_name == "PathPrefix":
                        args = n.child_by_field_name("arguments")
                        if args is not None:
                            named = args.named_children
                            if named and named[0].type == "interpreted_string_literal":
                                path = _go_string_literal_text(named[0], source)
                                entries.append(
                                    {
                                        "method": None,
                                        "path": path,
                                        "framework": "gorilla_mux",
                                        "file": rel_path,
                                        "line": n.start_point[0] + 1,
                                        "handler": "Subrouter()",
                                        "unresolved": True,
                                        "note": None,
                                    }
                                )

                    elif field_name in _GO_HANDLE_FIELDS:
                        if not _go_is_wrapped_by_methods_chain(n, source):
                            args = n.child_by_field_name("arguments")
                            if args is not None:
                                named = args.named_children
                                if named and named[0].type == "interpreted_string_literal":
                                    raw_path = _go_string_literal_text(named[0], source)
                                    method, path = _split_go_pattern(raw_path)
                                    handler = _go_handler_name(named, source)
                                    operand_text = source[
                                        operand.start_byte : operand.end_byte
                                    ].decode()
                                    framework = (
                                        "go_net_http" if operand_text == "http" else "gorilla_mux"
                                    )
                                    entries.append(
                                        {
                                            "method": method,
                                            "path": path,
                                            "framework": framework,
                                            "file": rel_path,
                                            "line": n.start_point[0] + 1,
                                            "handler": handler,
                                            "unresolved": False,
                                            "note": None,
                                        }
                                    )
        for child in n.children:
            walk(child)

    walk(root)
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k "go_stdlib or gorilla" -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add prototype/aletheore/endpoints.py prototype/tests/test_endpoints.py
git commit -m "feat: extract Go stdlib net/http and gorilla/mux routes"
```

---

### Task 3: Go — Gin

**Files:**
- Modify: `prototype/aletheore/endpoints.py`
- Test: `prototype/tests/test_endpoints.py`

**Interfaces:**
- Produces: `_extract_gin_routes(root: Node, source: bytes, rel_path: str) -> list[dict]`.

Gin's `router.GET/POST/PUT/DELETE/PATCH("/path", handler)` and `router.Any("/path", handler)`
share the exact same `call_expression`/`selector_expression` shape already verified for Go — no
new AST exploration needed, just a different field-name vocabulary and no chaining logic.

- [ ] **Step 1: Write the failing tests**

```python
# append to prototype/tests/test_endpoints.py
from aletheore.endpoints import _extract_gin_routes


def test_extract_gin_get_route():
    root, source = parse_go('router.GET("/ping", pingHandler)\n')

    entries = _extract_gin_routes(root, source, "main.go")

    assert entries == [
        {
            "method": "GET",
            "path": "/ping",
            "framework": "gin",
            "file": "main.go",
            "line": 1,
            "handler": "pingHandler",
            "unresolved": False,
            "note": None,
        }
    ]


def test_extract_gin_any_route_maps_to_any_method():
    root, source = parse_go('router.Any("/health", anyHandler)\n')

    entries = _extract_gin_routes(root, source, "main.go")

    assert entries[0]["method"] == "ANY"


def test_extract_gin_ignores_unrelated_selector_calls():
    root, source = parse_go('router.Use(loggerMiddleware)\n')

    entries = _extract_gin_routes(root, source, "main.go")

    assert entries == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k gin -v`
Expected: FAIL with `ImportError: cannot import name '_extract_gin_routes'`

- [ ] **Step 3: Write the implementation**

```python
# append to prototype/aletheore/endpoints.py

_GIN_VERB_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


def _extract_gin_routes(root: Node, source: bytes, rel_path: str) -> list[dict]:
    entries: list[dict] = []

    def walk(n: Node) -> None:
        if n.type == "call_expression":
            func = n.child_by_field_name("function")
            if func is not None and func.type == "selector_expression":
                field = func.child_by_field_name("field")
                if field is not None:
                    field_name = source[field.start_byte : field.end_byte].decode()
                    if field_name in _GIN_VERB_METHODS or field_name == "Any":
                        args = n.child_by_field_name("arguments")
                        if args is not None:
                            named = args.named_children
                            if named and named[0].type == "interpreted_string_literal":
                                path = _go_string_literal_text(named[0], source)
                                handler = _go_handler_name(named, source)
                                method = "ANY" if field_name == "Any" else field_name
                                entries.append(
                                    {
                                        "method": method,
                                        "path": path,
                                        "framework": "gin",
                                        "file": rel_path,
                                        "line": n.start_point[0] + 1,
                                        "handler": handler,
                                        "unresolved": False,
                                        "note": None,
                                    }
                                )
        for child in n.children:
            walk(child)

    walk(root)
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k gin -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add prototype/aletheore/endpoints.py prototype/tests/test_endpoints.py
git commit -m "feat: extract Gin routes"
```

---

### Task 4: Rust — Axum

**Files:**
- Modify: `prototype/aletheore/endpoints.py`
- Test: `prototype/tests/test_endpoints.py`

**Interfaces:**
- Produces: `_extract_axum_routes(root: Node, source: bytes, rel_path: str) -> list[dict]`.

Verified AST: `.route("/path", get(handler))` is a `call_expression` whose `function` is a
`field_expression` (`value` = the receiver, `field` = `field_identifier "route"`); its 2nd
argument is itself a `call_expression`. A chained combinator like `get(list_users).post
(create_user)` is a `call_expression` whose `function` is a `field_expression` (`value` = the
earlier combinator call, `field` = `"post"`) — recursing into `value` first and then processing
the current node's `field` walks the chain left-to-right. `any(handler)` → `"ANY"`. `.nest
("/api", router)` is the unresolved case, matched the same way `.route`/`Methods` are (a
`field_expression` with `field` `"nest"`).

- [ ] **Step 1: Write the failing tests**

```python
# append to prototype/tests/test_endpoints.py
from aletheore.scanner.graph import RUST_LANGUAGE
from aletheore.endpoints import _extract_axum_routes


def parse_rust(source: str):
    parser = Parser()
    parser.language = RUST_LANGUAGE
    tree = parser.parse(source.encode())
    return tree.root_node, source.encode()


def test_extract_axum_single_route():
    root, source = parse_rust(
        'fn main() { let app = Router::new().route("/health", get(health_handler)); }\n'
    )

    entries = _extract_axum_routes(root, source, "main.rs")

    assert entries == [
        {
            "method": "GET",
            "path": "/health",
            "framework": "axum",
            "file": "main.rs",
            "line": 1,
            "handler": "health_handler",
            "unresolved": False,
            "note": None,
        }
    ]


def test_extract_axum_chained_combinators_on_one_path():
    root, source = parse_rust(
        'fn main() { let app = Router::new().route("/users", get(list_users).post(create_user)); }\n'
    )

    entries = _extract_axum_routes(root, source, "main.rs")

    assert len(entries) == 2
    by_method = {e["method"]: e["handler"] for e in entries}
    assert by_method == {"GET": "list_users", "POST": "create_user"}
    assert all(e["path"] == "/users" for e in entries)


def test_extract_axum_any_combinator():
    root, source = parse_rust(
        'fn main() { let app = Router::new().route("/ping", any(ping_handler)); }\n'
    )

    entries = _extract_axum_routes(root, source, "main.rs")

    assert entries[0]["method"] == "ANY"


def test_extract_axum_nest_is_unresolved():
    root, source = parse_rust(
        'fn main() { let app = Router::new().nest("/api", api_router); }\n'
    )

    entries = _extract_axum_routes(root, source, "main.rs")

    assert entries == [
        {
            "method": None,
            "path": "/api",
            "framework": "axum",
            "file": "main.rs",
            "line": 1,
            "handler": "nest(...)",
            "unresolved": True,
            "note": None,
        }
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k axum -v`
Expected: FAIL with `ImportError: cannot import name '_extract_axum_routes'`

- [ ] **Step 3: Write the implementation**

```python
# append to prototype/aletheore/endpoints.py

_RUST_COMBINATOR_METHODS = {"get", "post", "put", "delete", "patch"}


def _rust_string_literal_text(node: Node, source: bytes) -> str:
    content = next((c for c in node.children if c.type == "string_content"), None)
    if content is None:
        return ""
    return source[content.start_byte : content.end_byte].decode()


def _collect_axum_combinators(node: Node, source: bytes) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []

    def walk(n: Node) -> None:
        if n.type != "call_expression":
            return
        func = n.child_by_field_name("function")
        if func is None:
            return
        if func.type == "identifier":
            name = source[func.start_byte : func.end_byte].decode()
            if name in _RUST_COMBINATOR_METHODS or name == "any":
                args = n.child_by_field_name("arguments")
                handler = "unknown"
                if args is not None:
                    named = args.named_children
                    if named and named[0].type == "identifier":
                        handler = source[named[0].start_byte : named[0].end_byte].decode()
                method = "ANY" if name == "any" else name.upper()
                results.append((method, handler))
        elif func.type == "field_expression":
            value = func.child_by_field_name("value")
            if value is not None:
                walk(value)
            field = func.child_by_field_name("field")
            if field is not None:
                field_name = source[field.start_byte : field.end_byte].decode()
                if field_name in _RUST_COMBINATOR_METHODS or field_name == "any":
                    args = n.child_by_field_name("arguments")
                    handler = "unknown"
                    if args is not None:
                        named = args.named_children
                        if named and named[0].type == "identifier":
                            handler = source[named[0].start_byte : named[0].end_byte].decode()
                    method = "ANY" if field_name == "any" else field_name.upper()
                    results.append((method, handler))

    walk(node)
    return results


def _extract_axum_routes(root: Node, source: bytes, rel_path: str) -> list[dict]:
    entries: list[dict] = []

    def walk(n: Node) -> None:
        if n.type == "call_expression":
            func = n.child_by_field_name("function")
            if func is not None and func.type == "field_expression":
                field = func.child_by_field_name("field")
                if field is not None:
                    field_name = source[field.start_byte : field.end_byte].decode()
                    if field_name == "route":
                        args = n.child_by_field_name("arguments")
                        if args is not None:
                            named = args.named_children
                            if len(named) >= 2 and named[0].type == "string_literal":
                                path = _rust_string_literal_text(named[0], source)
                                line = n.start_point[0] + 1
                                for method, handler in _collect_axum_combinators(
                                    named[1], source
                                ):
                                    entries.append(
                                        {
                                            "method": method,
                                            "path": path,
                                            "framework": "axum",
                                            "file": rel_path,
                                            "line": line,
                                            "handler": handler,
                                            "unresolved": False,
                                            "note": None,
                                        }
                                    )
                    elif field_name == "nest":
                        args = n.child_by_field_name("arguments")
                        if args is not None:
                            named = args.named_children
                            if named and named[0].type == "string_literal":
                                path = _rust_string_literal_text(named[0], source)
                                entries.append(
                                    {
                                        "method": None,
                                        "path": path,
                                        "framework": "axum",
                                        "file": rel_path,
                                        "line": n.start_point[0] + 1,
                                        "handler": "nest(...)",
                                        "unresolved": True,
                                        "note": None,
                                    }
                                )
        for child in n.children:
            walk(child)

    walk(root)
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k axum -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add prototype/aletheore/endpoints.py prototype/tests/test_endpoints.py
git commit -m "feat: extract Axum routes, including chained method combinators"
```

---

### Task 5: Java — Spring Boot

**Files:**
- Modify: `prototype/aletheore/endpoints.py`
- Test: `prototype/tests/test_endpoints.py`

**Interfaces:**
- Produces: `_extract_spring_boot_routes(root: Node, source: bytes, rel_path: str) -> list[dict]`.

Verified AST: a `method_declaration`'s `modifiers` child contains `annotation` nodes (`name`
field = the annotation identifier, `arguments` field = `annotation_argument_list` whose named
children are either a bare `string_literal` or `element_value_pair`s with `key`/`value` fields).
The class-level prefix check walks `.parent` up to the enclosing `class_declaration` and checks
its own `modifiers` for a `RequestMapping` annotation.

- [ ] **Step 1: Write the failing tests**

```python
# append to prototype/tests/test_endpoints.py
from aletheore.scanner.graph import JAVA_LANGUAGE
from aletheore.endpoints import _extract_spring_boot_routes


def parse_java(source: str):
    parser = Parser()
    parser.language = JAVA_LANGUAGE
    tree = parser.parse(source.encode())
    return tree.root_node, source.encode()


def test_extract_spring_get_mapping():
    root, source = parse_java(
        "public class UserController {\n"
        '    @GetMapping("/{id}")\n'
        "    public User getUser(Long id) { return null; }\n"
        "}\n"
    )

    entries = _extract_spring_boot_routes(root, source, "UserController.java")

    assert entries == [
        {
            "method": "GET",
            "path": "/{id}",
            "framework": "spring_boot",
            "file": "UserController.java",
            "line": 2,
            "handler": "getUser",
            "unresolved": False,
            "note": None,
        }
    ]


def test_extract_spring_request_mapping_with_explicit_method():
    root, source = parse_java(
        "public class UserController {\n"
        '    @RequestMapping(value = "/list", method = RequestMethod.GET)\n'
        "    public List<User> listUsers() { return null; }\n"
        "}\n"
    )

    entries = _extract_spring_boot_routes(root, source, "UserController.java")

    assert entries[0]["method"] == "GET"
    assert entries[0]["path"] == "/list"


def test_extract_spring_request_mapping_without_method_is_any():
    root, source = parse_java(
        "public class UserController {\n"
        '    @RequestMapping("/all")\n'
        "    public List<User> allUsers() { return null; }\n"
        "}\n"
    )

    entries = _extract_spring_boot_routes(root, source, "UserController.java")

    assert entries[0]["method"] == "ANY"


def test_extract_spring_class_level_prefix_produces_a_note():
    root, source = parse_java(
        '@RequestMapping("/api/users")\n'
        "public class UserController {\n"
        '    @GetMapping("/{id}")\n'
        "    public User getUser(Long id) { return null; }\n"
        "}\n"
    )

    entries = _extract_spring_boot_routes(root, source, "UserController.java")

    assert entries[0]["path"] == "/{id}"
    assert entries[0]["note"] == (
        "class-level @RequestMapping prefix present, not composed into this path"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k spring -v`
Expected: FAIL with `ImportError: cannot import name '_extract_spring_boot_routes'`

- [ ] **Step 3: Write the implementation**

```python
# append to prototype/aletheore/endpoints.py

_SPRING_VERB_ANNOTATIONS = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
}


def _java_string_literal_text(node: Node, source: bytes) -> str:
    content = next((c for c in node.children if c.type == "string_fragment"), None)
    if content is None:
        return ""
    return source[content.start_byte : content.end_byte].decode()


def _spring_path_from_args(args_list: Node | None, source: bytes) -> str | None:
    if args_list is None:
        return None
    for arg in args_list.named_children:
        if arg.type == "string_literal":
            return _java_string_literal_text(arg, source)
        if arg.type == "element_value_pair":
            key = arg.child_by_field_name("key")
            if key is not None and source[key.start_byte : key.end_byte].decode() == "value":
                value = arg.child_by_field_name("value")
                if value is not None and value.type == "string_literal":
                    return _java_string_literal_text(value, source)
    return None


def _spring_request_mapping_method(args_list: Node | None, source: bytes) -> str:
    if args_list is None:
        return "ANY"
    for arg in args_list.named_children:
        if arg.type == "element_value_pair":
            key = arg.child_by_field_name("key")
            if key is not None and source[key.start_byte : key.end_byte].decode() == "method":
                value = arg.child_by_field_name("value")
                if value is not None and value.type == "field_access":
                    field_node = value.child_by_field_name("field")
                    if field_node is not None:
                        return source[field_node.start_byte : field_node.end_byte].decode()
    return "ANY"


def _spring_class_prefix_note(method_node: Node, source: bytes) -> str | None:
    node = method_node.parent
    while node is not None and node.type != "class_declaration":
        node = node.parent
    if node is None:
        return None
    modifiers = next((c for c in node.children if c.type == "modifiers"), None)
    if modifiers is None:
        return None
    for ann in (c for c in modifiers.children if c.type == "annotation"):
        name_node = ann.child_by_field_name("name")
        if (
            name_node is not None
            and source[name_node.start_byte : name_node.end_byte].decode() == "RequestMapping"
        ):
            return "class-level @RequestMapping prefix present, not composed into this path"
    return None


def _extract_spring_boot_routes(root: Node, source: bytes, rel_path: str) -> list[dict]:
    entries: list[dict] = []

    def walk(n: Node) -> None:
        if n.type == "method_declaration":
            name_node = n.child_by_field_name("name")
            handler = "unknown"
            if name_node is not None:
                handler = source[name_node.start_byte : name_node.end_byte].decode()

            modifiers = next((c for c in n.children if c.type == "modifiers"), None)
            if modifiers is not None:
                for ann in (c for c in modifiers.children if c.type == "annotation"):
                    ann_name_node = ann.child_by_field_name("name")
                    if ann_name_node is None:
                        continue
                    ann_name = source[
                        ann_name_node.start_byte : ann_name_node.end_byte
                    ].decode()
                    args_list = ann.child_by_field_name("arguments")

                    method: str | None = None
                    if ann_name in _SPRING_VERB_ANNOTATIONS:
                        method = _SPRING_VERB_ANNOTATIONS[ann_name]
                    elif ann_name == "RequestMapping":
                        method = _spring_request_mapping_method(args_list, source)

                    if method is not None:
                        path = _spring_path_from_args(args_list, source)
                        if path is not None:
                            entries.append(
                                {
                                    "method": method,
                                    "path": path,
                                    "framework": "spring_boot",
                                    "file": rel_path,
                                    "line": ann.start_point[0] + 1,
                                    "handler": handler,
                                    "unresolved": False,
                                    "note": _spring_class_prefix_note(n, source),
                                }
                            )
        for child in n.children:
            walk(child)

    walk(root)
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k spring -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add prototype/aletheore/endpoints.py prototype/tests/test_endpoints.py
git commit -m "feat: extract Spring Boot routes, note class-level @RequestMapping prefixes"
```

---

### Task 6: Ruby — Rails

**Files:**
- Modify: `prototype/aletheore/endpoints.py`
- Test: `prototype/tests/test_endpoints.py`

**Interfaces:**
- Produces: `_extract_rails_routes(root: Node, source: bytes, rel_path: str) -> list[dict]`.

Verified AST: each DSL call (`get "path", to: "ctrl#action"`) is a `call` node with `method`
field (`identifier`) and `arguments` field (`argument_list` whose named children are a `string`
and/or a `pair` with `key`/`value` fields). `resources :items` has a single `simple_symbol`
argument.

- [ ] **Step 1: Write the failing tests**

```python
# append to prototype/tests/test_endpoints.py
from aletheore.scanner.graph import RUBY_LANGUAGE
from aletheore.endpoints import _extract_rails_routes


def parse_ruby(source: str):
    parser = Parser()
    parser.language = RUBY_LANGUAGE
    tree = parser.parse(source.encode())
    return tree.root_node, source.encode()


def test_extract_rails_get_route():
    root, source = parse_ruby('get "users", to: "users#index"\n')

    entries = _extract_rails_routes(root, source, "config/routes.rb")

    assert entries == [
        {
            "method": "GET",
            "path": "users",
            "framework": "rails",
            "file": "config/routes.rb",
            "line": 1,
            "handler": "users#index",
            "unresolved": False,
            "note": None,
        }
    ]


def test_extract_rails_root_route():
    root, source = parse_ruby('root to: "home#index"\n')

    entries = _extract_rails_routes(root, source, "config/routes.rb")

    assert entries == [
        {
            "method": "GET",
            "path": "/",
            "framework": "rails",
            "file": "config/routes.rb",
            "line": 1,
            "handler": "home#index",
            "unresolved": False,
            "note": None,
        }
    ]


def test_extract_rails_resources_is_unresolved():
    root, source = parse_ruby("resources :items\n")

    entries = _extract_rails_routes(root, source, "config/routes.rb")

    assert entries == [
        {
            "method": None,
            "path": "items",
            "framework": "rails",
            "file": "config/routes.rb",
            "line": 1,
            "handler": "resources(...)",
            "unresolved": True,
            "note": None,
        }
    ]


def test_extract_rails_ignores_unrelated_calls():
    root, source = parse_ruby('puts "hello"\n')

    entries = _extract_rails_routes(root, source, "config/routes.rb")

    assert entries == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k rails -v`
Expected: FAIL with `ImportError: cannot import name '_extract_rails_routes'`

- [ ] **Step 3: Write the implementation**

```python
# append to prototype/aletheore/endpoints.py

_RAILS_ROUTE_METHODS = {"get", "post", "put", "patch", "delete"}


def _ruby_string_content(node: Node, source: bytes) -> str:
    content = next((c for c in node.children if c.type == "string_content"), None)
    if content is None:
        return ""
    return source[content.start_byte : content.end_byte].decode()


def _rails_path_and_to(
    args: Node | None, source: bytes, is_root: bool
) -> tuple[str | None, str | None]:
    if args is None:
        return None, None
    path = None if not is_root else "/"
    to_value = None
    for arg in args.named_children:
        if arg.type == "string" and path is None:
            path = _ruby_string_content(arg, source)
        elif arg.type == "pair":
            key = arg.child_by_field_name("key")
            if key is not None and source[key.start_byte : key.end_byte].decode() == "to":
                value = arg.child_by_field_name("value")
                if value is not None and value.type == "string":
                    to_value = _ruby_string_content(value, source)
    return path, to_value


def _extract_rails_routes(root: Node, source: bytes, rel_path: str) -> list[dict]:
    entries: list[dict] = []

    def walk(n: Node) -> None:
        if n.type == "call":
            method_node = n.child_by_field_name("method")
            args = n.child_by_field_name("arguments")
            if method_node is not None and method_node.type == "identifier":
                method_name = source[method_node.start_byte : method_node.end_byte].decode()
                if method_name in _RAILS_ROUTE_METHODS or method_name == "root":
                    path, to_value = _rails_path_and_to(
                        args, source, is_root=(method_name == "root")
                    )
                    if to_value is not None and path is not None:
                        entries.append(
                            {
                                "method": "GET" if method_name == "root" else method_name.upper(),
                                "path": path,
                                "framework": "rails",
                                "file": rel_path,
                                "line": n.start_point[0] + 1,
                                "handler": to_value,
                                "unresolved": False,
                                "note": None,
                            }
                        )
                elif method_name == "resources" and args is not None:
                    named = args.named_children
                    if named and named[0].type == "simple_symbol":
                        resource_name = source[
                            named[0].start_byte : named[0].end_byte
                        ].decode().lstrip(":")
                        entries.append(
                            {
                                "method": None,
                                "path": resource_name,
                                "framework": "rails",
                                "file": rel_path,
                                "line": n.start_point[0] + 1,
                                "handler": "resources(...)",
                                "unresolved": True,
                                "note": None,
                            }
                        )
        for child in n.children:
            walk(child)

    walk(root)
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k rails -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add prototype/aletheore/endpoints.py prototype/tests/test_endpoints.py
git commit -m "feat: extract Rails routes, resources() recorded as unresolved"
```

---

### Task 7: PHP — Laravel

**Files:**
- Modify: `prototype/aletheore/endpoints.py`
- Test: `prototype/tests/test_endpoints.py`

**Interfaces:**
- Produces: `_extract_laravel_routes(root: Node, source: bytes, rel_path: str) -> list[dict]`.

Verified AST: `Route::get('/path', [Controller::class, 'method'])` is a
`scoped_call_expression` (`scope` field = `name "Route"`, `name` field = `name "get"`,
`arguments` field wraps each real value in an `argument` node). `Route::group(['prefix' =>
...], function () {...})`'s inner routes are still found by the general recursive walk (they're
real `scoped_call_expression` nodes nested inside the closure) — detecting the enclosing
`group()` call is done the same way as Spring Boot's class-prefix check, walking `.parent` up.

- [ ] **Step 1: Write the failing tests**

```python
# append to prototype/tests/test_endpoints.py
from aletheore.scanner.graph import PHP_LANGUAGE
from aletheore.endpoints import _extract_laravel_routes


def parse_php(source: str):
    parser = Parser()
    parser.language = PHP_LANGUAGE
    tree = parser.parse(source.encode())
    return tree.root_node, source.encode()


def test_extract_laravel_get_route():
    root, source = parse_php(
        "<?php\nRoute::get('/users', [UserController::class, 'index']);\n"
    )

    entries = _extract_laravel_routes(root, source, "routes/web.php")

    assert entries == [
        {
            "method": "GET",
            "path": "/users",
            "framework": "laravel",
            "file": "routes/web.php",
            "line": 2,
            "handler": "index",
            "unresolved": False,
            "note": None,
        }
    ]


def test_extract_laravel_match_route_multiple_methods():
    root, source = parse_php(
        "<?php\nRoute::match(['get', 'post'], '/search', [SearchController::class, 'handle']);\n"
    )

    entries = _extract_laravel_routes(root, source, "routes/web.php")

    assert {e["method"] for e in entries} == {"GET", "POST"}
    assert all(e["path"] == "/search" for e in entries)


def test_extract_laravel_route_inside_group_gets_a_note():
    root, source = parse_php(
        "<?php\n"
        "Route::group(['prefix' => 'admin'], function () {\n"
        "    Route::get('/dashboard', [AdminController::class, 'index']);\n"
        "});\n"
    )

    entries = _extract_laravel_routes(root, source, "routes/web.php")

    assert len(entries) == 1
    assert entries[0]["path"] == "/dashboard"
    assert entries[0]["note"] == (
        "declared inside a Route::group() prefix, not composed into this path"
    )


def test_extract_laravel_inline_closure_handler():
    root, source = parse_php(
        "<?php\nRoute::get('/ping', function () { return 'ok'; });\n"
    )

    entries = _extract_laravel_routes(root, source, "routes/web.php")

    assert entries[0]["handler"] == "<inline handler>"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k laravel -v`
Expected: FAIL with `ImportError: cannot import name '_extract_laravel_routes'`

- [ ] **Step 3: Write the implementation**

```python
# append to prototype/aletheore/endpoints.py

_LARAVEL_ROUTE_METHODS = {"get", "post", "put", "delete", "patch", "any"}


def _php_string_content(node: Node, source: bytes) -> str:
    content = next((c for c in node.children if c.type == "string_content"), None)
    if content is None:
        return ""
    return source[content.start_byte : content.end_byte].decode()


def _php_argument_value(arg_wrapper: Node) -> Node | None:
    return arg_wrapper.children[0] if arg_wrapper.type == "argument" and arg_wrapper.children else None


def _laravel_handler_label(node: Node | None, source: bytes) -> str:
    if node is None:
        return "unknown"
    if node.type == "array_creation_expression":
        elements = [c for c in node.named_children if c.type == "array_element_initializer"]
        if elements:
            last_value = elements[-1].children[0] if elements[-1].children else None
            if last_value is not None and last_value.type == "string":
                return _php_string_content(last_value, source)
    if node.type == "anonymous_function":
        return "<inline handler>"
    return "unknown"


def _laravel_group_note(call_node: Node, source: bytes) -> str | None:
    node = call_node.parent
    while node is not None:
        if node.type == "scoped_call_expression":
            scope = node.child_by_field_name("scope")
            name = node.child_by_field_name("name")
            if (
                scope is not None
                and source[scope.start_byte : scope.end_byte].decode() == "Route"
                and name is not None
                and source[name.start_byte : name.end_byte].decode() == "group"
            ):
                return "declared inside a Route::group() prefix, not composed into this path"
        node = node.parent
    return None


def _extract_laravel_routes(root: Node, source: bytes, rel_path: str) -> list[dict]:
    entries: list[dict] = []

    def walk(n: Node) -> None:
        if n.type == "scoped_call_expression":
            scope = n.child_by_field_name("scope")
            name = n.child_by_field_name("name")
            if scope is not None and name is not None:
                scope_text = source[scope.start_byte : scope.end_byte].decode()
                method_name = source[name.start_byte : name.end_byte].decode()
                if scope_text == "Route":
                    args = n.child_by_field_name("arguments")
                    arg_values = (
                        [_php_argument_value(a) for a in args.named_children]
                        if args is not None
                        else []
                    )
                    line = n.start_point[0] + 1
                    note = _laravel_group_note(n, source)

                    if (
                        method_name in _LARAVEL_ROUTE_METHODS
                        and arg_values
                        and arg_values[0] is not None
                        and arg_values[0].type == "string"
                    ):
                        path = _php_string_content(arg_values[0], source)
                        handler = _laravel_handler_label(
                            arg_values[1] if len(arg_values) > 1 else None, source
                        )
                        method = "ANY" if method_name == "any" else method_name.upper()
                        entries.append(
                            {
                                "method": method,
                                "path": path,
                                "framework": "laravel",
                                "file": rel_path,
                                "line": line,
                                "handler": handler,
                                "unresolved": False,
                                "note": note,
                            }
                        )
                    elif (
                        method_name == "match"
                        and len(arg_values) >= 2
                        and arg_values[0] is not None
                        and arg_values[0].type == "array_creation_expression"
                        and arg_values[1] is not None
                        and arg_values[1].type == "string"
                    ):
                        methods = [
                            _php_string_content(el.children[0], source).upper()
                            for el in arg_values[0].named_children
                            if el.type == "array_element_initializer"
                            and el.children
                            and el.children[0].type == "string"
                        ]
                        path = _php_string_content(arg_values[1], source)
                        handler = _laravel_handler_label(
                            arg_values[2] if len(arg_values) > 2 else None, source
                        )
                        for method in methods:
                            entries.append(
                                {
                                    "method": method,
                                    "path": path,
                                    "framework": "laravel",
                                    "file": rel_path,
                                    "line": line,
                                    "handler": handler,
                                    "unresolved": False,
                                    "note": note,
                                }
                            )
        for child in n.children:
            walk(child)

    walk(root)
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k laravel -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add prototype/aletheore/endpoints.py prototype/tests/test_endpoints.py
git commit -m "feat: extract Laravel routes, note routes declared inside Route::group()"
```

---

### Task 8: C# — ASP.NET Core attribute routing

**Files:**
- Modify: `prototype/aletheore/endpoints.py`
- Test: `prototype/tests/test_endpoints.py`

**Interfaces:**
- Produces: `_extract_aspnet_attribute_routes(root: Node, source: bytes, rel_path: str) ->
  list[dict]`.

Verified AST: a `method_declaration`'s `attribute_list` child contains `attribute` nodes
(`name` field = identifier; the argument, if present, is an `attribute_argument_list` **found
by type among children, not a field** — `attribute.child_by_field_name("arguments")` returned
`None` in a live check, confirmed not a real field on this grammar). Each `attribute_argument`
wraps its value as its first child.

- [ ] **Step 1: Write the failing tests**

```python
# append to prototype/tests/test_endpoints.py
from aletheore.scanner.graph import CSHARP_LANGUAGE
from aletheore.endpoints import _extract_aspnet_attribute_routes


def parse_csharp(source: str):
    parser = Parser()
    parser.language = CSHARP_LANGUAGE
    tree = parser.parse(source.encode())
    return tree.root_node, source.encode()


def test_extract_aspnet_httpget_attribute():
    root, source = parse_csharp(
        "public class UsersController {\n"
        '    [HttpGet("{id}")]\n'
        "    public User GetUser(int id) { return null; }\n"
        "}\n"
    )

    entries = _extract_aspnet_attribute_routes(root, source, "UsersController.cs")

    assert entries == [
        {
            "method": "GET",
            "path": "{id}",
            "framework": "aspnet_attribute",
            "file": "UsersController.cs",
            "line": 2,
            "handler": "GetUser",
            "unresolved": False,
            "note": None,
        }
    ]


def test_extract_aspnet_class_level_route_template_produces_a_note():
    root, source = parse_csharp(
        '[Route("api/[controller]")]\n'
        "public class UsersController {\n"
        '    [HttpGet("{id}")]\n'
        "    public User GetUser(int id) { return null; }\n"
        "}\n"
    )

    entries = _extract_aspnet_attribute_routes(root, source, "UsersController.cs")

    assert entries[0]["note"] == (
        "class-level [Route] template present, not composed into this path"
    )


def test_extract_aspnet_ignores_non_http_attributes():
    root, source = parse_csharp(
        "public class UsersController {\n"
        "    [Authorize]\n"
        "    public User GetUser(int id) { return null; }\n"
        "}\n"
    )

    entries = _extract_aspnet_attribute_routes(root, source, "UsersController.cs")

    assert entries == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k aspnet_httpget -k aspnet_class -k aspnet_ignores -v`
Expected: FAIL with `ImportError: cannot import name '_extract_aspnet_attribute_routes'`

- [ ] **Step 3: Write the implementation**

```python
# append to prototype/aletheore/endpoints.py

_ASPNET_ATTRIBUTE_METHODS = {
    "HttpGet": "GET",
    "HttpPost": "POST",
    "HttpPut": "PUT",
    "HttpDelete": "DELETE",
    "HttpPatch": "PATCH",
}


def _csharp_string_literal_text(node: Node, source: bytes) -> str:
    content = next((c for c in node.children if c.type == "string_literal_content"), None)
    if content is None:
        return ""
    return source[content.start_byte : content.end_byte].decode()


def _aspnet_attribute_path(attr_node: Node, source: bytes) -> str | None:
    args_list = next(
        (c for c in attr_node.children if c.type == "attribute_argument_list"), None
    )
    if args_list is None:
        return None
    for arg in args_list.named_children:
        if (
            arg.type == "attribute_argument"
            and arg.children
            and arg.children[0].type == "string_literal"
        ):
            return _csharp_string_literal_text(arg.children[0], source)
    return None


def _aspnet_class_prefix_note(method_node: Node, source: bytes) -> str | None:
    node = method_node.parent
    while node is not None and node.type != "class_declaration":
        node = node.parent
    if node is None:
        return None
    attr_list = next((c for c in node.children if c.type == "attribute_list"), None)
    if attr_list is None:
        return None
    for attr in (c for c in attr_list.children if c.type == "attribute"):
        name_node = attr.child_by_field_name("name")
        if (
            name_node is not None
            and source[name_node.start_byte : name_node.end_byte].decode() == "Route"
        ):
            return "class-level [Route] template present, not composed into this path"
    return None


def _extract_aspnet_attribute_routes(root: Node, source: bytes, rel_path: str) -> list[dict]:
    entries: list[dict] = []

    def walk(n: Node) -> None:
        if n.type == "method_declaration":
            name_node = n.child_by_field_name("name")
            handler = "unknown"
            if name_node is not None:
                handler = source[name_node.start_byte : name_node.end_byte].decode()

            attr_list = next((c for c in n.children if c.type == "attribute_list"), None)
            if attr_list is not None:
                for attr in (c for c in attr_list.children if c.type == "attribute"):
                    attr_name_node = attr.child_by_field_name("name")
                    if attr_name_node is None:
                        continue
                    attr_name = source[
                        attr_name_node.start_byte : attr_name_node.end_byte
                    ].decode()
                    if attr_name in _ASPNET_ATTRIBUTE_METHODS:
                        path = _aspnet_attribute_path(attr, source)
                        if path is not None:
                            entries.append(
                                {
                                    "method": _ASPNET_ATTRIBUTE_METHODS[attr_name],
                                    "path": path,
                                    "framework": "aspnet_attribute",
                                    "file": rel_path,
                                    "line": attr.start_point[0] + 1,
                                    "handler": handler,
                                    "unresolved": False,
                                    "note": _aspnet_class_prefix_note(n, source),
                                }
                            )
        for child in n.children:
            walk(child)

    walk(root)
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k "aspnet_httpget or aspnet_class or aspnet_ignores" -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add prototype/aletheore/endpoints.py prototype/tests/test_endpoints.py
git commit -m "feat: extract ASP.NET Core attribute-routed Controller endpoints"
```

---

### Task 9: C# — ASP.NET Core Minimal API

**Files:**
- Modify: `prototype/aletheore/endpoints.py`
- Test: `prototype/tests/test_endpoints.py`

**Interfaces:**
- Produces: `_extract_aspnet_minimal_routes(root: Node, source: bytes, rel_path: str) ->
  list[dict]`.

Verified AST: `app.MapGet("/path", handler)` is an `invocation_expression` whose `function` is a
`member_access_expression` (`name` field = identifier `"MapGet"`); `arguments` field wraps each
value in an `argument` node. `app.MapGroup("/api").MapGet(...)` chains the same way Go/Rust do —
the outer invocation's `member_access_expression`'s `expression` field is the inner
`invocation_expression` — but unlike Go/Axum, nothing here needs to walk that chain, since
`MapGroup` itself is matched directly as its own unresolved entry wherever it appears, the same
way Go's bare `PathPrefix` call is.

- [ ] **Step 1: Write the failing tests**

```python
# append to prototype/tests/test_endpoints.py
from aletheore.endpoints import _extract_aspnet_minimal_routes


def test_extract_aspnet_minimal_mapget():
    root, source = parse_csharp('app.MapGet("/health", HealthHandler);\n')

    entries = _extract_aspnet_minimal_routes(root, source, "Program.cs")

    assert entries == [
        {
            "method": "GET",
            "path": "/health",
            "framework": "aspnet_minimal",
            "file": "Program.cs",
            "line": 1,
            "handler": "HealthHandler",
            "unresolved": False,
            "note": None,
        }
    ]


def test_extract_aspnet_minimal_inline_lambda_handler():
    root, source = parse_csharp('app.MapGet("/ping", () => "ok");\n')

    entries = _extract_aspnet_minimal_routes(root, source, "Program.cs")

    assert entries[0]["handler"] == "<inline handler>"


def test_extract_aspnet_minimal_mapgroup_is_unresolved():
    root, source = parse_csharp('app.MapGroup("/api").MapGet("/items", GetItems);\n')

    entries = _extract_aspnet_minimal_routes(root, source, "Program.cs")

    assert any(
        e["unresolved"] and e["path"] == "/api" and e["framework"] == "aspnet_minimal"
        for e in entries
    )
    assert any(e["path"] == "/items" and e["method"] == "GET" for e in entries)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k aspnet_minimal -v`
Expected: FAIL with `ImportError: cannot import name '_extract_aspnet_minimal_routes'`

- [ ] **Step 3: Write the implementation**

```python
# append to prototype/aletheore/endpoints.py

_ASPNET_MINIMAL_METHODS = {
    "MapGet": "GET",
    "MapPost": "POST",
    "MapPut": "PUT",
    "MapDelete": "DELETE",
    "MapPatch": "PATCH",
}


def _aspnet_minimal_handler_label(arg_wrapper: Node | None, source: bytes) -> str:
    if arg_wrapper is None or not arg_wrapper.children:
        return "unknown"
    value = arg_wrapper.children[0]
    if value.type == "identifier":
        return source[value.start_byte : value.end_byte].decode()
    if value.type == "lambda_expression":
        return "<inline handler>"
    return "unknown"


def _extract_aspnet_minimal_routes(root: Node, source: bytes, rel_path: str) -> list[dict]:
    entries: list[dict] = []

    def walk(n: Node) -> None:
        if n.type == "invocation_expression":
            func = n.child_by_field_name("function")
            if func is not None and func.type == "member_access_expression":
                name_node = func.child_by_field_name("name")
                args = n.child_by_field_name("arguments")
                if name_node is not None and args is not None:
                    method_name = source[
                        name_node.start_byte : name_node.end_byte
                    ].decode()
                    named = args.named_children

                    if (
                        method_name in _ASPNET_MINIMAL_METHODS
                        and named
                        and named[0].type == "argument"
                        and named[0].children
                        and named[0].children[0].type == "string_literal"
                    ):
                        path = _csharp_string_literal_text(named[0].children[0], source)
                        handler = _aspnet_minimal_handler_label(
                            named[1] if len(named) > 1 else None, source
                        )
                        entries.append(
                            {
                                "method": _ASPNET_MINIMAL_METHODS[method_name],
                                "path": path,
                                "framework": "aspnet_minimal",
                                "file": rel_path,
                                "line": n.start_point[0] + 1,
                                "handler": handler,
                                "unresolved": False,
                                "note": None,
                            }
                        )
                    elif (
                        method_name == "MapGroup"
                        and named
                        and named[0].type == "argument"
                        and named[0].children
                        and named[0].children[0].type == "string_literal"
                    ):
                        path = _csharp_string_literal_text(named[0].children[0], source)
                        entries.append(
                            {
                                "method": None,
                                "path": path,
                                "framework": "aspnet_minimal",
                                "file": rel_path,
                                "line": n.start_point[0] + 1,
                                "handler": "MapGroup(...)",
                                "unresolved": True,
                                "note": None,
                            }
                        )
        for child in n.children:
            walk(child)

    walk(root)
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k aspnet_minimal -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add prototype/aletheore/endpoints.py prototype/tests/test_endpoints.py
git commit -m "feat: extract ASP.NET Core Minimal API endpoints"
```

---

### Task 10: Wire all 8 extractors into `map_api_endpoints`

**Files:**
- Modify: `prototype/aletheore/endpoints.py`
- Test: `prototype/tests/test_endpoints.py`

**Interfaces:**
- Consumes: all 8 extractors from Tasks 2-9.
- Modifies: `map_api_endpoints(repo_path: Path) -> dict` (same signature, same return shape).

- [ ] **Step 1: Write the failing test**

```python
# append to prototype/tests/test_endpoints.py

def test_map_api_endpoints_covers_all_new_languages(tmp_path):
    (tmp_path / "main.go").write_text(
        'package main\nfunc main() { http.HandleFunc("/health", h) }\n'
    )
    (tmp_path / "server.rs").write_text(
        'fn main() { let app = Router::new().route("/ping", get(ping)); }\n'
    )
    (tmp_path / "Controller.java").write_text(
        'public class C {\n    @GetMapping("/x")\n    public void x() {}\n}\n'
    )
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "routes.rb").write_text('get "y", to: "y#index"\n')
    (tmp_path / "routes").mkdir()
    (tmp_path / "routes" / "web.php").write_text(
        "<?php\nRoute::get('/z', [Z::class, 'index']);\n"
    )
    (tmp_path / "Program.cs").write_text('app.MapGet("/w", W);\n')

    result = map_api_endpoints(tmp_path)

    paths = {e["path"] for e in result["endpoints"]}
    assert paths == {"/health", "/ping", "/x", "y", "/z", "/w"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -k covers_all_new_languages -v`
Expected: FAIL — only `/health`... actually FAILS because none of the new extensions are wired
yet (`.go`/`.rs`/`.java`/`.rb`/`.php`/`.cs` aren't in `map_api_endpoints`'s branch list).

- [ ] **Step 3: Wire the new extractors**

Add these imports at the top of the language-constant import block:

```python
from aletheore.scanner.graph import (
    CSHARP_LANGUAGE,
    GO_LANGUAGE,
    JAVA_LANGUAGE,
    JS_LANGUAGE,
    PHP_LANGUAGE,
    PY_LANGUAGE,
    RUBY_LANGUAGE,
    RUST_LANGUAGE,
    TS_LANGUAGE,
    TSX_LANGUAGE,
    _iter_source_files,
    _rel,
)
```

Replace `map_api_endpoints`'s body:

```python
def map_api_endpoints(repo_path: Path) -> dict:
    endpoints: list[dict] = []

    parsers: dict[str, Parser] = {}
    for name, lang in (
        ("py", PY_LANGUAGE),
        ("js", JS_LANGUAGE),
        ("ts", TS_LANGUAGE),
        ("tsx", TSX_LANGUAGE),
        ("go", GO_LANGUAGE),
        ("rs", RUST_LANGUAGE),
        ("java", JAVA_LANGUAGE),
        ("rb", RUBY_LANGUAGE),
        ("php", PHP_LANGUAGE),
        ("cs", CSHARP_LANGUAGE),
    ):
        p = Parser()
        p.language = lang
        parsers[name] = p

    for path in _iter_source_files(repo_path):
        rel_path = _rel(repo_path, path)
        suffix = path.suffix

        if suffix == ".py":
            source = path.read_bytes()
            tree = parsers["py"].parse(source)
            endpoints.extend(_extract_flask_fastapi_routes(tree.root_node, source, rel_path))
            if path.name == "urls.py":
                endpoints.extend(_extract_django_routes(tree.root_node, source, rel_path))
        elif suffix in (".js", ".jsx"):
            source = path.read_bytes()
            tree = parsers["js"].parse(source)
            endpoints.extend(_extract_express_routes(tree.root_node, source, rel_path))
        elif suffix == ".ts":
            source = path.read_bytes()
            tree = parsers["ts"].parse(source)
            endpoints.extend(_extract_express_routes(tree.root_node, source, rel_path))
        elif suffix == ".tsx":
            source = path.read_bytes()
            tree = parsers["tsx"].parse(source)
            endpoints.extend(_extract_express_routes(tree.root_node, source, rel_path))
        elif suffix == ".go":
            source = path.read_bytes()
            tree = parsers["go"].parse(source)
            endpoints.extend(_extract_go_net_http_routes(tree.root_node, source, rel_path))
            endpoints.extend(_extract_gin_routes(tree.root_node, source, rel_path))
        elif suffix == ".rs":
            source = path.read_bytes()
            tree = parsers["rs"].parse(source)
            endpoints.extend(_extract_axum_routes(tree.root_node, source, rel_path))
        elif suffix == ".java":
            source = path.read_bytes()
            tree = parsers["java"].parse(source)
            endpoints.extend(_extract_spring_boot_routes(tree.root_node, source, rel_path))
        elif suffix == ".rb" and path.name == "routes.rb":
            source = path.read_bytes()
            tree = parsers["rb"].parse(source)
            endpoints.extend(_extract_rails_routes(tree.root_node, source, rel_path))
        elif suffix == ".php" and "routes" in Path(rel_path).parts:
            source = path.read_bytes()
            tree = parsers["php"].parse(source)
            endpoints.extend(_extract_laravel_routes(tree.root_node, source, rel_path))
        elif suffix == ".cs":
            source = path.read_bytes()
            tree = parsers["cs"].parse(source)
            endpoints.extend(_extract_aspnet_attribute_routes(tree.root_node, source, rel_path))
            endpoints.extend(_extract_aspnet_minimal_routes(tree.root_node, source, rel_path))

    return {"checked": True, "endpoints": endpoints}
```

Note: `"routes" in path.parts` matches any file under a directory literally named `routes`
anywhere in the relative path (matching Laravel's own `routes/web.php`/`routes/api.php`
convention), not just a direct child of the repo root.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd prototype && python3 -m pytest tests/test_endpoints.py -v`
Expected: all pass (roughly 45 tests in this file now).

- [ ] **Step 5: Run the full suite**

Run: `cd prototype && python3 -m pytest -q`
Expected: all pass, no regressions in `test_evidence.py`, `test_query.py`, `test_mcp_server.py`,
`test_history.py`, `test_cli.py`, `test_healthcheck.py` (none of them assert exact endpoint
counts beyond what Task 1 already updated).

- [ ] **Step 6: Commit**

```bash
git add prototype/aletheore/endpoints.py prototype/tests/test_endpoints.py
git commit -m "feat: wire Go/Rust/Java/Ruby/PHP/C# extractors into map_api_endpoints"
```

---

### Task 11: Real live verification across all 6 languages

Not a TDD task — the same live-verification discipline used for every previous language and
framework addition in this project. The base toolchains (Go, Rust/cargo, Java/JDK, Ruby, PHP,
.NET SDK) are already installed from the original module-graph work; install the
framework-specific pieces fresh, run each app for real, and confirm the extractor matches.

- [ ] **Step 1: Go — stdlib + gorilla/mux + Gin**

```bash
mkdir -p /tmp/aletheore-lang-check/goapp && cd /tmp/aletheore-lang-check/goapp
go mod init example.com/goapp
go get github.com/gorilla/mux github.com/gin-gonic/gin
cat > main.go <<'EOF'
package main

import (
	"net/http"
	"github.com/gorilla/mux"
	"github.com/gin-gonic/gin"
)

func health(w http.ResponseWriter, r *http.Request) {}
func listItems(w http.ResponseWriter, r *http.Request) {}

func main() {
	http.HandleFunc("/health", health)

	r := mux.NewRouter()
	r.HandleFunc("/items", listItems).Methods("GET", "POST")

	g := gin.Default()
	g.GET("/ping", func(c *gin.Context) {})

	_ = r
	_ = g
}
EOF
go build ./...
python3 -c "
from pathlib import Path
from aletheore.endpoints import map_api_endpoints
result = map_api_endpoints(Path('.'))
for e in result['endpoints']:
    print(e)
assert any(e['path'] == '/health' for e in result['endpoints'])
assert any(e['path'] == '/items' and e['method'] == 'POST' for e in result['endpoints'])
assert any(e['path'] == '/ping' and e['framework'] == 'gin' for e in result['endpoints'])
"
```

Expected: `go build` succeeds for real, and the printed entries match `/health` (ANY,
go_net_http), `/items` (GET+POST, gorilla_mux), `/ping` (GET, gin).

- [ ] **Step 2: Rust — Axum**

```bash
mkdir -p /tmp/aletheore-lang-check/rustapp && cd /tmp/aletheore-lang-check/rustapp
cargo init --name rustapp
cargo add axum tokio --features tokio/full
cat > src/main.rs <<'EOF'
use axum::{Router, routing::get};

async fn health() -> &'static str { "ok" }
async fn list_items() -> &'static str { "ok" }

#[tokio::main]
async fn main() {
    let app = Router::new()
        .route("/health", get(health))
        .route("/items", get(list_items));
    let _ = app;
}
EOF
cargo build
python3 -c "
from pathlib import Path
from aletheore.endpoints import map_api_endpoints
result = map_api_endpoints(Path('.'))
paths = {e['path'] for e in result['endpoints']}
assert paths == {'/health', '/items'}
"
```

Expected: `cargo build` succeeds for real; both routes detected.

- [ ] **Step 3: Java — Spring Boot**

```bash
mkdir -p /tmp/aletheore-lang-check/springapp && cd /tmp/aletheore-lang-check/springapp
curl https://start.spring.io/starter.zip -d dependencies=web -d type=maven-project \
  -d javaVersion=17 -o starter.zip
unzip -q starter.zip
cat > src/main/java/com/example/demo/UserController.java <<'EOF'
package com.example.demo;

import org.springframework.web.bind.annotation.*;

@RestController
public class UserController {
    @GetMapping("/users/{id}")
    public String getUser() { return "ok"; }
}
EOF
./mvnw -q compile
python3 -c "
from pathlib import Path
from aletheore.endpoints import map_api_endpoints
result = map_api_endpoints(Path('.'))
assert any(e['path'] == '/users/{id}' and e['method'] == 'GET' for e in result['endpoints'])
"
```

Expected: `./mvnw compile` succeeds for real; the route is detected.

- [ ] **Step 4: Ruby — Rails**

```bash
gem install rails -N
mkdir -p /tmp/aletheore-lang-check && cd /tmp/aletheore-lang-check
rails new railsapp --minimal --skip-bundle
cd railsapp
cat >> config/routes.rb <<'EOF'
get "ping", to: "pings#show"
EOF
ruby -c config/routes.rb
python3 -c "
from pathlib import Path
from aletheore.endpoints import map_api_endpoints
result = map_api_endpoints(Path('.'))
assert any(e['path'] == 'ping' and e['handler'] == 'pings#show' for e in result['endpoints'])
assert any(e['unresolved'] for e in result['endpoints'])  # the scaffolded root/resources, if any
"
```

Expected: `ruby -c` confirms the routes file is syntactically real Ruby; the route is detected.

- [ ] **Step 5: PHP — Laravel**

```bash
composer create-project laravel/laravel /tmp/aletheore-lang-check/laravelapp
cd /tmp/aletheore-lang-check/laravelapp
cat >> routes/web.php <<'EOF'
Route::get('/ping', function () { return 'ok'; });
EOF
php -l routes/web.php
python3 -c "
from pathlib import Path
from aletheore.endpoints import map_api_endpoints
result = map_api_endpoints(Path('.'))
assert any(e['path'] == '/ping' and e['handler'] == '<inline handler>' for e in result['endpoints'])
"
```

Expected: `php -l` confirms valid PHP; the route is detected.

- [ ] **Step 6: C# — ASP.NET Core Minimal API + attribute routing**

```bash
mkdir -p /tmp/aletheore-lang-check/dotnetapp && cd /tmp/aletheore-lang-check/dotnetapp
dotnet new web
cat >> Program.cs <<'EOF'
app.MapGet("/ping", () => "ok");
EOF
mkdir Controllers
cat > Controllers/UsersController.cs <<'EOF'
using Microsoft.AspNetCore.Mvc;

[ApiController]
public class UsersController : ControllerBase
{
    [HttpGet("/users/{id}")]
    public string GetUser(int id) { return "ok"; }
}
EOF
dotnet build
python3 -c "
from pathlib import Path
from aletheore.endpoints import map_api_endpoints
result = map_api_endpoints(Path('.'))
assert any(e['path'] == '/ping' and e['framework'] == 'aspnet_minimal' for e in result['endpoints'])
assert any(e['path'] == '/users/{id}' and e['framework'] == 'aspnet_attribute' for e in result['endpoints'])
"
```

Expected: `dotnet build` succeeds for real; both conventions detected in the same repo.

- [ ] **Step 7: Clean up scratch directories**

```bash
rm -rf /tmp/aletheore-lang-check
```

---

### Task 12: Documentation

**Files:**
- Modify: `prototype/README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update `prototype/README.md`**

Update the API-endpoint-mapping paragraph to list all 10 frameworks now covered: "Flask,
FastAPI-style decorators, Django `urlpatterns`, Express, Go (`net/http`/`gorilla/mux` and Gin),
Rust (Axum), Java (Spring Boot), Ruby (Rails), PHP (Laravel), and C# (both attribute-routed
Controllers and Minimal API)." Mention the `note` field and what it means.

- [ ] **Step 2: Update `CHANGELOG.md`**

Add to `## Unreleased`:

```markdown
- Extended static API endpoint mapping to 8 more frameworks across 6 languages: Go (stdlib
  `net/http`/`gorilla/mux`, and Gin), Rust (Axum), Java (Spring Boot), Ruby (Rails), PHP
  (Laravel), and C# (both attribute-routed Controllers and Minimal API) - 10 frameworks total
  now, up from 4. Endpoint entries gain a `note` field for same-file prefixes that aren't
  composed into the recorded path (Spring Boot's class-level `@RequestMapping`, C#'s `[Route]`
  template, Laravel's `Route::group` prefix), alongside the existing `unresolved` flag for
  distinct mount/include-style indirection (Go's `.PathPrefix().Subrouter()`, Axum's `.nest`,
  Rails' `resources`, C#'s `MapGroup`).
```

- [ ] **Step 3: Commit**

```bash
git add prototype/README.md CHANGELOG.md
git commit -m "docs: document multi-language API endpoint mapping"
```

## Success Criteria (from the spec, restated for final verification)

1. Each of the 8 new extractors, run against a real compiled/running instance (Task 11),
   produces entries matching that framework's actual routes exactly.
2. Each language's identified indirection case (gorilla/mux subrouter, Axum `.nest`, Rails
   `resources`, C# `MapGroup`) is `unresolved: true`; each same-file prefix case (Spring Boot,
   ASP.NET attribute routing, Laravel groups) carries a populated `note` — never silently
   resolved, never silently dropped.
3. Every Phase 1 test (Flask/FastAPI/Django/Express) passes with only the additive
   `"note": None` key changed.
4. `aletheore query endpoints`, `aletheore_endpoints`, `aletheore diff`, and `aletheore
   healthcheck` all continue working unchanged (verified in Task 10 Step 5's full suite run).
