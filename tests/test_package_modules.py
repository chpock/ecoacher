import importlib


def test_package_modules_have_docstrings():
    modules = [
        "ecoacher",
        "ecoacher.app",
        "ecoacher.config",
        "ecoacher.ipc",
        "ecoacher.logging",
        "ecoacher.opencode",
        "ecoacher.spellcheck",
        "ecoacher.text",
    ]
    for module_name in modules:
        module = importlib.import_module(module_name)
        assert module.__doc__
