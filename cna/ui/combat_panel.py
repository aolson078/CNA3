"""Section 11.0 — Combat detail display panel.

Renders a CombatReport (from cna/rules/combat/resolver.py) as a Rich
Panel suitable for embedding in the CNA dashboard. Shows the four-step
combat sequence: Barrage, Anti-Armor, Close Assault differential
breakdown, and final outcomes, with side-colored headers and
result-coded styles.

Cross-references:
  - Case 11.0: Combat sequence overview.
  - Case 12.0: Barrage results.
  - Case 14.0: Anti-Armor results.
  - Case 15.0: Close Assault differential and CRT results.
  - Case 11.2: CP costs for combat participants.
"""

from __future__ import annotations

from typing import Optional

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cna.engine.game_state import GameState, HexCoord, Side, Unit, UnitType
from cna.rules.combat.barrage import BarrageResult
from cna.rules.combat.anti_armor import AntiArmorResult
from cna.rules.combat.close_assault import (
    AssaultDifferential,
    AssaultOutcome,
    CloseAssaultResult,
)
from cna.rules.combat.common import (
    CombatStrengthSummary,
    summarize_combat_strength,
)
from cna.rules.combat.resolver import CombatReport


# ---------------------------------------------------------------------------
# Style constants (mirrors dashboard.py SIDE_STYLES)
# ---------------------------------------------------------------------------

SIDE_STYLES: dict[Side, str] = {
    Side.AXIS: "bold red",
    Side.COMMONWEALTH: "bold cyan",
}

_FAVORABLE = "green"
_UNFAVORABLE = "red"
_NEUTRAL = "yellow"


def _side_color(side: Side) -> str:
    """Return the Rich color name for a side."""
    return "red" if side == Side.AXIS else "cyan"


def _result_style(value: int, *, higher_is_better: bool = True) -> str:
    """Pick green/red/yellow based on a numeric result.

    Case 11.0 -- Color-code combat results for quick readability.
    """
    if value == 0:
        return _NEUTRAL
    if higher_is_better:
        return _FAVORABLE if value > 0 else _UNFAVORABLE
    return _UNFAVORABLE if value > 0 else _FAVORABLE


def _signed(value: int) -> str:
    """Format an int with explicit +/- sign."""
    return f"+{value}" if value > 0 else str(value)


# ---------------------------------------------------------------------------
# Section 1: Header
# ---------------------------------------------------------------------------


def _render_header(report: CombatReport) -> Text:
    """Section 11.0 -- Combat header showing hex coordinates and sides.

    Format: "COMBAT: Hex(q,r) -> Hex(q,r)" with attacker/defender coloring.
    """
    t = Text()
    t.append("COMBAT: ", style="bold white")
    att_coord = report.attacker_hex
    def_coord = report.defender_hex
    att_style = _side_color(report.attacker_side)
    def_style = _side_color(report.defender_side)
    t.append(f"Hex({att_coord.q},{att_coord.r})", style=f"bold {att_style}")
    t.append(" -> ", style="bold white")
    t.append(f"Hex({def_coord.q},{def_coord.r})", style=f"bold {def_style}")
    return t


# ---------------------------------------------------------------------------
# Section 2: Forces table
# ---------------------------------------------------------------------------


def _unit_type_label(u: Unit) -> str:
    """Short type label for the forces table."""
    return u.unit_type.value.replace("_", " ").title()


def _render_forces_table(
    attackers: list[Unit],
    defenders: list[Unit],
    attacker_side: Side,
    defender_side: Side,
) -> Table:
    """Section 11.0 -- List each unit on each side with name, TOE, type.

    Case 11.0 -- Forces engaged in this combat.
    """
    table = Table(
        title="Forces Engaged",
        show_header=True,
        expand=True,
        pad_edge=False,
    )
    table.add_column("Role", no_wrap=True, style="bold")
    table.add_column("Unit", no_wrap=True)
    table.add_column("Type", no_wrap=True)
    table.add_column("TOE", justify="right")

    att_style = _side_color(attacker_side)
    for u in attackers:
        table.add_row(
            Text("ATK", style=att_style),
            u.name,
            _unit_type_label(u),
            str(u.current_toe),
        )

    def_style = _side_color(defender_side)
    for u in defenders:
        table.add_row(
            Text("DEF", style=def_style),
            u.name,
            _unit_type_label(u),
            str(u.current_toe),
        )

    if not attackers and not defenders:
        table.add_row("--", "(no units)", "--", "--")

    return table


# ---------------------------------------------------------------------------
# Section 3: Strength summary
# ---------------------------------------------------------------------------


def _render_strength_summary(
    att_summary: CombatStrengthSummary,
    def_summary: CombatStrengthSummary,
    attacker_side: Side,
    defender_side: Side,
) -> Table:
    """Section 11.0, Cases 11.32-11.36 -- Raw and Actual strength breakdown.

    Shows Raw -> Actual for barrage, anti-armor, and close assault
    (offensive for attacker, defensive for defender).
    """
    table = Table(
        title="Strength Summary",
        show_header=True,
        expand=True,
        pad_edge=False,
    )
    att_label = f"ATK ({attacker_side.value[:2].upper()})"
    def_label = f"DEF ({defender_side.value[:2].upper()})"

    table.add_column("Category", no_wrap=True, style="bold")
    table.add_column(att_label, justify="right",
                     header_style=_side_color(attacker_side))
    table.add_column(def_label, justify="right",
                     header_style=_side_color(defender_side))

    def _fmt_raw_actual(raw: int, actual: int) -> Text:
        return Text(f"{raw} -> {actual}")

    table.add_row(
        "Barrage",
        _fmt_raw_actual(att_summary.barrage_raw, att_summary.barrage_actual),
        _fmt_raw_actual(def_summary.barrage_raw, def_summary.barrage_actual),
    )
    table.add_row(
        "Anti-Armor",
        _fmt_raw_actual(att_summary.anti_armor_raw, att_summary.anti_armor_actual),
        _fmt_raw_actual(def_summary.anti_armor_raw, def_summary.anti_armor_actual),
    )
    table.add_row(
        "Close Assault",
        _fmt_raw_actual(
            att_summary.offensive_assault_raw, att_summary.offensive_assault_actual
        ),
        _fmt_raw_actual(
            def_summary.defensive_assault_raw, def_summary.defensive_assault_actual
        ),
    )
    return table


# ---------------------------------------------------------------------------
# Section 4: Step-by-step results
# ---------------------------------------------------------------------------


def _render_barrage_result(barrage: Optional[BarrageResult]) -> Text:
    """Section 12.0, Case 12.6 -- Barrage result line.

    Shows points, roll, and result (Pinned, losses).
    """
    t = Text()
    t.append("Barrage: ", style="bold")
    if barrage is None:
        t.append("(skipped)", style="dim")
        return t
    t.append(f"{barrage.barrage_points} pts, roll {barrage.dice_roll}")
    if barrage.pinned and barrage.toe_losses > 0:
        t.append(f" -> PINNED + {barrage.toe_losses} losses", style=_FAVORABLE)
    elif barrage.pinned:
        t.append(" -> PINNED", style=_NEUTRAL)
    elif barrage.toe_losses > 0:
        t.append(f" -> {barrage.toe_losses} losses", style=_FAVORABLE)
    else:
        t.append(" -> No effect", style="dim")
    return t


def _render_anti_armor_results(
    att_aa: Optional[AntiArmorResult],
    def_aa: Optional[AntiArmorResult],
    attacker_side: Side,
    defender_side: Side,
) -> Text:
    """Section 14.0, Case 14.6 -- Anti-armor fire results for both sides.

    Shows attacker fire -> DP against defender, and defender fire -> DP
    against attacker.
    """
    t = Text()
    t.append("Anti-Armor:\n", style="bold")

    # Attacker fires at defender armor
    t.append("  ATK fire: ", style=_side_color(attacker_side))
    if att_aa is None:
        t.append("(no AT fire)", style="dim")
    else:
        dp_style = _FAVORABLE if att_aa.damage_points > 0 else "dim"
        t.append(
            f"{att_aa.aa_points} pts, roll {att_aa.dice_roll} -> "
            f"{att_aa.damage_points} DP",
            style=dp_style,
        )

    t.append("\n")

    # Defender fires at attacker armor
    t.append("  DEF fire: ", style=_side_color(defender_side))
    if def_aa is None:
        t.append("(no AT fire)", style="dim")
    else:
        dp_style = _UNFAVORABLE if def_aa.damage_points > 0 else "dim"
        t.append(
            f"{def_aa.aa_points} pts, roll {def_aa.dice_roll} -> "
            f"{def_aa.damage_points} DP",
            style=dp_style,
        )

    return t


def _render_differential_breakdown(diff: Optional[AssaultDifferential]) -> Text:
    """Section 15.0, Cases 15.2-15.6 -- Assault differential breakdown.

    Shows: basic + terrain + morale + org-size + 2:1 + combined arms = final.
    """
    t = Text()
    t.append("Assault Differential:\n", style="bold")
    if diff is None:
        t.append("  (no close assault)", style="dim")
        return t

    t.append(f"  Basic (att {diff.attacker_actual} - def {diff.defender_actual}): ")
    t.append(_signed(diff.basic_differential), style=_result_style(diff.basic_differential))
    t.append("\n")

    modifiers: list[tuple[str, int]] = [
        ("Terrain", diff.terrain_shift),
        ("Morale", diff.morale_shift),
        ("Org-Size", diff.org_size_shift),
        ("2:1 Raw", diff.raw_2to1_shift),
        ("Combined Arms", -diff.combined_arms_penalty),
    ]
    for label, value in modifiers:
        if value != 0:
            t.append(f"    {label}: ")
            t.append(_signed(value), style=_result_style(value))
            t.append("\n")

    final_style = _result_style(diff.final_differential)
    t.append("  Final: ")
    t.append(_signed(diff.final_differential), style=f"bold {final_style}")
    if diff.is_overrun:
        t.append(" OVERRUN", style="bold red")
    if diff.is_probe:
        t.append(" (Probe)", style="dim")

    return t


def _render_close_assault_result(ca: Optional[CloseAssaultResult]) -> Text:
    """Section 15.0, Cases 15.7-15.8 -- Close assault CRT result.

    Shows attacker/defender loss%, raw losses, and outcome.
    """
    t = Text()
    t.append("Close Assault:\n", style="bold")
    if ca is None:
        t.append("  (skipped)", style="dim")
        return t

    # Attacker losses
    att_style = _UNFAVORABLE if ca.attacker_loss_pct > 10 else _NEUTRAL
    t.append("  ATK: ", style="bold")
    t.append(f"{ca.attacker_loss_pct}% loss, {ca.attacker_raw_losses} raw", style=att_style)
    t.append("\n")

    # Defender losses
    def_style = _FAVORABLE if ca.defender_loss_pct > 10 else _NEUTRAL
    t.append("  DEF: ", style="bold")
    t.append(f"{ca.defender_loss_pct}% loss, {ca.defender_raw_losses} raw", style=def_style)
    t.append("\n")

    # Outcome
    outcome_styles: dict[AssaultOutcome, str] = {
        AssaultOutcome.NO_EFFECT: "dim",
        AssaultOutcome.ENGAGED: _NEUTRAL,
        AssaultOutcome.RETREAT: _FAVORABLE,
        AssaultOutcome.CAPTURED: f"bold {_FAVORABLE}",
    }
    outcome_style = outcome_styles.get(ca.outcome, "")
    t.append("  Outcome: ")
    t.append(ca.outcome.value.replace("_", " ").title(), style=outcome_style)
    if ca.outcome == AssaultOutcome.RETREAT and ca.retreat_hexes > 0:
        t.append(f" ({ca.retreat_hexes} hex{'es' if ca.retreat_hexes != 1 else ''})")

    return t


# ---------------------------------------------------------------------------
# Section 5: CP costs
# ---------------------------------------------------------------------------


def _render_cp_costs(report: CombatReport) -> Text:
    """Section 11.0, Cases 11.21-11.27 -- CP expenditure for combat.

    Shows CP spent by each side.
    """
    t = Text()
    t.append("CP Costs: ", style="bold")
    att_style = _side_color(report.attacker_side)
    def_style = _side_color(report.defender_side)
    t.append(f"ATK {report.attacker_cp_spent} CP", style=att_style)
    t.append("  ")
    t.append(f"DEF {report.defender_cp_spent} CP", style=def_style)
    return t


# ---------------------------------------------------------------------------
# Section 6: Supply costs
# ---------------------------------------------------------------------------


def _render_supply_costs(
    attackers: list[Unit],
    defenders: list[Unit],
    report: CombatReport,
    attacker_side: Side,
    defender_side: Side,
) -> Text:
    """Section 11.0 -- Ammo consumed by each side in combat.

    Case 11.0 -- Supply costs are proportional to units engaged.
    The barrage/AA/assault each consume ammunition. We show a summary
    based on the units that participated.
    """
    t = Text()
    t.append("Supply: ", style="bold")

    # Estimate ammo consumed: barrage points + AA points + assault points
    # each contribute. We show the number of units engaged as a proxy.
    att_count = len(attackers)
    def_count = len(defenders)
    att_style = _side_color(attacker_side)
    def_style = _side_color(defender_side)
    t.append(f"ATK {att_count} unit{'s' if att_count != 1 else ''} engaged", style=att_style)
    t.append("  ")
    t.append(f"DEF {def_count} unit{'s' if def_count != 1 else ''} engaged", style=def_style)
    return t


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_combat_report(report: CombatReport, state: GameState) -> Panel:
    """Render a full CombatReport as a Rich Panel for the dashboard.

    Section 11.0 -- Displays the four-step combat sequence results:
    forces engaged, strength summary, barrage, anti-armor, close assault
    differential breakdown, CRT outcomes, CP costs, and supply.

    Args:
        report: The CombatReport from resolve_combat().
        state: Current GameState (used to look up unit details).

    Returns:
        A Rich Panel suitable for display in the CNA dashboard.
    """
    # Gather the units involved.
    attackers = [
        u for u in state.units.values()
        if u.position == report.attacker_hex and u.side == report.attacker_side
    ]
    defenders = [
        u for u in state.units.values()
        if u.position == report.defender_hex and u.side == report.defender_side
    ]

    # Also check if units retreated away from the defender hex
    # (they may no longer be at the original position after combat).
    if not defenders and report.defender_toe_lost > 0:
        # Units were destroyed or retreated; we still show the report
        # with an empty defender list.
        pass

    # Compute strength summaries.
    att_summary = summarize_combat_strength(attackers)
    def_summary = summarize_combat_strength(defenders)

    # Build all sections.
    header = _render_header(report)
    forces = _render_forces_table(
        attackers, defenders, report.attacker_side, report.defender_side
    )
    strengths = _render_strength_summary(
        att_summary, def_summary, report.attacker_side, report.defender_side
    )

    # Step-by-step results
    barrage_line = _render_barrage_result(report.barrage)
    aa_lines = _render_anti_armor_results(
        report.anti_armor_attacker,
        report.anti_armor_defender,
        report.attacker_side,
        report.defender_side,
    )
    diff_lines = _render_differential_breakdown(report.differential)
    ca_lines = _render_close_assault_result(report.close_assault)

    # Costs
    cp_line = _render_cp_costs(report)
    supply_line = _render_supply_costs(
        attackers, defenders, report, report.attacker_side, report.defender_side
    )

    # Separator
    sep = Text("---", style="dim")

    body = Group(
        header,
        Text(""),
        forces,
        Text(""),
        strengths,
        Text(""),
        sep,
        barrage_line,
        Text(""),
        aa_lines,
        Text(""),
        diff_lines,
        Text(""),
        ca_lines,
        Text(""),
        sep,
        cp_line,
        supply_line,
    )

    # Panel border color based on attacker side.
    border = SIDE_STYLES.get(report.attacker_side, "white")
    return Panel(body, title="Combat Report", border_style=border)
