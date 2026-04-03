"""布局引擎：Slot 定义、Region 声明、Rect 计算。"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class Slot(Enum):
    TOP = "top"
    LEFT = "left"
    RIGHT_TOP = "right-top"
    RIGHT_BOT = "right-bot"
    BOTTOM = "bottom"


@dataclass
class Region:
    id: str
    slot: Slot
    min_height: int = 1
    weight: int = 100
    priority: int = 50


@dataclass
class Rect:
    row: int
    col: int
    height: int
    width: int


class LayoutEngine:
    """收集 Region 声明，计算屏幕坐标。"""

    def compute(self, regions: List[Region], screen_h: int, screen_w: int) -> Dict[str, Rect]:
        by_slot: Dict[Slot, List[Region]] = {}
        for r in regions:
            by_slot.setdefault(r.slot, []).append(r)

        result: Dict[str, Rect] = {}

        # TOP: row 0, 全宽, 固定 1 行
        top_regions = by_slot.get(Slot.TOP, [])
        if top_regions:
            winner = max(top_regions, key=lambda r: r.priority)
            result[winner.id] = Rect(row=0, col=0, height=1, width=screen_w)

        # BOTTOM: 最后 3 行, 全宽
        bottom_start = screen_h - 3
        bottom_regions = sorted(by_slot.get(Slot.BOTTOM, []), key=lambda r: -r.priority)
        total_weight = sum(r.weight for r in bottom_regions) or 1
        avail_h = 3
        row = bottom_start
        for i, r in enumerate(bottom_regions):
            if i < len(bottom_regions) - 1:
                h = max(1, avail_h * r.weight // total_weight)
            else:
                h = avail_h
            result[r.id] = Rect(row=row, col=0, height=h, width=screen_w)
            row += h
            avail_h -= h

        # 左右分割
        left_w = max(30, screen_w * 2 // 5)
        right_w = screen_w - left_w - 1
        content_start = 1
        content_end = bottom_start

        # LEFT: 左侧面板
        left_regions = sorted(by_slot.get(Slot.LEFT, []), key=lambda r: -r.priority)
        left_h = content_end - content_start
        total_lw = sum(r.weight for r in left_regions) or 1
        avail_lh = left_h
        row = content_start
        for i, r in enumerate(left_regions):
            if avail_lh < r.min_height:
                break
            if i < len(left_regions) - 1:
                h = max(r.min_height, left_h * r.weight // total_lw)
            else:
                h = avail_lh
            result[r.id] = Rect(row=row, col=0, height=h, width=left_w)
            row += h
            avail_lh -= h

        # RIGHT: 上下分割 (45%/55%)
        right_total_h = content_end - content_start
        right_split = int(right_total_h * 0.45)

        # RIGHT_TOP
        rt_regions = sorted(by_slot.get(Slot.RIGHT_TOP, []), key=lambda r: -r.priority)
        rt_winner = rt_regions[0] if rt_regions else None
        if rt_winner:
            result[rt_winner.id] = Rect(
                row=content_start, col=left_w + 1,
                height=right_split, width=right_w
            )

        # RIGHT_BOT
        rb_regions = sorted(by_slot.get(Slot.RIGHT_BOT, []), key=lambda r: -r.priority)
        rb_winner = rb_regions[0] if rb_regions else None
        if rb_winner:
            result[rb_winner.id] = Rect(
                row=content_start + right_split + 1, col=left_w + 1,
                height=right_total_h - right_split - 1, width=right_w
            )

        return result
