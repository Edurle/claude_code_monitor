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
