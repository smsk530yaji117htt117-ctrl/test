# -*- coding: utf-8 -*-
"""絶対制約のガード: 新規モジュールが consensus.py を import しない。"""
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
MODULES = ["main.py", "bridge.py", "notify.py", "bridge_notion.py"]


@pytest.mark.parametrize("fname", MODULES)
def test_does_not_import_consensus(fname):
    with open(os.path.join(ROOT, fname), encoding="utf-8") as f:
        src = f.read()
    assert "import consensus" not in src
    assert "from consensus" not in src
