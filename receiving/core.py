"""발주현황 행 → 시트3 달력 셀 문구 변환 (입출력과 무관한 순수 로직)."""
from __future__ import annotations

import datetime as dt
import re
from collections import OrderedDict
from dataclasses import dataclass

# 품번 접두어 → 구분
CATEGORY_BY_PREFIX = {"MPM": "자재", "CPM": "자재", "MRM": "원료", "CRM": "원료"}
CATEGORY_ORDER = ("원료", "자재")

# 비고에 이 문구가 있으면 입고현황 전체수량(b)에서 제외
EXCLUDE_REMARKS = ("성적서 확보용", "성적서확보용", "안전재고")

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
    shortage: object = None    # 부족
    remark: object = None      # 비고


@dataclass
class Item:
    row: int
    product: str
    category: str
    part_no: str
    part_name: str
    date: dt.date | None     # 달력에 표시할 날짜
    received: bool
    shortage: float | None = None
    exclude_tag: str | None = None  # '안전재고' / '성적서 확보용' → 전체수량 제외


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


def exclude_tag_of(remark) -> str | None:
    text = str(remark or "")
    for word in EXCLUDE_REMARKS:
        if word in text:
            return "성적서 확보용" if word.startswith("성적서") else word
    return None


def to_number(value) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


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
                          str(r.part_name or "").strip(), date, is_filled(r.received),
                          to_number(r.shortage), exclude_tag_of(r.remark)))
    return items


def build_cell_texts(items: list[Item]) -> "OrderedDict[dt.date, str]":
    """날짜별 셀 문구. 입고현황(a/b)은 모품목+구분 전체 기준."""
    totals: dict[tuple, list[int]] = {}
    for it in items:
        t = totals.setdefault((it.product, it.category), [0, 0])
        if it.exclude_tag:
            continue
        t[1] += 1
        if it.received:
            t[0] += 1

    product_order = list(OrderedDict.fromkeys(it.product for it in items))
    by_date: dict[dt.date, dict[tuple, list[int]]] = {}
    for it in items:
        if it.date is None:
            continue
        key = (it.product, it.category, it.exclude_tag or "")
        g = by_date.setdefault(it.date, {}).setdefault(key, [0, 0])
        g[0 if it.received else 1] += 1

    out: "OrderedDict[dt.date, str]" = OrderedDict()
    for date in sorted(by_date):
        groups = by_date[date]
        keys = sorted(groups, key=lambda k: (product_order.index(k[0]), CATEGORY_ORDER.index(k[1]), k[2]))
        blocks = []
        for product, cat, tag in keys:
            done, pending = groups[(product, cat, tag)]
            parts = []
            if done:
                parts.append(f"{done}종 입고완료")
            if pending:
                parts.append(f"{pending}종 입고예정")
            head = f"{product}-{cat} {' / '.join(parts)}"
            if tag:  # 제외 품목은 입고현황 없이 표시
                blocks.append(f"{head}\n({tag})")
            else:
                a, b = totals[(product, cat)]
                blocks.append(f"{head}\n입고현황 ({a}/{b})")
        out[date] = "\n\n".join(blocks)
    return out


def unplaced(items: list[Item]) -> list[Item]:
    return [it for it in items if it.date is None]


def shortage_warnings(items: list[Item]) -> list[Item]:
    """부족이 양수인데 비고에 안전재고/성적서 확보용 문구가 없는 품목."""
    return [it for it in items if it.shortage is not None and it.shortage > 0 and not it.exclude_tag]
