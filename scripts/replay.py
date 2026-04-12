"""CNA Deterministic Replay Regression Harness.

Records a sequence of game actions with seeded dice to a JSON file, then
replays the same sequence after code changes. Any state divergence = regression.

Commands:
    record   Run actions with a seeded DiceRoller, save actions + resulting state.
    replay   Re-run the recorded action sequence, save new state.
    diff     Compare two state files and report divergences.

The replay file format:
    {
        "seed": 42,
        "recorded_at": "2026-04-12T10:00:00",
        "actions": [
            {"type": "roll", "method": "roll", "args": {}, "expected_result": 3},
            {"type": "roll", "method": "roll_concat", "args": {}, "expected_result": 52},
            ...
        ],
        "final_state": {
            "roll_log": [...],
            "roll_count": 5,
            "last_seed": 42
        }
    }

Usage:
    python scripts/replay.py record --seed 42 --output regression_01.json
    python scripts/replay.py replay --input regression_01.json --output replay_result.json
    python scripts/replay.py diff --expected regression_01.json --actual replay_result.json
"""

import argparse
import io
import json
import os
import sys
from datetime import datetime, timezone

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add project root to path so we can import from cna
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from cna.engine.dice import DiceRoller  # noqa: E402


# ---------------------------------------------------------------------------
# Default action sequence -- a mix of roll types to exercise the dice module.
# Projects can extend this with custom action providers.
# ---------------------------------------------------------------------------

DEFAULT_ACTIONS = [
    {"type": "roll", "method": "roll", "args": {}},
    {"type": "roll", "method": "roll", "args": {}},
    {"type": "roll", "method": "roll_concat", "args": {}},
    {"type": "roll", "method": "roll_sum", "args": {"count": 2}},
    {"type": "roll", "method": "roll", "args": {}},
    {"type": "roll", "method": "roll_concat", "args": {}},
    {"type": "roll", "method": "roll_concat", "args": {}},
    {"type": "roll", "method": "roll_sum", "args": {"count": 3}},
    {"type": "roll", "method": "roll", "args": {}},
    {"type": "roll", "method": "roll", "args": {}},
    {"type": "roll", "method": "roll_sum", "args": {"count": 2}},
    {"type": "roll", "method": "roll_concat", "args": {}},
]


def execute_action(roller: DiceRoller, action: dict) -> int:
    """Execute a single action against the DiceRoller.

    Returns the result of the dice operation.
    """
    method_name = action["method"]
    args = action.get("args", {})

    method = getattr(roller, method_name, None)
    if method is None:
        raise ValueError(f"Unknown DiceRoller method: {method_name}")

    return method(**args)


def capture_state(roller: DiceRoller) -> dict:
    """Capture the current roller state for comparison."""
    return {
        "roll_log": [dict(entry) for entry in roller.roll_log],
        "roll_count": len(roller.roll_log),
        "last_seed": roller.seed,
    }


def load_actions_file(filepath: str) -> dict:
    """Load a previously saved action/state file."""
    if not os.path.isfile(filepath):
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_record(args):
    """Record a sequence of actions with a seeded dice roller."""
    seed = args.seed
    actions_file = args.actions
    output = args.output

    # Load custom actions or use defaults
    if actions_file:
        with open(actions_file, 'r', encoding='utf-8') as f:
            actions = json.load(f)
        print(f"  Loaded {len(actions)} actions from {actions_file}")
    else:
        actions = list(DEFAULT_ACTIONS)
        print(f"  Using {len(actions)} default actions")

    print(f"  Seed: {seed}")
    print()

    roller = DiceRoller(seed=seed)
    recorded_actions = []

    for i, action in enumerate(actions):
        result = execute_action(roller, action)
        recorded_action = dict(action)
        recorded_action["expected_result"] = result
        recorded_actions.append(recorded_action)
        print(f"  [{i + 1:>3}] {action['method']:15s} -> {result}")

    final_state = capture_state(roller)

    record = {
        "seed": seed,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "actions": recorded_actions,
        "final_state": final_state,
    }

    with open(output, 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    print()
    print(f"  Recorded {len(recorded_actions)} actions to {output}")
    print(f"  Final state: {final_state['roll_count']} rolls logged")


def cmd_replay(args):
    """Replay a recorded sequence and save the new state."""
    input_path = args.input
    output = args.output

    record = load_actions_file(input_path)
    seed = record["seed"]
    actions = record["actions"]

    print(f"  Replaying {len(actions)} actions from {os.path.basename(input_path)}")
    print(f"  Seed: {seed}")
    print()

    roller = DiceRoller(seed=seed)
    replayed_actions = []
    mismatches = 0

    for i, action in enumerate(actions):
        result = execute_action(roller, action)
        expected = action.get("expected_result")

        status = "OK"
        if expected is not None and result != expected:
            status = "MISMATCH"
            mismatches += 1

        replayed_action = dict(action)
        replayed_action["actual_result"] = result
        replayed_actions.append(replayed_action)

        indicator = "  " if status == "OK" else "!!"
        print(f"  {indicator} [{i + 1:>3}] {action['method']:15s} -> {result}"
              + (f"  (expected {expected})" if status != "OK" else ""))

    final_state = capture_state(roller)

    replay_record = {
        "seed": seed,
        "replayed_at": datetime.now(timezone.utc).isoformat(),
        "source": os.path.basename(input_path),
        "actions": replayed_actions,
        "final_state": final_state,
        "mismatches": mismatches,
    }

    with open(output, 'w', encoding='utf-8') as f:
        json.dump(replay_record, f, indent=2, ensure_ascii=False)

    print()
    if mismatches == 0:
        print(f"  PASS: All {len(actions)} actions matched. Saved to {output}")
    else:
        print(f"  FAIL: {mismatches} mismatches found. Saved to {output}")

    return mismatches


def cmd_diff(args):
    """Compare two state files and report divergences."""
    expected_path = args.expected
    actual_path = args.actual

    expected = load_actions_file(expected_path)
    actual = load_actions_file(actual_path)

    print(f"  Comparing:")
    print(f"    Expected: {os.path.basename(expected_path)}")
    print(f"    Actual:   {os.path.basename(actual_path)}")
    print()

    divergences = []

    # Compare seeds
    if expected.get("seed") != actual.get("seed"):
        divergences.append(
            f"Seed mismatch: expected {expected.get('seed')}, got {actual.get('seed')}"
        )

    # Compare action counts
    exp_actions = expected.get("actions", [])
    act_actions = actual.get("actions", [])
    if len(exp_actions) != len(act_actions):
        divergences.append(
            f"Action count mismatch: expected {len(exp_actions)}, got {len(act_actions)}"
        )

    # Compare individual action results
    min_len = min(len(exp_actions), len(act_actions))
    for i in range(min_len):
        exp_result = exp_actions[i].get("expected_result", exp_actions[i].get("actual_result"))
        act_result = act_actions[i].get("actual_result", act_actions[i].get("expected_result"))

        if exp_result != act_result:
            divergences.append(
                f"Action {i + 1} ({exp_actions[i]['method']}): "
                f"expected {exp_result}, got {act_result}"
            )

    # Compare final state
    exp_state = expected.get("final_state", {})
    act_state = actual.get("final_state", {})

    if exp_state.get("roll_count") != act_state.get("roll_count"):
        divergences.append(
            f"Roll count: expected {exp_state.get('roll_count')}, "
            f"got {act_state.get('roll_count')}"
        )

    # Deep compare roll logs
    exp_log = exp_state.get("roll_log", [])
    act_log = act_state.get("roll_log", [])
    if len(exp_log) != len(act_log):
        divergences.append(
            f"Roll log length: expected {len(exp_log)}, got {len(act_log)}"
        )
    else:
        for i, (e, a) in enumerate(zip(exp_log, act_log)):
            if e != a:
                divergences.append(f"Roll log entry {i}: expected {e}, got {a}")

    # Report
    if not divergences:
        print("  PASS: No divergences found. States are identical.")
    else:
        print(f"  FAIL: {len(divergences)} divergence(s) found:")
        print()
        for d in divergences:
            print(f"    !! {d}")

    print()
    return len(divergences)


def main():
    parser = argparse.ArgumentParser(
        description="CNA Deterministic Replay Regression Harness"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # record
    p_record = subparsers.add_parser("record", help="Record a new action sequence")
    p_record.add_argument('--seed', type=int, default=42,
                          help="Random seed (default: 42)")
    p_record.add_argument('--actions', '-a',
                          help="JSON file with custom action sequence")
    p_record.add_argument('--output', '-o', default="regression_baseline.json",
                          help="Output file (default: regression_baseline.json)")

    # replay
    p_replay = subparsers.add_parser("replay", help="Replay a recorded sequence")
    p_replay.add_argument('--input', '-i', required=True,
                          help="Recorded baseline file to replay")
    p_replay.add_argument('--output', '-o', default="regression_replay.json",
                          help="Output file for replay results")

    # diff
    p_diff = subparsers.add_parser("diff", help="Diff two state files")
    p_diff.add_argument('--expected', '-e', required=True,
                        help="Expected (baseline) state file")
    p_diff.add_argument('--actual', '-a', required=True,
                        help="Actual (replay) state file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    print()
    print("=" * 60)
    print(f"  CNA Replay Harness  [{args.command.upper()}]")
    print("=" * 60)
    print()

    if args.command == "record":
        cmd_record(args)
    elif args.command == "replay":
        exit_code = cmd_replay(args)
        sys.exit(1 if exit_code > 0 else 0)
    elif args.command == "diff":
        exit_code = cmd_diff(args)
        sys.exit(1 if exit_code > 0 else 0)


if __name__ == '__main__':
    main()
