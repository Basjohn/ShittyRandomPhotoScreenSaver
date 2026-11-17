"""Bounded Bubble owner replay and pass diagnostics (5.5s, variant a, display).

The recipes call owner_render_parity and restore process-local diagnostic hooks.
The exit code retains its parity verdict; inspect passive_guards_pass separately.
This synthetic fixture does not replace BTF section 24 music/performance gates.
Run as: python -m tools.visualizer_replay.bubble_native_diagnostics --help
"""
from __future__ import annotations

import argparse
import importlib
from pathlib import Path


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("replay", "Reproduce canonical owner rule (a), retaining module/source/settings proof."),
        ("fade-inputs", "Passively inspect input 244/346 fades, uploads and native cards."),
        ("components", "Inspect fixed input 346 ambient coverage/light with physical oracles."),
    ):
        sub = commands.add_parser(command, help=help_text)
        sub.add_argument("--repo", type=Path, required=True)
        sub.add_argument("--module-dir", type=Path, required=True)
        sub.add_argument("--label", required=True, help="Fresh evidence label; existing output is refused.")
        if command != "replay":
            sub.add_argument("--baseline-dir", type=Path, required=True)
        if command == "fade-inputs":
            sub.add_argument("--quad-adapter", type=Path, help="Explicit existing own-vertex-quad negative control.")
        if command == "components":
            sub.add_argument("--passive-dir", type=Path, required=True, help="Matched successful fade-input receipt.")
    return parser


def main(argv=None):
    parser = argument_parser()
    args = parser.parse_args(argv)
    from tools import artifact_paths

    # Refuse a different checkout: imported owners and evidence paths belong to this tool's checkout.
    root = artifact_paths.repository_root(args.repo)
    if root != artifact_paths.REPO_ROOT.resolve():
        parser.error("--repo must identify the checkout containing this diagnostic tool")
    args.repo = root
    from tools.visualizer_replay._bubble_native_common import fresh_output

    fresh_output(args.label)  # Fail before importing Qt/render owners or installing hooks.
    recipe = {"replay": "replay", "fade-inputs": "fade", "components": "components"}[args.command]
    module = importlib.import_module(f"tools.visualizer_replay._bubble_native_{recipe}")
    return module.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
