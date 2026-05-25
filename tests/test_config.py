from email_agent.config import Settings, load_behavior


def test_settings_read_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    monkeypatch.setenv("GROQ_API_KEY", "sk-test")
    monkeypatch.setenv("DRY_RUN", "false")
    s = Settings()
    assert s.database_url.endswith("/db")
    assert s.groq_api_key == "sk-test"
    assert s.dry_run is False
    assert s.triage_model  # has a default


def test_load_behavior_reads_yaml(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("persona:\n  name: Tk\nprefilter:\n  deny_sender_substrings: [no-reply]\n")
    behavior = load_behavior(cfg)
    assert behavior["persona"]["name"] == "Tk"
    assert "no-reply" in behavior["prefilter"]["deny_sender_substrings"]
