"""발주현황 행 → 시트3 달력 셀 문구 변환 (입출력과 무관한 순수 로직)."""
from __future__ import annotations

import datetime as dt
import re
from collections import OrderedDict
from dataclasses import dataclass

# 품번 접두어 → 구분
CATEGORY_BY_PREFIX = {"MPM": "자재", "CPM": "자재", "MRM": "원료", "CRM": "원료"}
CATEGORY_ORDER = ("원료", "자재")

SHEETS_EPOCH = dt.date(1899, 12, 30)  # 구글 시트/엑셀 날짜 일련번호 기준일


@dataclass
class OrderRow:
    row: int                 # 원본 시트 행 번호 (1부터)
    product: str             # 모품목
    part_no: str             # 품번
    part_name: str           # 품명
    expected: object         # 입고예정일 (원본 값)
    received: object         # 입고일 (원본 값)
    order_date: object = None  # 발주일 (연도 추정용)


@dataclass
class Item:
    row: int
    product: str
    category: str
    part_no: str
    part_name: str
    date: dt.date | None     # 달력에 표시할 날짜
    received: bool


def category_of(part_no: str) -> str | None:
    return CATEGORY_BY_PREFIX.get(str(part_no or "").strip()[:3].upper())


def to_date(value, ref_year: int | None = None, ref_date: dt.date | None = None) -> dt.date | None:
    """날짜 셀 값을 date로 변환. 지원: date/datetime, 일련번호, '2026-09-21', '10/13(화)', '10월 13일'."""
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 20000 < value < 80000:
            return SHEETS_EPOCH + dt.timedelta(days=int(value))
        return None
    s = str(value).strip()
    m = re.match(r"^(\d{4})[-./\s]+(\d{1,2})[-./\s]+(\d{1,2})", s)
    if m:
        return _safe_date(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r"^(\d{1,2})\s*[/.월]\s*(\d{1,2})", s)
    if m:
        month, day = int(m[1]), int(m[2])
        year = ref_year or (ref_date.year if ref_date else dt.date.today().year)
        d = _safe_date(year, month, day)
        # 발주일보다 한참 앞이면 다음 해로 본다 (예: 12월 발주 → 1/5 입고)
        if d and ref_date and (ref_date - d).days > 60:
            d = _safe_date(year + 1, month, day)
        return d
    return None


def _safe_date(y, m, d):
    try:
        return dt.date(y, m, d)
    except ValueError:
        return None


def is_filled(value) -> bool:
    return value is not None and str(value).strip() != ""


def build_items(rows: list[OrderRow], default_year: int) -> list[Item]:
    items = []
    for r in rows:
        cat = category_of(r.part_no)
        product = str(r.product or "").strip()
        if not cat or not product:
            continue
        ref = to_date(r.order_date, default_year)
        date = to_date(r.expected, ref.year if ref else default_year, ref)
        if date is None:  # 입고예정일이 '9월 예정'처럼 날짜가 아니면 입고일로 대체
            date = to_date(r.received, ref.year if ref else default_year, ref)
        items.append(Item(r.row, product, cat, str(r.part_no).strip(),
                          str(r.part_name or "").strip(), date, is_filled(r.received)))
    return items


def build_cell_texts(items: list[Item]) -> "OrderedDict[dt.date, str]":
    """날짜별 셀 문구. 입고현황(a/b)은 모품목+구분 전체 기준."""
    totals: dict[tuple, list[int]] = {}
    for it in items:
        t = totals.setdefault((it.product, it.category), [0, 0])
        t[1] += 1
        if it.received:
            t[0] += 1

    product_order = list(OrderedDict.fromkeys(it.product for it in items))
    by_date: dict[dt.date, dict[tuple, list[int]]] = {}
    for it in items:
        if it.date is None:
            continue
        g = by_date.setdefault(it.date, {}).setdefault((it.product, it.category), [0, 0])
        g[0 if it.received else 1] += 1

    out: "OrderedDict[dt.date, str]" = OrderedDict()
    for date in sorted(by_date):
        groups = by_date[date]
        keys = sorted(groups, key=lambda k: (product_order.index(k[0]), CATEGORY_ORDER.index(k[1])))
        blocks = []
        for product, cat in keys:
            done, pending = groups[(product, cat)]
            parts = []
            if done:
                parts.append(f"{done}종 입고완료")
            if pending:
                parts.append(f"{pending}종 입고예정")
            a, b = totals[(product, cat)]
            blocks.append(f"{product}-{cat} {' / '.join(parts)}\n입고현황 ({a}/{b})")
        out[date] = "\n\n".join(blocks)
    return out


def unplaced(items: list[Item]) -> list[Item]:
    return [it for it in items if it.date is None]
