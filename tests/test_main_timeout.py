# -*- coding: utf-8 -*-
"""
監査 Low（安全網）: main.py の subprocess.TimeoutExpired 分岐。

consensus がタイムアウトで kill されても bridge.run() は必ず実行される
（通知/発火リレーを止めない）ことを担保する。既存 test_main.py は returncode!=0 と
OSError を覆うが timeout 分岐は未カバーだった。
"""
import os
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import main


def test_runs_bridge_even_when_consensus_times_out():
    timeout_exc = subprocess.TimeoutExpired(cmd="consensus.py", timeout=480)
    with patch.object(main.subprocess, "run", side_effect=timeout_exc), \
         patch.object(main.bridge, "run") as bridge_run:
        main.main()  # 例外が外に漏れないこと
    bridge_run.assert_called_once()
