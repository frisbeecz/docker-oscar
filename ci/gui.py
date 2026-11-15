"""Screenshot/OCR input for the pinned English Qt GUI, never DB/config fixtures.

SPDX-License-Identifier: Apache-2.0
"""
from __future__ import annotations

import csv
import io
from pathlib import Path
import re
import subprocess
import time


class GUIFailure(AssertionError):
    """An observable GUI checkpoint failed (not an infrastructure substitute)."""


def parse_tsv(text: str) -> list[dict]:
    return [{"text": row["text"], "left": int(row["left"]), "top": int(row["top"]),
             "width": int(row["width"]), "height": int(row["height"]),
             "line": tuple(row[k] for k in ["page_num", "block_num", "par_num", "line_num"])}
            for row in csv.DictReader(io.StringIO(text), delimiter="\t")
            if row.get("text", "").strip() and float(row.get("conf", -1)) >= 20]


def normalized(text):
    return re.sub(r"[^a-z0-9-]", "", text.lower())


def locate(words: list[dict], phrase: str) -> tuple[float, float]:
    wanted = [normalized(w) for w in phrase.split()]
    for i in range(len(words) - len(wanted) + 1):
        group = words[i:i + len(wanted)]
        if ([normalized(w["text"]) for w in group] == wanted
                and len({w["line"] for w in group}) == 1):
            left = min(w["left"] for w in group)
            right = max(w["left"] + w["width"] for w in group)
            top = min(w["top"] for w in group)
            bottom = max(w["top"] + w["height"] for w in group)
            return ((left + right) / 2, (top + bottom) / 2)
    raise LookupError(f"GUI text not visible: {phrase}")


class Desktop:
    def __init__(self, page, artifacts: Path):
        self.page = page
        self.artifacts = Path(artifacts)
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.sequence = 0
        self.checkpoints = []

    def capture(self, checkpoint):
        self.sequence += 1
        name = f"{self.sequence:03d}-{checkpoint}"
        png = self.artifacts / (name + ".png")
        self.page.screenshot(path=str(png))
        result = subprocess.run(["tesseract", str(png), "stdout", "-l", "eng", "--psm", "11", "tsv"],
                                check=True, capture_output=True, text=True, timeout=30)
        (self.artifacts / (name + ".tsv")).write_text(result.stdout)
        return parse_tsv(result.stdout)

    def wait(self, phrase, *, timeout=60, absent=None):
        end = time.monotonic() + timeout
        while True:
            words = self.capture(re.sub(r"[^a-z0-9-]", "-", phrase.lower())[:48])
            if absent:
                try:
                    locate(words, absent)
                except LookupError:
                    pass
                else:
                    raise GUIFailure(f"unexpected repeated GUI prompt: {absent}")
            try:
                location = locate(words, phrase)
                self.checkpoints.append(phrase)
                return location
            except LookupError:
                if time.monotonic() >= end:
                    raise GUIFailure(f"missing OSCAR GUI checkpoint: {phrase}") from None
                self.page.wait_for_timeout(750)

    def click(self, phrase, *, double=False, timeout=60):
        x, y = self.wait(phrase, timeout=timeout)
        if double:
            self.page.mouse.dblclick(x, y)
        else:
            self.page.mouse.click(x, y)
        self.page.wait_for_timeout(500)


def select_language(desktop: Desktop, *, timeout=60):
    # Qt preselects US. Its white-on-blue text disappears from Tesseract's
    # binarized image even while adjacent black-on-white labels are readable.
    # A single click changes only the selection (translation.cpp); double click
    # commits it. Deselect first, then require a fresh exact US OCR match.
    words = desktop.capture("language-selection")
    try:
        locate(words, "English (US)")
    except LookupError:
        desktop.click("English (UK)", timeout=timeout)
    desktop.click("English (US)", double=True, timeout=timeout)


def exercise(page, phase: str, profile: str, artifacts: Path) -> dict:
    if phase not in {"create", "verify"}:
        raise ValueError("phase must be create or verify")
    if profile != "ci-synthetic":
        raise ValueError("only the synthetic ci-synthetic profile is permitted")
    desktop = Desktop(page, artifacts)
    if phase == "create":
        select_language(desktop)
        # On an empty database upstream opens its welcome wizard automatically.
        # On the selector, the same New Profile action starts at the name page.
        end = time.monotonic() + 60
        migration_skipped = False
        while True:
            words = desktop.capture("startup")
            # A new v2 database offers legacy migration even with no old data.
            # This helper only creates a synthetic CI profile: never migrate or
            # cancel/delete a database, and never apply this to verify/restart.
            try:
                locate(words, "OSCAR 1.x Data Migration")
                x, y = locate(words, "Skip migration")
            except LookupError:
                pass
            else:
                if migration_skipped:
                    raise GUIFailure("unexpected repeated migration prompt")
                page.mouse.click(x, y)
                migration_skipped = True
                page.wait_for_timeout(500)
                continue
            # Upstream firstRunMessage() opens About before the selector.
            if any(normalized(w["text"]) == "credits" for w in words):
                try:
                    x, y = locate(words, "Close")
                except LookupError:
                    pass
                else:
                    page.mouse.click(x, y)
                    page.wait_for_timeout(500)
                    continue
            try:
                x, y = locate(words, "I agree")
            except LookupError:
                try:
                    x, y = locate(words, "New Profile")
                except LookupError:
                    if time.monotonic() >= end:
                        raise GUIFailure("neither OSCAR welcome wizard nor profile selector appeared")
                    page.wait_for_timeout(750)
                    continue
                page.mouse.click(x, y)
            else:
                page.mouse.click(x, y)
                desktop.click("Next")
            break
        # The label is left of its Qt line edit; click the label then Tab is not
        # reliable without a buddy. The actual field is to its right on this form.
        x, y = desktop.wait("Profile Name")
        page.mouse.click(x + 200, y)
        page.keyboard.press("Control+a")
        page.keyboard.type(profile)
        desktop.click("Next")
        # Personal, contact, CPAP, doctor, and final pages contain optional
        # synthetic defaults only. Do not enter any real identity/health data.
        for _ in range(8):
            words = desktop.capture("wizard")
            try:
                x, y = locate(words, "Finish")
            except LookupError:
                desktop.click("Next")
            else:
                page.mouse.click(x, y)
                # Finish opens an explicit save confirmation (newprofile.cpp).
                # Do not accept an unrelated Yes button or write the DB for it.
                desktop.wait("Accept and save this information?")
                desktop.click("Yes")
                break
        else:
            raise GUIFailure("profile wizard did not reach Finish")
    # Both auto-open and the explicit profile selector are supported, but the
    # profile must visibly exist; absence is never made into a new fixture.
    desktop.wait(profile, absent="Language / Taal")
    words = desktop.capture("profile-open")
    try:
        x, y = locate(words, "Open Profile")
    except LookupError:
        pass
    else:
        desktop.click(profile)
        page.mouse.click(x, y)
    desktop.wait("OSCAR", absent="Language / Taal")
    desktop.wait(profile)
    desktop.capture("profile-ready")
    return {"phase": phase, "profile": profile, "visibleProfile": True,
            "languageSelectedViaGui": phase == "create", "noLanguageReprompt": phase == "verify",
            "checkpoints": desktop.checkpoints}


def import_dialog(page, artifacts: Path) -> dict:
    desktop = Desktop(page, artifacts)
    # The pinned mainwindow action opens the import directory chooser.
    desktop.click("Import")
    desktop.wait("Find your CPAP data card", timeout=45)
    page.keyboard.press("Control+l")
    page.keyboard.type("/config/SDCARD")
    page.keyboard.press("Enter")
    desktop.capture("sdcard-import-dialog")
    page.keyboard.press("Escape")
    return {"importDialog": True}


def storage_failure(page, artifacts: Path) -> dict:
    desktop = Desktop(page, artifacts)
    desktop.wait("Database Error", timeout=60)
    desktop.capture("read-only-data-error")
    return {"visibleStorageFailure": True}


def close_application(page, artifacts: Path):
    desktop = Desktop(page, artifacts)
    desktop.click("File")
    desktop.click("Exit")
    # If upstream asks about shutdown, accept only its explicit Yes button.
    page.wait_for_timeout(500)
    words = desktop.capture("closed-or-confirmation")
    try:
        x, y = locate(words, "Yes")
    except LookupError:
        return
    page.mouse.click(x, y)
