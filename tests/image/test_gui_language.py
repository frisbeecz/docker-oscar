"""Selected Qt rows can disappear from OCR; still require the exact US option."""
from types import SimpleNamespace

import pytest

from ci import gui


# Actual Tesseract5.5.4/locked English data output from both CI language
# screenshots: UK is readable at y132, selected US at y154 is absent entirely.
# Only these two word rows are needed to reproduce the failing input.
HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
UK = ("5\t1\t12\t1\t1\t1\t243\t132\t52\t16\t96.448051\tEnglish\n"
      "5\t1\t12\t1\t1\t2\t301\t132\t30\t15\t95.534195\t(UK)\n")
# External OCR response after deselecting US: modeled, not a native GUI receipt.
US = ("5\t1\t13\t1\t1\t1\t243\t154\t52\t16\t96\tEnglish\n"
      "5\t1\t13\t1\t1\t2\t301\t154\t30\t15\t95\t(US)\n")


class LanguagePage:
    """External Qt input boundary: one click selects, double click commits."""
    def __init__(self, *, highlighted=True, missing_us=False, missing_uk=False):
        self.highlighted = highlighted
        self.missing_us = missing_us
        self.missing_uk = missing_uk
        self.committed = None
        self.mouse = SimpleNamespace(click=self.click, dblclick=self.dblclick)

    def click(self, x, y):
        assert (x, y) == (287, 140), "deselect using the visible UK label"
        self.highlighted = False

    def dblclick(self, x, y):
        assert (x, y) == (287, 162), "commit only the OCR-located US label"
        self.committed = "en_US"

    def wait_for_timeout(self, milliseconds):
        pass  # No external GUI in the unit suite.

    def words(self):
        return gui.parse_tsv(HEADER + ("" if self.missing_uk else UK)
                             + (US if not self.highlighted and not self.missing_us else ""))


def desktop_for(page, tmp_path, monkeypatch):
    desktop = gui.Desktop(page, tmp_path)
    monkeypatch.setattr(desktop, "capture", lambda checkpoint: page.words())
    return desktop


def test_selected_language_is_deselected_then_visibly_confirmed(tmp_path, monkeypatch):
    page = LanguagePage()
    desktop = desktop_for(page, tmp_path, monkeypatch)
    with pytest.raises(LookupError):
        gui.locate(page.words(), "English (US)")
    gui.select_language(desktop, timeout=0)
    assert page.committed == "en_US"
    assert desktop.checkpoints == ["English (UK)", "English (US)"]


def test_readable_us_option_needs_no_intermediate_selection(tmp_path, monkeypatch):
    page = LanguagePage(highlighted=False, missing_uk=True)
    desktop = desktop_for(page, tmp_path, monkeypatch)
    gui.select_language(desktop, timeout=0)
    assert page.committed == "en_US"
    assert desktop.checkpoints == ["English (US)"]


@pytest.mark.parametrize("options,missing", [
    ({"missing_us": True}, "English \\(US\\)"),
    ({"missing_uk": True}, "English \\(UK\\)"),
])
def test_missing_option_still_fails_without_committing(tmp_path, monkeypatch, options, missing):
    page = LanguagePage(**options)
    desktop = desktop_for(page, tmp_path, monkeypatch)
    with pytest.raises(gui.GUIFailure, match=missing):
        gui.select_language(desktop, timeout=0)
    assert page.committed is None


def test_create_flow_uses_visible_language_selection(tmp_path, monkeypatch):
    page = LanguagePage()
    desktop = desktop_for(page, tmp_path, monkeypatch)
    class StartupReached(Exception):
        pass
    def capture(checkpoint):
        if checkpoint == "startup":
            assert page.committed == "en_US"
            raise StartupReached
        return page.words()
    monkeypatch.setattr(desktop, "capture", capture)
    monkeypatch.setattr(gui, "Desktop", lambda *args: desktop)
    # Make the old missing-US wait fail immediately, not after 60 seconds.
    times = iter([0, 61])
    monkeypatch.setattr(gui.time, "monotonic", lambda: next(times, 122))
    with pytest.raises(StartupReached):
        gui.exercise(page, "create", "ci-synthetic", tmp_path)
