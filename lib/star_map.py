"""全息星图渲染引擎：节点飘动、背景效果、流星"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

# 状态对应的显示配置
STATUS_DISPLAY = {
    "start":       {"char": "◇", "color": 6, "pulse": True},   # 蓝色
    "idle":        {"char": "○", "color": 8, "pulse": False},   # 灰色
    "working":     {"char": "◆", "color": 3, "pulse": True},   # 橙色/黄色
    "hitl":        {"char": "⚠", "color": 4, "pulse": True},   # 红色
    "complete":    {"char": "✦", "color": 2, "pulse": False},  # 绿色
    "error":       {"char": "✖", "color": 4, "pulse": True},   # 红色
    "api_error":   {"char": "⛔", "color": 4, "pulse": True},  # 红色
    "offline":     {"char": "·", "color": 8, "pulse": False},  # 灰暗
}


@dataclass
class StarNode:
    """星图中的一个节点（代表一个 session）"""
    session: str
    x: float = 0.0     # 百分比位置 0-100
    y: float = 0.0
    base_x: float = 0.0
    base_y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    status: str = "start"
    tool: str = ""
    project: str = ""
    subagents: List[str] = field(default_factory=list)
    fade_alpha: float = 1.0      # 0.0=不可见, 1.0=完全可见
    anim_phase: float = 0.0      # 动画相位
    ripple: float = 0.0          # 涟漪半径


class Meteor:
    """流星粒子"""
    def __init__(self, max_w: int, max_h: int):
        # 从顶部或右侧出发
        if random.random() > 0.5:
            self.x = random.uniform(0, max_w)
            self.y = -2
        else:
            self.x = max_w + 2
            self.y = random.uniform(0, max_h * 0.5)
        angle = math.pi * (0.55 + random.random() * 0.3)
        speed = 1.5 + random.random() * 2
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = 1.0
        self.decay = 0.01 + random.random() * 0.02
        self.trail: List[Tuple[float, float]] = []
        self.max_trail = 12 + int(random.random() * 8)
        self.alive = True

    def update(self):
        self.trail.insert(0, (self.x, self.y))
        if len(self.trail) > self.max_trail:
            self.trail.pop()
        self.x += self.vx
        self.y += self.vy
        self.life -= self.decay
        if self.life <= 0:
            self.alive = False


class StarMap:
    """全息星图渲染引擎"""

    def __init__(self):
        self._stars: Dict[str, StarNode] = {}
        self._meteors: List[Meteor] = []
        self._radar_angle: float = 0.0
        self._field_w: int = 0
        self._field_h: int = 0

    def update_from_sessions(self, sessions: list):
        """根据 SessionTracker 的 sessions 更新星星"""
        # 标记当前已有的 session
        current_sessions = set()
        for s in sessions:
            current_sessions.add(s.session)
            if s.session not in self._stars:
                # 新 session：在面板中心附近随机位置创建
                star = StarNode(
                    session=s.session,
                    x=30 + random.uniform(5, 40),
                    y=20 + random.uniform(5, 50),
                    project=s.project,
                )
                star.base_x = star.x
                star.base_y = star.y
                star.vx = (random.random() - 0.5) * 0.06
                star.vy = (random.random() - 0.5) * 0.06
                self._stars[s.session] = star
            else:
                star = self._stars[s.session]

            star.status = s.status
            star.tool = s.tool
            star.project = s.project
            star.subagents = list(s.subagents)
            if s.status == "offline":
                star.fade_alpha = max(0, star.fade_alpha - 0.02)
            else:
                star.fade_alpha = min(1.0, star.fade_alpha + 0.1)

        # 渐隐消失的 offline session
        to_remove = []
        for sid, star in self._stars.items():
            if sid not in current_sessions:
                star.fade_alpha -= 0.01
                if star.fade_alpha <= 0:
                    to_remove.append(sid)
        for sid in to_remove:
            del self._stars[sid]

    def tick(self):
        """每帧调用：更新飘动、流星、雷达"""
        for star in self._stars.values():
            # 布朗运动
            star.vx += (random.random() - 0.5) * 0.012
            star.vy += (random.random() - 0.5) * 0.012
            # 速度上限
            star.vx = max(-0.12, min(0.12, star.vx))
            star.vy = max(-0.12, min(0.12, star.vy))
            # 弹性回弹
            star.vx += (star.base_x - star.x) * 0.001
            star.vy += (star.base_y - star.y) * 0.001
            # 边界
            if star.x < 5:
                star.vx += 0.03
            if star.x > 88:
                star.vx -= 0.03
            if star.y < 5:
                star.vy += 0.03
            if star.y > 88:
                star.vy -= 0.03
            # 阻尼
            star.vx *= 0.995
            star.vy *= 0.995
            star.x += star.vx
            star.y += star.vy
            # 动画相位
            star.anim_phase += 0.1
            # 涟漪
            if star.status == "hitl":
                star.ripple += 0.5

        # 雷达扫描
        self._radar_angle += math.pi * 2 / (6 * 20)  # 6秒一周 @20fps

        # 流星
        if len(self._meteors) < 3 and random.random() < 0.03:
            self._meteors.append(Meteor(100, 100))
        self._meteors = [m for m in self._meteors if m.alive]
        for m in self._meteors:
            m.update()

    def render(self, stdscr, x_off: int, y_off: int, width: int, height: int, addstr_fn) -> list:
        """渲染星图到 curses 窗口，返回需要绘制的元素列表"""
        import curses
        self._field_w = width
        self._field_h = height
        elements = []  # [(row, col, text, attr), ...]

        # 1. 背景网格（稀疏点阵）
        for gy in range(2, height - 1, 3):
            for gx in range(2, width - 1, 6):
                elements.append((y_off + gy, x_off + gx, ".", curses.A_DIM))

        # 2. 同心圆（面板中心）
        cx, cy = width // 2, height // 2
        for r_pct in [0.25, 0.40, 0.55]:
            r = int(min(width, height) * r_pct / 2)
            for angle in range(0, 360, 8):
                rad = math.radians(angle)
                px = int(cx + r * math.cos(rad))
                py = int(cy + r * math.sin(rad) * 0.5)  # 椭圆
                if 0 <= px < width and 0 <= py < height:
                    elements.append((y_off + py, x_off + px, ".", curses.A_DIM))

        # 3. 雷达扫描线
        scan_len = min(width, height) * 0.45
        sx = int(cx + scan_len * math.cos(self._radar_angle))
        sy = int(cy + scan_len * math.sin(self._radar_angle) * 0.5)
        # 画线（简单的直线点）
        steps = max(abs(sx - cx), abs(sy - cy), 1)
        for i in range(steps):
            t = i / steps
            px = int(cx + (sx - cx) * t)
            py = int(cy + (sy - cy) * t)
            if 0 <= px < width and 0 <= py < height:
                elements.append((y_off + py, x_off + px, "-", curses.color_pair(1) | curses.A_DIM))

        # 4. 流星
        for m in self._meteors:
            if len(m.trail) < 2:
                continue
            for i, (tx, ty) in enumerate(m.trail):
                # 将流星坐标映射到面板区域
                px = int(tx * width / 100)
                py = int(ty * height / 100)
                if 0 <= px < width and 0 <= py < height:
                    alpha = m.life * (1 - i / len(m.trail))
                    if alpha > 0.1:
                        elements.append((y_off + py, x_off + px, ".", curses.color_pair(6)))

        # 5. 星星节点
        for star in self._stars.values():
            display = STATUS_DISPLAY.get(star.status, STATUS_DISPLAY["idle"])
            # 百分比 → 面板坐标
            sx = int(star.x * width / 100)
            sy = int(star.y * height / 100)
            if sx < 1 or sx >= width - 1 or sy < 1 or sy >= height - 2:
                continue

            # 透明度
            if star.fade_alpha < 0.3:
                continue

            attr = curses.color_pair(display["color"])
            if display["pulse"]:
                # 脉冲效果：交替亮度
                phase = math.sin(star.anim_phase)
                if phase < -0.3:
                    attr |= curses.A_DIM
                elif phase > 0.3:
                    attr |= curses.A_BOLD

            # 涟漪
            if star.status == "hitl" and star.ripple > 0:
                ripple_r = int(star.ripple)
                for a in range(0, 360, 30):
                    rad = math.radians(a)
                    rx = int(sx + ripple_r * math.cos(rad))
                    ry = int(sy + ripple_r * math.sin(rad) * 0.5)
                    if 0 <= rx < width and 0 <= ry < height:
                        elements.append((y_off + ry, x_off + rx, ".", curses.color_pair(4) | curses.A_DIM))
                if star.ripple > 8:
                    star.ripple = 0

            # 星星字符
            elements.append((y_off + sy, x_off + sx, display["char"], attr))

            # session 名称（星星下方）
            name = star.project or star.session
            name = name[:12]
            elements.append((y_off + sy + 1, x_off + sx - len(name) // 2, name, curses.A_DIM))

            # 工具/状态信息（名称下方）
            if star.tool and star.status == "working":
                tool_text = f"... {star.tool}"[:14]
                elements.append((y_off + sy + 2, x_off + sx - len(tool_text) // 2, tool_text, curses.A_DIM))
            elif star.status == "hitl" and star.fade_alpha >= 0.5:
                hitl_text = "!! HITL"[:14]
                elements.append((y_off + sy + 2, x_off + sx - len(hitl_text) // 2, hitl_text, curses.color_pair(4)))

            # 子代理标识
            if star.subagents:
                sa_text = f":{star.subagents[0][:6]}"[:8]
                elements.append((y_off + sy, x_off + sx + 2, sa_text, curses.A_DIM))

        return elements
