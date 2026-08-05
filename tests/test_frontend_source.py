"""
Guarantees that used to be checkable by grepping server-rendered HTML
(status dot always present, Auto is the default LLM mode) moved into
React component state/markup when the frontend was rewritten
(2026-08-06) - a plain HTTP request no longer sees them, since they
only exist after the browser runs the built JS. These tests check the
same guarantees at the source level instead: cheap, no browser needed,
and they still catch someone silently changing the default or
dropping the status indicator from a page.

This is a real trade-off, not a free win: these tests can't catch a
regression introduced by a *build* step, a runtime error, or incorrect
wiring between components - only a real browser check (or the
Vitest/Testing Library setup deferred for later, see docs/decisions.md)
covers that. Combined with the live-verification pass done after every
frontend change in this project, that gap is judged acceptable for now.
"""

from pathlib import Path

FRONTEND_SRC = Path(__file__).resolve().parent.parent / "webapp" / "frontend" / "src"
STATIC_DIR = Path(__file__).resolve().parent.parent / "webapp" / "static"


def _read(*parts):
    return (FRONTEND_SRC / Path(*parts)).read_text(encoding="utf-8")


def test_llm_mode_defaults_to_auto():
    chat_source = _read("pages", "Chat.jsx")
    assert "useState('auto')" in chat_source


def test_header_component_always_renders_status_dot():
    header_source = _read("components", "Header.jsx")
    assert "<StatusDot" in header_source


def test_chat_page_uses_the_shared_header():
    chat_source = _read("pages", "Chat.jsx")
    assert "<Header" in chat_source


def test_dashboard_page_uses_the_shared_header():
    dashboard_source = _read("pages", "Dashboard.jsx")
    assert "<Header" in dashboard_source


def test_landing_page_links_to_chat_and_dashboard():
    landing_source = _read("pages", "Landing.jsx")
    assert 'href="/chat"' in landing_source
    assert 'href="/dashboard"' in landing_source


def test_llm_picker_still_has_all_four_modes():
    picker_source = _read("components", "LlmPicker.jsx")
    for mode in ("off", "ollama", "groq", "auto"):
        assert f"value: '{mode}'" in picker_source


def test_built_frontend_output_exists():
    # Sanity check the build actually ran and landed where backend.py
    # expects it (webapp/static/, see .gitignore - it's a build
    # artifact, not committed). Skips rather than fails on a fresh
    # checkout that hasn't run `npm run build` yet, since that's a
    # real, expected state (documented in docs/docker_setup.md), not a
    # regression.
    if not (STATIC_DIR / "landing.html").exists():
        import pytest

        pytest.skip("frontend not built yet - run `npm run build` in webapp/frontend/")

    for name in ("landing.html", "chat.html", "dashboard.html"):
        assert (STATIC_DIR / name).exists()
    assert (STATIC_DIR / "assets").is_dir()
    assert any((STATIC_DIR / "assets").iterdir())
