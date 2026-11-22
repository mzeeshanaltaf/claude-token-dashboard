"""CSV writing for `/api/export/*.csv`: stdlib `csv`, streamed row by row.

Two Excel accommodations, both applied to text cells only:
- a cell that starts with `=`, `+`, `-`, `@`, tab or CR gets a leading `'`, so
  Excel shows it as text instead of evaluating it as a formula (CSV injection);
- very long text is cut (with a marker) to fit Excel's 32,767-character cell
  limit, because Excel otherwise spills the rest into extra rows and the row
  count stops matching. Excel's CSV import applies the limit to the *raw*
  field: UTF-16 code units (an emoji is 2) with every `"` escaped as `""`. A
  real 32,766-character prompt with 144 quotes still spilled, so the budget
  also keeps a margin (EXCEL_SAFE_UNITS).
The stream starts with a UTF-8 BOM so Excel detects the encoding.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Any, Iterable, Iterator, Sequence

BOM = "﻿"
EXCEL_CELL_MAX = 32_767
EXCEL_SAFE_UNITS = 32_000  # what a cut cell may cost, marker and formula guard included
_TRUNCATED = " …[truncated]"
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def utf16_len(s: str) -> int:
    """UTF-16 code units (an emoji is 2)."""
    return len(s.encode("utf-16-le")) // 2


def excel_units(s: str) -> int:
    """What a field costs against Excel's cell limit on CSV import: UTF-16
    units, with each `"` counted twice (it is written escaped as `""`)."""
    return utf16_len(s) + s.count('"')


def _fit_excel(value: str) -> str:
    """Cut `value` so it (plus the marker and a possible `'` prefix) fits Excel."""
    budget = EXCEL_SAFE_UNITS - 1  # room for the formula-guard quote
    if excel_units(value) <= budget:
        return value
    budget -= excel_units(_TRUNCATED)
    cut = value[:budget]
    while (over := excel_units(cut) - budget) > 0:
        cut = cut[:-over]  # each code point costs >= 1 unit, so this converges
    return cut + _TRUNCATED


def cell(value: Any) -> Any:
    """One value as a CSV-safe cell."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, str):
        value = _fit_excel(value)
        if value.startswith(_FORMULA_PREFIXES):
            value = "'" + value
        return value
    return value


def csv_lines(columns: Sequence[str], rows: Iterable[dict]) -> Iterator[str]:
    """The BOM + header, then one CSV line per row (each row a dict)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")

    def flush() -> str:
        s = buf.getvalue()
        buf.seek(0)
        buf.truncate()
        return s

    writer.writerow(columns)
    yield BOM + flush()
    for r in rows:
        writer.writerow([cell(r.get(c)) for c in columns])
        yield flush()
