from pathlib import Path

from tree_sitter import Node, Parser

from aletheore.scanner.graph import (
    JS_LANGUAGE,
    PY_LANGUAGE,
    TS_LANGUAGE,
    TSX_LANGUAGE,
    _iter_source_files,
    _rel,
)

_ROUTE_VERB_METHODS = {"get", "post", "put", "delete", "patch"}
_DJANGO_ROUTE_FUNCS = {"path", "re_path"}
_EXPRESS_ROUTE_METHODS = {"get", "post", "put", "delete", "patch", "all"}


def _string_literal_text(node: Node, source: bytes) -> str:
    raw = source[node.start_byte : node.end_byte].decode()
    if raw.startswith(("r'", 'r"', "R'", 'R"')):
        raw = raw[1:]
    return raw.strip("'\"")


def _extract_flask_fastapi_routes(root: Node, source: bytes, rel_path: str) -> list[dict]:
    entries: list[dict] = []

    def walk(n: Node) -> None:
        if n.type == "decorated_definition":
            definition = n.child_by_field_name("definition")
            handler = "unknown"
            if definition is not None and definition.type == "function_definition":
                name_node = definition.child_by_field_name("name")
                if name_node is not None:
                    handler = source[name_node.start_byte : name_node.end_byte].decode()

            for decorator in (c for c in n.children if c.type == "decorator"):
                call = next((c for c in decorator.named_children if c.type == "call"), None)
                if call is None:
                    continue
                func = call.child_by_field_name("function")
                if func is None or func.type != "attribute":
                    continue
                attribute_node = func.child_by_field_name("attribute")
                if attribute_node is None:
                    continue
                attribute_name = source[
                    attribute_node.start_byte : attribute_node.end_byte
                ].decode()

                args = call.child_by_field_name("arguments")
                if args is None:
                    continue
                path_node = next((a for a in args.named_children if a.type == "string"), None)
                if path_node is None:
                    continue
                path = _string_literal_text(path_node, source)
                line = decorator.start_point[0] + 1

                if attribute_name == "route":
                    methods = ["GET"]
                    for arg in args.named_children:
                        if arg.type != "keyword_argument":
                            continue
                        kw_name = arg.child_by_field_name("name")
                        if kw_name is None:
                            continue
                        if source[kw_name.start_byte : kw_name.end_byte].decode() != "methods":
                            continue
                        value = arg.child_by_field_name("value")
                        if value is not None and value.type == "list":
                            methods = [
                                _string_literal_text(item, source).upper()
                                for item in value.named_children
                                if item.type == "string"
                            ]
                    for method in methods:
                        entries.append(
                            {
                                "method": method,
                                "path": path,
                                "framework": "flask",
                                "file": rel_path,
                                "line": line,
                                "handler": handler,
                                "unresolved": False,
                            }
                        )
                elif attribute_name in _ROUTE_VERB_METHODS:
                    entries.append(
                        {
                            "method": attribute_name.upper(),
                            "path": path,
                            "framework": "flask_or_fastapi",
                            "file": rel_path,
                            "line": line,
                            "handler": handler,
                            "unresolved": False,
                        }
                    )
        for child in n.children:
            walk(child)

    walk(root)
    return entries


def _extract_django_routes(root: Node, source: bytes, rel_path: str) -> list[dict]:
    entries: list[dict] = []

    def walk(n: Node) -> None:
        if n.type == "assignment":
            left = n.child_by_field_name("left")
            right = n.child_by_field_name("right")
            is_urlpatterns = (
                left is not None
                and left.type == "identifier"
                and source[left.start_byte : left.end_byte].decode() == "urlpatterns"
            )
            if is_urlpatterns and right is not None and right.type == "list":
                for item in right.named_children:
                    entry = _django_call_to_entry(item, source, rel_path)
                    if entry is not None:
                        entries.append(entry)
        for child in n.children:
            walk(child)

    walk(root)
    return entries


def _django_call_to_entry(call: Node, source: bytes, rel_path: str) -> dict | None:
    if call.type != "call":
        return None
    func = call.child_by_field_name("function")
    if func is None or func.type != "identifier":
        return None
    func_name = source[func.start_byte : func.end_byte].decode()
    if func_name not in _DJANGO_ROUTE_FUNCS and func_name != "include":
        return None

    args = call.child_by_field_name("arguments")
    if args is None:
        return None
    positional = [a for a in args.named_children if a.type != "keyword_argument"]
    if not positional or positional[0].type != "string":
        return None
    path = _string_literal_text(positional[0], source)
    line = call.start_point[0] + 1

    if func_name == "include":
        return {
            "method": None,
            "path": path,
            "framework": "django",
            "file": rel_path,
            "line": line,
            "handler": "include(...)",
            "unresolved": True,
        }

    handler = "unknown"
    if len(positional) >= 2:
        view = positional[1]
        handler = source[view.start_byte : view.end_byte].decode()

    return {
        "method": "ANY",
        "path": path,
        "framework": "django",
        "file": rel_path,
        "line": line,
        "handler": handler,
        "unresolved": False,
    }


def _js_string_literal_text(node: Node, source: bytes) -> str:
    raw = source[node.start_byte : node.end_byte].decode()
    return raw.strip("'\"")


def _express_handler_label(node: Node | None, source: bytes) -> str:
    if node is None:
        return "unknown"
    if node.type == "identifier":
        return source[node.start_byte : node.end_byte].decode()
    return "<inline handler>"


def _extract_express_routes(root: Node, source: bytes, rel_path: str) -> list[dict]:
    entries: list[dict] = []

    def walk(n: Node) -> None:
        if n.type == "call_expression":
            func = n.child_by_field_name("function")
            if func is not None and func.type == "member_expression":
                property_node = func.child_by_field_name("property")
                args = n.child_by_field_name("arguments")
                if property_node is not None and args is not None:
                    method_name = source[
                        property_node.start_byte : property_node.end_byte
                    ].decode()
                    named = args.named_children
                    if named and named[0].type == "string":
                        path = _js_string_literal_text(named[0], source)
                        line = n.start_point[0] + 1
                        handler_node = named[1] if len(named) > 1 else None

                        if method_name in _EXPRESS_ROUTE_METHODS:
                            entries.append(
                                {
                                    "method": (
                                        "ANY" if method_name == "all" else method_name.upper()
                                    ),
                                    "path": path,
                                    "framework": "express",
                                    "file": rel_path,
                                    "line": line,
                                    "handler": _express_handler_label(handler_node, source),
                                    "unresolved": False,
                                }
                            )
                        elif method_name == "use":
                            entries.append(
                                {
                                    "method": None,
                                    "path": path,
                                    "framework": "express",
                                    "file": rel_path,
                                    "line": line,
                                    "handler": "app.use(...)",
                                    "unresolved": True,
                                }
                            )
        for child in n.children:
            walk(child)

    walk(root)
    return entries


def map_api_endpoints(repo_path: Path) -> dict:
    endpoints: list[dict] = []

    py_parser = Parser()
    py_parser.language = PY_LANGUAGE
    js_parser = Parser()
    js_parser.language = JS_LANGUAGE
    ts_parser = Parser()
    ts_parser.language = TS_LANGUAGE
    tsx_parser = Parser()
    tsx_parser.language = TSX_LANGUAGE

    for path in _iter_source_files(repo_path):
        rel_path = _rel(repo_path, path)
        suffix = path.suffix

        if suffix == ".py":
            source = path.read_bytes()
            tree = py_parser.parse(source)
            endpoints.extend(_extract_flask_fastapi_routes(tree.root_node, source, rel_path))
            if path.name == "urls.py":
                endpoints.extend(_extract_django_routes(tree.root_node, source, rel_path))
        elif suffix in (".js", ".jsx"):
            source = path.read_bytes()
            tree = js_parser.parse(source)
            endpoints.extend(_extract_express_routes(tree.root_node, source, rel_path))
        elif suffix == ".ts":
            source = path.read_bytes()
            tree = ts_parser.parse(source)
            endpoints.extend(_extract_express_routes(tree.root_node, source, rel_path))
        elif suffix == ".tsx":
            source = path.read_bytes()
            tree = tsx_parser.parse(source)
            endpoints.extend(_extract_express_routes(tree.root_node, source, rel_path))

    return {"checked": True, "endpoints": endpoints}
