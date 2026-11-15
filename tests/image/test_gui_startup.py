"""One synthetic profile exercises packaging persistence, not CPAP analysis."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from ci import gui


# Recorded heading/button TSV rows from run43763743296's two synthetic startup
# screenshots. Subsequent Qt/OCR responses are a model, not native CI evidence.
FIXTURES = Path(__file__).with_name("fixtures")


def words(phrase):
    return [{"text": word, "left": 100 + i * 80, "top": 100,
             "width": 70, "height": 20, "line": ("1", "1", "1", "1")}
            for i, word in enumerate(phrase.split())]


class StartupPage:
    """Only the external Qt/OCR boundary is modeled; controller stays real."""
    def __init__(self, migration):
        self.migration = migration
        self.state = "language"
        self.clicks = []
        self.saved = False
        self.typed = False
        self.mouse = SimpleNamespace(click=self.click, dblclick=self.double_click)
        self.keyboard = SimpleNamespace(press=lambda key: None, type=self.type)

    def capture(self, checkpoint):
        if self.state == "migration":
            return self.migration
        return words({"language": "English (US)", "welcome": "I agree", "name": "Profile Name",
                      "finish": "Finish", "save": "Accept and save this information? Yes",
                      "ready": "OSCAR ci-synthetic"}[self.state])

    def double_click(self, x, y):
        assert self.state == "language"
        self.state = "migration" if self.migration else "welcome"

    def click(self, x, y):
        self.clicks.append((self.state, x, y))
        if self.state == "migration":
            assert (x, y) == gui.locate(self.migration, "Skip migration")
            self.state = "welcome"
        elif self.state == "welcome":
            self.state = "name" if x < 300 else self.state
        elif self.state == "name":
            if x == 400 and self.typed:
                self.state = "finish"
        elif self.state == "finish":
            self.state = "save"
        elif self.state == "save":
            assert (x, y) == gui.locate(self.capture("save"), "Yes")
            self.saved = True
            self.state = "ready"

    def type(self, text):
        assert self.state == "name" and text == "ci-synthetic"
        self.typed = True

    def wait_for_timeout(self, milliseconds):
        pass


@pytest.mark.parametrize("arch", ["amd64", "arm64", None])
def test_create_profile_handles_clean_install_without_migrating(arch, monkeypatch, tmp_path):
    migration = gui.parse_tsv((FIXTURES / f"startup-migration-{arch}.tsv").read_text()) if arch else []
    page = StartupPage(migration)
    desktop = gui.Desktop(page, tmp_path)
    monkeypatch.setattr(desktop, "capture", page.capture)
    monkeypatch.setattr(gui, "Desktop", lambda *args: desktop)
    original_wait = desktop.wait

    def wait(phrase, **kwargs):
        if phrase == "Next":
            return (400, 110)
        return original_wait(phrase, **kwargs)

    monkeypatch.setattr(desktop, "wait", wait)
    # An unhandled prompt fails immediately rather than consuming a real minute.
    tick = iter(range(0, 10000, 61))
    monkeypatch.setattr(gui.time, "monotonic", lambda: next(tick))
    result = gui.exercise(page, "create", "ci-synthetic", tmp_path)
    assert page.saved and result["visibleProfile"]
    assert sum(state == "migration" for state, *_ in page.clicks) == bool(arch)
    assert sum(state == "save" for state, *_ in page.clicks) == 1


def test_migration_screen_without_skip_does_not_click_migrate(monkeypatch, tmp_path):
    page = StartupPage(words("OSCAR 1.x Data Migration Migrate Cancel"))
    desktop = gui.Desktop(page, tmp_path)
    monkeypatch.setattr(desktop, "capture", page.capture)
    monkeypatch.setattr(gui, "Desktop", lambda *args: desktop)
    tick = iter(range(0, 10000, 61))
    monkeypatch.setattr(gui.time, "monotonic", lambda: next(tick))
    with pytest.raises(gui.GUIFailure, match="welcome wizard|profile selector"):
        gui.exercise(page, "create", "ci-synthetic", tmp_path)
    assert not page.saved and page.clicks == []


def test_repeated_migration_prompt_is_not_clicked_forever(monkeypatch, tmp_path):
    migration = gui.parse_tsv((FIXTURES / "startup-migration-amd64.tsv").read_text())
    page = StartupPage(migration)
    desktop = gui.Desktop(page, tmp_path)
    monkeypatch.setattr(desktop, "capture", page.capture)
    monkeypatch.setattr(gui, "Desktop", lambda *args: desktop)
    clicks = []

    def click(x, y):
        clicks.append((x, y))
        assert len(clicks) == 1, "do not repeatedly click an unhandled dialog"

    monkeypatch.setattr(page.mouse, "click", click)
    with pytest.raises(gui.GUIFailure, match="repeated migration"):
        gui.exercise(page, "create", "ci-synthetic", tmp_path)
    assert clicks == [gui.locate(migration, "Skip migration")]


def test_verify_never_skips_migration(monkeypatch, tmp_path):
    migration = gui.parse_tsv((FIXTURES / "startup-migration-amd64.tsv").read_text())
    page = StartupPage(migration)
    page.state = "migration"
    desktop = gui.Desktop(page, tmp_path)
    monkeypatch.setattr(desktop, "capture", page.capture)
    monkeypatch.setattr(gui, "Desktop", lambda *args: desktop)
    tick = iter(range(0, 10000, 61))
    monkeypatch.setattr(gui.time, "monotonic", lambda: next(tick))
    with pytest.raises(gui.GUIFailure, match="ci-synthetic"):
        gui.exercise(page, "verify", "ci-synthetic", tmp_path)
    assert page.clicks == []
