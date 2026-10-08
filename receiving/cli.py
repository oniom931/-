"""사용법
  python -m receiving.cli show  --product 리프          # 채팅용 정리 (시트 변경 없음)
  python -m receiving.cli apply --product 리프          # 시트3에 입력
  python -m receiving.cli apply                         # 모든 모품목 입력
  python -m receiving.cli today [--date 2026-10-08]     # 그날 입고 예정/완료 품목
옵션
  --dry-run                     apply 시 실제로 쓰지 않고 바뀔 칸만 출력
  --order-xlsx / --calendar-xlsx  구글 API 대신 xlsx 파일로 실행 (테스트용, 쓰기 불가)
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from . import core, sources

KST = dt.timezone(dt.timedelta(hours=9))


def _today() -> dt.date:
    return dt.datetime.now(KST).date()


def _load(args):
    client = None
    if args.order_xlsx:
        orders = sources.read_orders_xlsx(args.order_xlsx)
    else:
        client = sources.SheetsClient()
        orders = sources.read_orders_api(client)
    items = core.build_items(orders, _today().year)
    return client, items


def _select(items, products):
    if not products:
        return items
    picked = [it for it in items if it.product in products]
    missing = set(products) - {it.product for it in picked}
    for p in sorted(missing):
        near = sorted({it.product for it in items if p in it.product or it.product in p})
        print(f"[!] 모품목 '{p}' 을(를) 찾지 못했습니다." + (f" 비슷한 이름: {', '.join(near)}" if near else ""))
    return picked


def _warnings(items):
    lines = []
    for it in core.shortage_warnings(items):
        lines.append(f"[부족 양수·비고 없음] {it.product} {it.part_no} {it.part_name} (부족 {it.shortage:+,.0f}, 행 {it.row})")
    for it in core.unplaced(items):
        lines.append(f"[날짜 없음] {it.product} {it.part_no} {it.part_name} (행 {it.row}) - 입고예정일/입고일이 비어 있거나 날짜가 아님")
    return lines


def cmd_show(args):
    _, items = _load(args)
    items = _select(items, args.product)
    for date, blocks in core.build_cell_blocks(items).items():
        for _, text in blocks:
            print(text + "\n")
    for line in _warnings(items):
        print(line)


def cmd_today(args):
    _, items = _load(args)
    day = dt.date.fromisoformat(args.date) if args.date else _today()
    items = _select(items, args.product)
    todays = [it for it in items if it.date == day]
    if not todays:
        print(f"{day.month}/{day.day} 입고 예정/완료 품목 없음")
        return
    blocks = core.build_cell_blocks([it for it in items if it.product in {t.product for t in todays}])
    for _, text in blocks.get(day, []):
        print(text)
    print()
    for it in todays:
        print(f"- {it.product} | {it.part_no} {it.part_name} | {'입고완료' if it.received else '입고예정'}")


def cmd_apply(args):
    client, items = _load(args)
    items = _select(items, args.product)
    if args.product and not items:
        return 1
    if args.calendar_xlsx:
        cal = sources.read_calendar_xlsx(args.calendar_xlsx)
    elif client:
        cal = sources.read_calendar_api(client)
    else:
        print("xlsx 모드에서는 --calendar-xlsx 가 필요합니다.")
        return 1

    products = set(args.product) if args.product else None
    blocks_by_cell: dict[str, list[str]] = {}
    outside = []
    for date, blocks in core.build_cell_blocks(items).items():
        addr = cal.cell_of(date)
        if addr is None:
            outside.extend(text for _, text in blocks)
            continue
        blocks_by_cell.setdefault(addr, []).extend(text for _, text in blocks)

    # 대상 모품목의 자동 블록이 남아 있는 칸(날짜가 바뀐 경우)도 정리 대상에 포함
    for addr, text in cal.values.items():
        if addr not in blocks_by_cell and any(
                core.AUTO_BLOCK_RE.match(b.strip()) and (products is None or core.AUTO_BLOCK_RE.match(b.strip())["product"] in products)
                for b in text.split("\n\n")):
            blocks_by_cell[addr] = []

    changes = {}
    for addr, new_blocks in blocks_by_cell.items():
        old = cal.values.get(addr, "")
        new = core.merge_cell(old, new_blocks, products)
        if new.strip() != old.strip():
            changes[addr] = new

    def sort_key(a):
        return (int(a[1:]), a[0])

    if not changes:
        print("변경할 칸이 없습니다 (이미 최신).")
    for addr in sorted(changes, key=sort_key):
        print(f"── {addr}\n{changes[addr]}\n")
    for text in outside:
        print(f"[달력 범위 밖이라 건너뜀] {text.splitlines()[0]}")
    for line in _warnings(items):
        print(line)

    if changes and not args.dry_run:
        if client is None:
            print("xlsx 모드에서는 시트에 쓸 수 없습니다 (--dry-run 결과만 표시).")
            return 0
        client.write_cells(sources.SCHEDULE_SPREADSHEET_ID, sources.SCHEDULE_SHEET, changes)
        print(f"시트3에 {len(changes)}칸 입력 완료: {', '.join(sorted(changes, key=sort_key))}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="receiving", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("show", "apply", "today"):
        s = sub.add_parser(name)
        s.add_argument("--product", action="append", help="모품목 이름 (여러 번 지정 가능)")
        s.add_argument("--order-xlsx")
        s.add_argument("--calendar-xlsx")
        s.add_argument("--dry-run", action="store_true")
        s.add_argument("--date")
    args = p.parse_args(argv)
    return {"show": cmd_show, "apply": cmd_apply, "today": cmd_today}[args.cmd](args) or 0


if __name__ == "__main__":
    sys.exit(main())
