"""Sync guard: the pure functions in contracts/safelink.py must stay
byte-identical (AST-identical) to contracts/safelink_logic.py.

The contract is self-contained because a single-file GenLayer contract
cannot import a sibling module on-chain, so the logic is duplicated.
If this test fails, copy the changed function from safelink_logic.py
into safelink.py (or vice versa) and re-run.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGIC = ROOT / "contracts" / "safelink_logic.py"
CONTRACT = ROOT / "contracts" / "safelink.py"

PURE_FUNCTIONS = [
    "host_of",
    "normalize_url",
    "_impersonated_brand",
    "_is_ip_literal",
    "_off_host_form",
    "derive_signals",
    "verdict_from_signals",
]


def _functions(path):
    tree = ast.parse(path.read_text())
    return {
        node.name: ast.dump(node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def test_pure_functions_in_sync():
    logic_fns = _functions(LOGIC)
    contract_fns = _functions(CONTRACT)
    for name in PURE_FUNCTIONS:
        assert name in logic_fns, f"{name} missing from safelink_logic.py"
        assert name in contract_fns, f"{name} missing from safelink.py"
        assert logic_fns[name] == contract_fns[name], (
            f"{name} drifted between safelink_logic.py and safelink.py — "
            "copy the change across and re-run"
        )


def test_contract_header_pins_stable_runner():
    first_line = CONTRACT.read_text().splitlines()[0]
    assert first_line == (
        '# { "Depends": "py-genlayer:'
        "1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6"
        '" }'
    )
    assert "py-genlayer:test" not in CONTRACT.read_text()
    assert "py-genlayer:latest" not in CONTRACT.read_text()


def test_no_llm_calls_in_contract():
    text = CONTRACT.read_text()
    assert "exec_prompt" not in text
    assert "nondet.llm" not in text
