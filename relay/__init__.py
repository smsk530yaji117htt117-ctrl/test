# -*- coding: utf-8 -*-
"""relay — 会議結果 → Handoff 起票のリレー層。

generate_handoff_prompt: SynthesisDecision → Handoff spec（純関数・I/Oなし）
create_handoff_page:     Handoff spec → Notion AI Handoff DB へ起票（dry-run 可）
"""
