"""Sections 11-15 — CNA Combat System.

The combat system is a multi-step sequence:
  1. Position Determination (guns Forward or Back) — Case 12.1
  2. Barrage (artillery indirect fire) — Section 12.0
  3. Retreat Before Assault (non-phasing only) — Section 13.0
  4. Force Assignment (allocate TOE to Anti-Armor or Close Assault)
  5. Anti-Armor Fire (simultaneous) — Section 14.0
  6. Close Assault (sequential, Phasing Player's choice) — Section 15.0

Modules:
  - common: Strength calculations, CP costs (Section 11.0)
  - barrage: Artillery barrage resolution (Section 12.0)
  - retreat: Retreat Before Assault (Section 13.0)
  - anti_armor: Anti-Armor combat (Section 14.0)
  - close_assault: Close Assault combat (Section 15.0)
"""
