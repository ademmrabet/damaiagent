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
    chat_source = _read("pages", "Chat.jsx")
    assert "detectedLanguage" in chat_source
    assert "lang-badge" in chat_source
    assert "translationError" in chat_source


def test_chat_page_has_an_explicit_language_picker():
    chat_source = _read("pages", "Chat.jsx")
    assert "<LanguagePicker" in chat_source
    assert "uiLanguage" in chat_source
    assert "answerLanguage" in chat_source

    picker_source = _read("components", "LanguagePicker.jsx")
    assert "LANGUAGE_OPTIONS" in picker_source

    i18n_source = _read("i18n.js")
    for code in ("auto", "en", "fr", "es", "pt", "ar"):
        assert f"value: '{code}'" in i18n_source


def test_api_sends_the_selected_target_language():
    api_source = _read("api.js")
    assert "target_language" in api_source


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
    chart_source = _read("components", "ChartCanvas.jsx")
    assert "[type, data, options]" in chart_source


def test_built_frontend_output_exists():
    if not (STATIC_DIR / "landing.html").exists():
        import pytest

        pytest.skip("frontend not built yet - run `npm run build` in webapp/frontend/")

    for name in ("landing.html", "chat.html", "dashboard.html"):
        assert (STATIC_DIR / name).exists()
    assert (STATIC_DIR / "assets").is_dir()
    assert any((STATIC_DIR / "assets").iterdir())
