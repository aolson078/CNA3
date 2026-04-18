"""Tests for cna.rules.capability_points (Section 6.0)."""

from __future__ import annotations

import pytest

from cna.engine.errors import RuleViolationError
from cna.engine.game_state import (
    CohesionLevel,
    GameState,
    HexCoord,
    OrgSize,
    Player,
    Side,
    Unit,
    UnitClass,
    UnitStats,
    UnitType,
)
from cna.rules.capability_points import (
    COHESION_MAX,
    COHESION_SHATTERED,
    IDLE_RP_AWARD,
    apply_disorganization,
    apply_reorganization,
    award_idle_rp,
    averaged_cohesion,
    can_spend,
    cohesion_value,
    effective_cpa,
    is_shattered,
    reset_stage_cp,
    spend_cp,
    voluntary_cp_cap,
)


def _mk_unit(cpa: int = 8, toe: int = 6, **kwargs) -> Unit:
    defaults = dict(
        id="test.unit", side=Side.AXIS, name="Test Unit",
        unit_type=UnitType.INFANTRY, unit_class=UnitClass.INFANTRY,
        org_size=OrgSize.BATTALION,
        stats=UnitStats(capability_point_allowance=cpa, max_toe_strength=toe),
        position=HexCoord(0, 0), current_toe=toe,
    )
    defaults.update(kwargs)
    return Unit(**defaults)


# ---------------------------------------------------------------------------
# Effective CPA (Case 6.11)
# ---------------------------------------------------------------------------


def test_effective_cpa_normal():
    u = _mk_unit(cpa=15)
    assert effective_cpa(u) == 15


def test_effective_cpa_gun_zero():
    # Case 6.11: guns with CPA 0 → effective 10.
    u = _mk_unit(cpa=0, unit_type=UnitType.ARTILLERY)
    assert effective_cpa(u) == 10


def test_voluntary_cap_non_motorized():
    # Case 8.17: non-motorized (CPA ≤ 10) → 150% cap.
    u = _mk_unit(cpa=8)
    assert voluntary_cp_cap(u) == 12  # 8 + 4


def test_voluntary_cap_motorized():
    u = _mk_unit(cpa=25)
    cap = voluntary_cp_cap(u)
    assert cap > 1000  # Effectively uncapped.


# ---------------------------------------------------------------------------
# CP spending (Case 6.12, 6.21, 6.22)
# ---------------------------------------------------------------------------


def test_spend_within_cpa_no_dp():
    u = _mk_unit(cpa=10)
    dp = spend_cp(u, 5)
    assert dp == 0
    assert u.capability_points_spent == 5


def test_spend_exactly_at_cpa():
    u = _mk_unit(cpa=10)
    dp = spend_cp(u, 10)
    assert dp == 0
    assert u.capability_points_spent == 10


def test_spend_over_cpa_earns_dp():
    # Case 6.21: 1 DP per CP over CPA.
    u = _mk_unit(cpa=10)
    dp = spend_cp(u, 13)
    assert dp == 3
    assert u.capability_points_spent == 13
    assert cohesion_value(u) == -3


def test_incremental_overspend():
    # Spend 8, then 5 → total 13, overspend 3 DP.
    u = _mk_unit(cpa=10)
    dp1 = spend_cp(u, 8)
    assert dp1 == 0
    dp2 = spend_cp(u, 5)
    assert dp2 == 3
    assert cohesion_value(u) == -3


def test_spend_zero_is_noop():
    u = _mk_unit(cpa=10)
    dp = spend_cp(u, 0)
    assert dp == 0


def test_can_spend_within_voluntary_cap():
    u = _mk_unit(cpa=8)
    assert can_spend(u, 12)  # 8 * 1.5 = 12
    assert not can_spend(u, 13)


def test_can_spend_involuntary_bypasses_cap():
    u = _mk_unit(cpa=8)
    assert can_spend(u, 20, voluntary=False)


# ---------------------------------------------------------------------------
# Cohesion (Cases 6.22, 6.23, 6.26)
# ---------------------------------------------------------------------------


def test_disorganization_lowers_cohesion():
    u = _mk_unit()
    apply_disorganization(u, 5)
    assert cohesion_value(u) == -5
    assert u.cohesion == CohesionLevel.DISORGANIZED


def test_reorganization_raises_cohesion():
    u = _mk_unit()
    apply_disorganization(u, 5)
    apply_reorganization(u, 3)
    assert cohesion_value(u) == -2


def test_reorganization_capped_at_plus_ten():
    u = _mk_unit()
    apply_reorganization(u, 15)
    assert cohesion_value(u) == COHESION_MAX


def test_reorganization_cap_at_zero():
    # Case 6.24.1: idle stage RP caps at 0.
    u = _mk_unit()
    apply_disorganization(u, 3)
    apply_reorganization(u, 10, cap_at_zero=True)
    assert cohesion_value(u) == 0


def test_shattered_threshold():
    u = _mk_unit()
    apply_disorganization(u, 26)
    assert is_shattered(u)
    assert u.cohesion == CohesionLevel.SHATTERED


def test_shattered_cannot_spend():
    u = _mk_unit()
    apply_disorganization(u, 30)
    with pytest.raises(RuleViolationError) as exc:
        spend_cp(u, 1)
    assert exc.value.case_number == "6.26"


def test_shattered_can_spend_returns_false():
    u = _mk_unit()
    apply_disorganization(u, 30)
    assert not can_spend(u, 1)


# ---------------------------------------------------------------------------
# Case 6.22 example from rulebook
# ---------------------------------------------------------------------------


def test_rulebook_example_6_22():
    # "the 1st RNF, with a CPA of '8' and a Cohesion Level of -2
    # has expended five CP's ... then assaults ... expending five CP's
    # ... exceeded CPA by two, earning 2 DP's → Cohesion -4"
    u = _mk_unit(cpa=8)
    apply_disorganization(u, 2)  # Start at Cohesion -2.
    assert cohesion_value(u) == -2

    spend_cp(u, 5)   # 5 CP spent, still within CPA.
    assert cohesion_value(u) == -2

    dp = spend_cp(u, 5)   # 10 total, over CPA by 2.
    assert dp == 2
    assert cohesion_value(u) == -4


# ---------------------------------------------------------------------------
# Stage boundary (Case 6.16, 6.24)
# ---------------------------------------------------------------------------


def test_reset_stage_cp():
    gs = GameState()
    u = _mk_unit(cpa=10)
    u.capability_points_spent = 7
    gs.units[u.id] = u
    reset_stage_cp(gs)
    assert u.capability_points_spent == 0


def test_award_idle_rp():
    gs = GameState()
    idle_unit = _mk_unit(id="idle", cpa=10)
    apply_disorganization(idle_unit, 3)
    idle_unit.capability_points_spent = 0
    gs.units[idle_unit.id] = idle_unit

    active_unit = _mk_unit(id="active", cpa=10)
    active_unit.capability_points_spent = 5
    gs.units[active_unit.id] = active_unit

    awarded = award_idle_rp(gs, None)
    assert "idle" in awarded
    assert "active" not in awarded
    assert cohesion_value(idle_unit) == 0  # Was -3, +5 capped at 0.


# ---------------------------------------------------------------------------
# Multi-unit averaging (Case 6.27)
# ---------------------------------------------------------------------------


def test_averaged_cohesion_single():
    u = _mk_unit()
    apply_disorganization(u, 4)
    assert averaged_cohesion([u]) == -4


def test_averaged_cohesion_multiple():
    # Case 6.27 example: three brigades at -4, -1, +3 → average = -2/3 ≈ 0
    a = _mk_unit(id="a")
    b = _mk_unit(id="b")
    c = _mk_unit(id="c")
    apply_disorganization(a, 4)
    apply_disorganization(b, 1)
    apply_reorganization(c, 3)
    result = averaged_cohesion([a, b, c])
    # (-4 + -1 + 3) / 3 = -2/3 → truncated to 0 (int toward zero).
    assert result == 0


def test_averaged_cohesion_empty():
    assert averaged_cohesion([]) == 0
