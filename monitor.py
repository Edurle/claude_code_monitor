#!/usr/bin/env python3
"""claude-monitor — 插件化 HITL 监控器入口"""
import curses
from lib.frame import Frame


def main():
    def run(stdscr):
        frame = Frame(stdscr)
        frame.run()

    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
