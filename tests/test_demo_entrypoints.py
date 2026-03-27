import importlib


def test_demo_ui_module_imports_without_relative_import_errors() -> None:
    module = importlib.import_module("thesis_prototype.demo_ui")
    assert hasattr(module, "run")


def test_demo_api_module_imports_without_relative_import_errors() -> None:
    module = importlib.import_module("thesis_prototype.demo_api")
    assert hasattr(module, "create_fastapi_app")
