#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    ".gitignore",
    "prompt/SYSTEM_PROMPT.md",
    "prompt/COMPACT_PROMPT.md",
    "prompt/NEGATIVE_PROMPT.md",
    "docs/01_CORE.md",
    "docs/02_SEARCH.md",
    "docs/03_ANALYSIS.md",
    "docs/04_OUTPUT.md",
    "docs/05_EXAMPLES.md",
    "docs/06_TOOL_CONTRACTS.md",
    "docs/07_SOURCE_POLICY.md",
    "docs/08_ERROR_HANDLING.md",
    "docs/09_OUTPUT_SCHEMA.md",
    "docs/10_SECURITY.md",
    "docs/11_SCORING_GATES.md",
    "templates/comparison-table.md",
    "templates/scoring.md",
    "templates/review-summary.md",
    "templates/recommendation.md",
    "schemas/example-output.json",
    "evals/rubric.md",
]

FORMULA = (
    "S = 0,22A + 0,18V + 0,16R + 0,14P + "
    "0,12D + 0,10G + 0,08C − F"
)

FORMULA_FILES = [
    "README.md",
    "prompt/SYSTEM_PROMPT.md",
    "prompt/COMPACT_PROMPT.md",
    "docs/03_ANALYSIS.md",
    "templates/scoring.md",
]

FORBIDDEN_PATTERNS = {
    r"\bTODO\b": "TODO",
    r"\bTBD\b": "TBD",
    r"lorem ipsum": "Lorem ipsum",
    r"заполнить позднее": "обещание заполнить позднее",
    r"будет добавлено позднее": "обещание будущего наполнения",
}

IGNORED_LINK_TARGETS = {
    "прямая-ссылка",
    "https://...",
}


class ValidationError(Exception):
    pass


def markdown_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*.md")
        if ".git" not in path.parts
    ]


def validate_required_files() -> list[str]:
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"Отсутствует обязательный файл: {relative}")
        elif not path.read_text(encoding="utf-8").strip():
            errors.append(f"Пустой файл: {relative}")

    return errors


def validate_all_files_nonempty() -> list[str]:
    errors: list[str] = []

    checked_suffixes = {".md", ".json", ".yml", ".yaml", ".py"}

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        if path.suffix.lower() not in checked_suffixes:
            continue
        if path.stat().st_size == 0:
            errors.append(
                f"Пустой файл: {path.relative_to(ROOT)}"
            )

    return errors


def validate_forbidden_markers() -> list[str]:
    errors: list[str] = []

    for path in markdown_files():
        text = path.read_text(encoding="utf-8")
        for pattern, label in FORBIDDEN_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                errors.append(
                    f"{path.relative_to(ROOT)}: найден {label}"
                )

    return errors


def validate_links() -> list[str]:
    errors: list[str] = []
    link_pattern = re.compile(
        r"(?<!!)\[[^\]]+\]\(([^)]+)\)"
    )

    for path in markdown_files():
        text = path.read_text(encoding="utf-8")

        for raw_target in link_pattern.findall(text):
            target = raw_target.strip()

            if not target:
                continue

            target_without_anchor = target.split("#", 1)[0]

            if not target_without_anchor:
                continue

            if target_without_anchor.startswith(
                ("http://", "https://", "mailto:")
            ):
                continue

            if target_without_anchor in IGNORED_LINK_TARGETS:
                continue

            resolved = (
                path.parent / target_without_anchor
            ).resolve()

            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                errors.append(
                    f"{path.relative_to(ROOT)}: ссылка выходит "
                    f"за пределы репозитория: {target}"
                )
                continue

            if not resolved.exists():
                errors.append(
                    f"{path.relative_to(ROOT)}: "
                    f"несуществующая ссылка: {target}"
                )

    return errors


def validate_formula() -> list[str]:
    errors: list[str] = []

    for relative in FORMULA_FILES:
        path = ROOT / relative
        if not path.exists():
            continue

        text = path.read_text(encoding="utf-8")
        if FORMULA not in text:
            errors.append(
                f"{relative}: отсутствует единая формула"
            )

    weights = [0.22, 0.18, 0.16, 0.14, 0.12, 0.10, 0.08]
    if abs(sum(weights) - 1.0) > 1e-12:
        errors.append("Сумма положительных весов не равна 1.0")

    return errors


def validate_top_five_template() -> list[str]:
    path = ROOT / "templates/comparison-table.md"

    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    rows = re.findall(
        r"^\|\s*([1-5])\s*\|",
        text,
        re.MULTILINE,
    )

    if rows != ["1", "2", "3", "4", "5"]:
        return [
            "Шаблон comparison-table.md должен содержать "
            "строки 1–5"
        ]

    return []


def validate_json() -> list[str]:
    path = ROOT / "schemas/example-output.json"

    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"Некорректный JSON: {error}"]

    required = {
        "schema_version",
        "query",
        "checked_at",
        "result_status",
        "offers",
        "alternatives",
        "unconfirmed_fields",
        "warnings",
    }

    missing = required - set(data)
    if missing:
        return [
            "В JSON отсутствуют поля: "
            + ", ".join(sorted(missing))
        ]

    return []


def validate_no_local_agent_directories() -> list[str]:
    errors: list[str] = []

    for name in [".omo", ".opencode"]:
        if (ROOT / name).exists():
            errors.append(
                f"Локальный служебный каталог не удалён: {name}"
            )

    return errors


def main() -> int:
    checks = [
        validate_required_files,
        validate_all_files_nonempty,
        validate_forbidden_markers,
        validate_links,
        validate_formula,
        validate_top_five_template,
        validate_json,
        validate_no_local_agent_directories,
    ]

    errors: list[str] = []

    for check in checks:
        errors.extend(check())

    if errors:
        print("Проверка не пройдена:\n")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Все проверки пройдены.")
    print(f"Проверено Markdown-файлов: {len(markdown_files())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
