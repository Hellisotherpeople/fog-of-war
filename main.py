#!/usr/bin/env python3
"""FOG OF WAR - a Second World War roguelike.

    python main.py            play
    python main.py --font F   use another CP437 16x16 tilesheet
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(description="FOG OF WAR - a WW2 roguelike")
    ap.add_argument("--font", help="path to a CP437 16x16 tilesheet png")
    args = ap.parse_args()
    from fow.ui import App
    App(font=args.font).run()


if __name__ == "__main__":
    main()
