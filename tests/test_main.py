# -*- coding: utf-8 -*-
"""main.py のテスト（consensus.py は subprocess 起動・終了コードに関わらず bridge 実行）。"""
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import main


def test_runs_bridge_even_when_consensus_nonzero():
    completed = MagicMock(returncode=1)
    with patch.object(main.subprocess, "run", return_value=completed) as run, \
         patch.object(main.bridge, "run") as bridge_run:
        main.main()
    run.assert_called_once()
    # consensus を import せず subprocess で起動している
    assert run.call_args[0][0][1] == "consensus.py"
    bridge_run.assert_called_once()


def test_runs_bridge_even_when_consensus_raises():
    with patch.object(main.subprocess, "run", side_effect=OSError("spawn failed")), \
         patch.object(main.bridge, "run") as bridge_run:
        main.main()
    bridge_run.assert_called_once()


def test_bridge_failure_does_not_raise():
    completed = MagicMock(returncode=0)
    with patch.object(main.subprocess, "run", return_value=completed), \
         patch.object(main.bridge, "run", side_effect=RuntimeError("bridge boom")):
        main.main()  # 例外が外に漏れなければ合格
