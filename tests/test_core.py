import datetime as dt

from receiving.core import OrderRow, build_cell_blocks, build_items, merge_cell, shortage_warnings


def rows():
    return [
        OrderRow(1, "리파인", "CRM-1006", "DPG", "9/30(수)", dt.datetime(2026, 9, 30), dt.datetime(2026, 9, 20)),
        OrderRow(2, "리파인", "CRM-1013", "ELOL", "9/30(수)", dt.datetime(2026, 9, 30), dt.datetime(2026, 9, 20)),
        OrderRow(3, "리파인", "CRM-1004", "BG", "10/2(금)", dt.datetime(2026, 10, 2), dt.datetime(2026, 9, 20)),
        OrderRow(4, "리파인", "CRM-6010", "B12", "10/2(금)", dt.datetime(2026, 10, 2), None, 58, "성적서 확보용"),
        OrderRow(5, "리파인", "CRM-6015", "NIA", "10/6(화)", None, dt.datetime(2026, 9, 20), -5),
        OrderRow(6, "리파인", "CPM-0019", "캡", "10/20(화)", None, None, 10, None),
        OrderRow(7, "리파인", "XXX-0001", "무시", "10/20(화)", None),
    ]


def texts(items):
    return {d: [t for _, t in b] for d, b in build_cell_blocks(items).items()}


def test_cumulative_count_and_exclusion():
    t = texts(build_items(rows(), 2026))
    assert t[dt.date(2026, 9, 30)] == ["9/30 리파인-원료2종\n입고완료 입고현황(2/4)"]
    assert t[dt.date(2026, 10, 2)] == ["10/2 리파인-원료1종\n입고완료 입고현황(3/4)",
                                       "10/2 리파인-원료1종\n입고완료 (성적서 확보용)"]
    assert t[dt.date(2026, 10, 6)] == ["10/6 리파인-원료1종\n입고예정 입고현황(3/4)"]
    assert t[dt.date(2026, 10, 20)] == ["10/20 리파인-자재1종\n입고예정 입고현황(0/1)"]


def test_received_item_moves_to_received_date():
    r = [OrderRow(1, "A", "MPM-1", "x", "10/13(화)", dt.datetime(2026, 10, 10), dt.datetime(2026, 10, 1))]
    assert list(texts(build_items(r, 2026))) == [dt.date(2026, 10, 10)]


def test_shortage_warning_only_without_remark():
    warn = shortage_warnings(build_items(rows(), 2026))
    assert [w.part_no for w in warn] == ["CPM-0019"]


def test_merge_keeps_manual_text_and_replaces_own_blocks():
    old = "XELAJU 충전\n\n10/13 리프-자재2종\n입고예정 입고현황(0/3)\n\n10/13 리파인-자재2종\n입고예정 입고현황(0/12)"
    new = merge_cell(old, ["10/13 리프-자재2종\n입고완료 입고현황(2/3)"], {"리프"})
    assert new == ("XELAJU 충전\n\n10/13 리파인-자재2종\n입고예정 입고현황(0/12)"
                   "\n\n10/13 리프-자재2종\n입고완료 입고현황(2/3)")
