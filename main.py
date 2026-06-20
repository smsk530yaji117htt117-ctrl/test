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

# subprocess hard-kill までの秒数。環境変数で上書き可能（値が1箇所に集約される）。
# consensus 側の RUNNING_TIMEOUT_MINUTES（既定15分）はこの kill を上回る前提で短めに設定し、
# kill された Running 行を数 cron ティックで回収できるようにしている。
CONSENSUS_TIMEOUT_SECONDS = int(os.environ.get("CONSENSUS_TIMEOUT_SECONDS", "480"))


def main() -> None:
    # ① consensus.py を subprocess 実行（改変・import はしない）
    try:
        completed = subprocess.run(
            [sys.executable, "consensus.py"], cwd=HERE, timeout=CONSENSUS_TIMEOUT_SECONDS
        )
        print(f"consensus.py 終了コード: {completed.returncode}")
    except subprocess.TimeoutExpired:
        print(
            f"consensus.py タイムアウト（{CONSENSUS_TIMEOUT_SECONDS}秒）。"
            f"Running 行は次回起動時の handle_running_timeouts で Error に回収されます"
        )
    except Exception as e:
        print(mask_secrets(f"consensus.py 実行に失敗: {e}"))

    # ② 終了コードに関わらず bridge を実行
    try:
        bridge.run()
    except Exception as e:
        print(mask_secrets(f"bridge 実行に失敗: {e}"))


if __name__ == "__main__":
    main()
