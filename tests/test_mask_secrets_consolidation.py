# -*- coding: utf-8 -*-
"""
監査 Med: consensus.mask_secrets を notify.mask_secrets に一本化したことの担保。

旧 consensus 版は Bearer トークン / Slack・Discord webhook URL を取りこぼし、
これらを含む例外文字列が Notion / ログにそのまま書かれる恐れがあった。
統合後は notify 版（上位互換）が使われることを確認する。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import consensus
import notify


def test_consensus_uses_notify_mask_secrets():
    """consensus.mask_secrets は notify.mask_secrets と同一実体"""
    assert consensus.mask_secrets is notify.mask_secrets


def test_masks_bearer_and_webhooks_old_version_missed():
    """旧版が取りこぼしていた Bearer / webhook URL がマスクされる"""
    raw = (
        "auth=Bearer abc123DEF-token "
        "slack=https://hooks.slack.com/services/T000/B000/XXXXXX "
        "discord=https://discord.com/api/webhooks/123/abcXYZ"
    )
    masked = consensus.mask_secrets(raw)
    assert "abc123DEF-token" not in masked
    assert "Bearer ***" in masked
    assert "T000/B000/XXXXXX" not in masked
    assert "123/abcXYZ" not in masked


def test_still_masks_api_key_patterns():
    """従来の sk-ant- / ntn_ パターンも引き続きマスクされる"""
    masked = consensus.mask_secrets("key=sk-ant-SECRETVALUE tok=ntn_NOTIONSECRET")
    assert "sk-ant-SECRETVALUE" not in masked
    assert "ntn_NOTIONSECRET" not in masked
    assert "sk-ant-***" in masked
    assert "ntn_***" in masked


def test_none_is_safe():
    """None を渡しても落ちず空文字を返す（notify 版の堅牢性）"""
    assert consensus.mask_secrets(None) == ""
