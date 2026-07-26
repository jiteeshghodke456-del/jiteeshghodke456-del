# Backlog

Open items only. Delete the line when it is fixed.

- [low][tetris] Mobile board shows only the most recent 42 of 59 problems — 7px cells cap the column count at 420px wide. Card reports the truncated count honestly. `scripts/cockpit/cards/tetris.py:60`
- [low][cluster] Mobile dial readout ("37%") slightly overlaps the value arc at radius 52. Legible, not clean. `scripts/cockpit/cards/cluster.py:_dial`
- [low][design] No light-theme asset variants — the cards are deliberately always dark. Revisit only if the page reads badly for light-theme users.
- [low][icons] LinkedIn has no icon: Simple Icons removed the slug over trademark policy, so the contact row sets it as text. Do not re-add `linkedin` to `vendor_icons.py`; it 404s.
- [info][fonts] `assets/fonts/*.ttf` are vendored sources for `vendor_glyphs.py` only. Nothing at runtime reads them; the generator reads `assets/glyphs/*.json`.
