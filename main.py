# -*- coding: utf-8 -*-
"""
main — Render 用ラッパー

① subprocess で consensus.py を実行（consensus.py は import せず subprocess 起動のみ）
② その終了コードに関わらず bridge 処理を実行する

マージ後、Render の Start Command を `python consensus.py` から `python main.py` に変更する。
"""

import os
import subprocess
import sys

import bridge
from notify import mask_secrets

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    # ① consensus.py を subprocess 実行（改変・import はしない）
    try:
        completed = subprocess.run([sys.executable, "consensus.py"], cwd=HERE, timeout=480)
        print(f"consensus.py 終了コード: {completed.returncode}")
    except subprocess.TimeoutExpired:
        print("consensus.py タイムアウト（480秒）")
    except Exception as e:
        print(mask_secrets(f"consensus.py 実行に失敗: {e}"))

    # ② 終了コードに関わらず bridge を実行
    try:
        bridge.run()
    except Exception as e:
        print(mask_secrets(f"bridge 実行に失敗: {e}"))


if __name__ == "__main__":
    main()
