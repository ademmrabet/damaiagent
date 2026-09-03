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


def test_header_supports_a_hamburger_menu_button():
    header_source = _read("components", "Header.jsx")
    assert "onMenuClick" in header_source
    assert "hamburger-btn" in header_source


def test_chat_page_wires_up_the_mobile_sidebar_toggle():
    chat_source = _read("pages", "Chat.jsx")
    assert "sidebarOpen" in chat_source
    assert "onMenuClick" in chat_source
    assert "sidebar-backdrop" in chat_source


def test_chat_page_surfaces_detected_language_to_the_user():
    # Multi-language support (2026-08-06, see docs/decisions.md) is
    # invisible to the user without this - the backend detects and
    # translates transparently, but a French/Spanish/Portuguese/Arabic
    # question getting answered without any on-screen sign it was
    # translated would look like a silent black box.
    chat_source = _read("pages", "Chat.jsx")
    assert "detectedLanguage" in chat_source
    assert "lang-badge" in chat_source
    assert "translationError" in chat_source


def test_conversation_sidebar_becomes_an_off_canvas_drawer_on_mobile():
    css_source = _read("components", "conversationSidebar.css")
    assert "position: fixed" in css_source
    assert ".conversation-sidebar.open" in css_source


def test_dashboard_has_a_chapter_filter():
    dashboard_source = _read("pages", "Dashboard.jsx")
    assert "selectedChapter" in dashboard_source
    assert "data.chapters" in dashboard_source


def test_dashboard_action_chart_is_clickable_to_filter_roles():
    dashboard_source = _read("pages", "Dashboard.jsx")
    assert "selectedAction" in dashboard_source
    assert "onClick" in dashboard_source
    assert "roles_by_action" in dashboard_source


def test_chart_canvas_rerenders_on_data_change():
    # Real bug caught during the dashboard rework (2026-08-06): the
    # original version built the Chart.js instance once on mount
    # (empty effect dependency array) and never updated it again - a
    # chart fed new data after the first render silently kept showing
    # stale numbers forever. Pinning the fixed dependency array as a
    # regression guard.
    chart_source = _read("components", "ChartCanvas.jsx")
    assert "[type, data, options]" in chart_source


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
