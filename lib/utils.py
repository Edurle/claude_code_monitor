"""共享工具函数"""


def display_width(s: str) -> int:
    """计算字符串显示宽度（考虑全角字符和 emoji）"""
    width = 0
    for c in s:
        code = ord(c)
        if '\u4e00' <= c <= '\u9fff' or code > 0x1F00:
            width += 2
        else:
            width += 1
    return width


def truncate_to_width(s: str, max_w: int) -> str:
    """截断字符串使其显示宽度不超过 max_w"""
    result = []
    w = 0
    for c in s:
        cw = 2 if (0x4e00 <= ord(c) <= 0x9fff or ord(c) > 0x1F00) else 1
        if w + cw > max_w:
            break
        result.append(c)
        w += cw
    return "".join(result)
