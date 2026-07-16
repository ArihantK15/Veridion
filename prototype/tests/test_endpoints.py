from tree_sitter import Parser

from aletheore.endpoints import (
    _extract_django_routes,
    _extract_express_routes,
    _extract_flask_fastapi_routes,
    map_api_endpoints,
)
from aletheore.scanner.graph import JS_LANGUAGE, PY_LANGUAGE


def parse_python(source: str):
    parser = Parser()
    parser.language = PY_LANGUAGE
    tree = parser.parse(source.encode())
    return tree.root_node, source.encode()


def parse_js(source: str):
    parser = Parser()
    parser.language = JS_LANGUAGE
    tree = parser.parse(source.encode())
    return tree.root_node, source.encode()


def test_extract_flask_route_decorator_with_methods():
    root, source = parse_python(
        '@app.route("/users/<int:id>", methods=["GET", "POST"])\n'
        "def get_user(id):\n"
        "    pass\n"
    )

    entries = _extract_flask_fastapi_routes(root, source, "app/routes.py")

    assert len(entries) == 2
    methods = {e["method"] for e in entries}
    assert methods == {"GET", "POST"}
    for entry in entries:
        assert entry["path"] == "/users/<int:id>"
        assert entry["framework"] == "flask"
        assert entry["file"] == "app/routes.py"
        assert entry["handler"] == "get_user"
        assert entry["unresolved"] is False


def test_extract_flask_route_defaults_to_get_when_no_methods_kwarg():
    root, source = parse_python('@app.route("/ping")\ndef ping():\n    pass\n')

    entries = _extract_flask_fastapi_routes(root, source, "app.py")

    assert len(entries) == 1
    assert entries[0]["method"] == "GET"


def test_extract_fastapi_verb_decorator_labeled_ambiguous():
    root, source = parse_python(
        '@router.get("/items/{item_id}")\ndef read_item(item_id):\n    pass\n'
    )

    entries = _extract_flask_fastapi_routes(root, source, "app/api.py")

    assert entries == [
        {
            "method": "GET",
            "path": "/items/{item_id}",
            "framework": "flask_or_fastapi",
            "file": "app/api.py",
            "line": 1,
            "handler": "read_item",
            "unresolved": False,
        }
    ]


def test_extract_flask_fastapi_ignores_non_route_decorators():
    root, source = parse_python("@staticmethod\ndef helper():\n    pass\n")

    entries = _extract_flask_fastapi_routes(root, source, "app.py")

    assert entries == []


def test_extract_flask_fastapi_handles_multiple_decorators_on_one_function():
    root, source = parse_python(
        '@app.get("/a")\n@some_other_decorator\ndef handler():\n    pass\n'
    )

    entries = _extract_flask_fastapi_routes(root, source, "app.py")

    assert len(entries) == 1
    assert entries[0]["path"] == "/a"


def test_extract_django_path_call():
    root, source = parse_python(
        "urlpatterns = [\n"
        "    path('users/<int:id>/', views.get_user, name='get_user'),\n"
        "]\n"
    )

    entries = _extract_django_routes(root, source, "app/urls.py")

    assert entries == [
        {
            "method": "ANY",
            "path": "users/<int:id>/",
            "framework": "django",
            "file": "app/urls.py",
            "line": 2,
            "handler": "views.get_user",
            "unresolved": False,
        }
    ]


def test_extract_django_re_path_call():
    root, source = parse_python("urlpatterns = [re_path(r'^items/$', views.list_items)]\n")

    entries = _extract_django_routes(root, source, "app/urls.py")

    assert len(entries) == 1
    assert entries[0]["path"] == "^items/$"
    assert entries[0]["handler"] == "views.list_items"


def test_extract_django_include_is_recorded_as_unresolved():
    root, source = parse_python('urlpatterns = [include("myapp.urls")]\n')

    entries = _extract_django_routes(root, source, "project/urls.py")

    assert entries == [
        {
            "method": None,
            "path": "myapp.urls",
            "framework": "django",
            "file": "project/urls.py",
            "line": 1,
            "handler": "include(...)",
            "unresolved": True,
        }
    ]


def test_extract_django_ignores_non_urlpatterns_assignments():
    root, source = parse_python("app_name = 'myapp'\n")

    entries = _extract_django_routes(root, source, "app/urls.py")

    assert entries == []


def test_extract_express_get_route_with_named_handler():
    root, source = parse_js('app.get("/users", listUsers);\n')

    entries = _extract_express_routes(root, source, "server.js")

    assert entries == [
        {
            "method": "GET",
            "path": "/users",
            "framework": "express",
            "file": "server.js",
            "line": 1,
            "handler": "listUsers",
            "unresolved": False,
        }
    ]


def test_extract_express_route_with_inline_arrow_handler():
    root, source = parse_js('app.post("/users", (req, res) => { res.send("ok"); });\n')

    entries = _extract_express_routes(root, source, "server.js")

    assert len(entries) == 1
    assert entries[0]["method"] == "POST"
    assert entries[0]["handler"] == "<inline handler>"


def test_extract_express_router_all_maps_to_any():
    root, source = parse_js("router.all('/health', handler);\n")

    entries = _extract_express_routes(root, source, "routes.js")

    assert entries[0]["method"] == "ANY"


def test_extract_express_mounted_router_is_recorded_as_unresolved():
    root, source = parse_js("app.use('/api', apiRouter);\n")

    entries = _extract_express_routes(root, source, "server.js")

    assert entries == [
        {
            "method": None,
            "path": "/api",
            "framework": "express",
            "file": "server.js",
            "line": 1,
            "handler": "app.use(...)",
            "unresolved": True,
        }
    ]


def test_extract_express_ignores_unrelated_method_calls():
    root, source = parse_js('res.send("ok");\napp.listen(3000);\n')

    entries = _extract_express_routes(root, source, "server.js")

    assert entries == []


def test_map_api_endpoints_combines_all_frameworks(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "routes.py").write_text(
        '@app.route("/users")\ndef list_users():\n    pass\n'
    )
    (tmp_path / "app" / "urls.py").write_text(
        "urlpatterns = [path('items/', views.list_items)]\n"
    )
    (tmp_path / "server.js").write_text('app.get("/health", healthCheck);\n')

    result = map_api_endpoints(tmp_path)

    assert result["checked"] is True
    paths = {e["path"] for e in result["endpoints"]}
    assert paths == {"/users", "items/", "/health"}


def test_map_api_endpoints_only_treats_urls_py_as_django_routes(tmp_path):
    (tmp_path / "not_urls.py").write_text(
        "urlpatterns = [path('items/', views.list_items)]\n"
    )

    result = map_api_endpoints(tmp_path)

    assert result["endpoints"] == []


def test_map_api_endpoints_empty_repo_returns_checked_true_empty_list(tmp_path):
    (tmp_path / "README.md").write_text("hello\n")

    result = map_api_endpoints(tmp_path)

    assert result == {"checked": True, "endpoints": []}
