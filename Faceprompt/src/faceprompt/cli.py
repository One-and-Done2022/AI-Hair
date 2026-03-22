from __future__ import annotations

import argparse
import sys
from typing import Callable

from .catalog import catalog_summary, list_records, render_prompt, validate_catalog

STYLE_LINE_LABELS = {
    "realistic_editorial": "真实高级写真",
    "fashion_editorial": "时尚大片",
}

GENDER_CHOICES = [
    ("male", "男性"),
    ("female", "女性"),
]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="faceprompt")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("summary", help="Print catalog counts")
    subparsers.add_parser("validate", help="Validate bundled prompt catalog")

    list_parser = subparsers.add_parser("list", help="List catalog records")
    list_parser.add_argument("--category", choices=["scene", "hairstyle"])
    list_parser.add_argument("--gender", choices=["male", "female", "unisex"])
    list_parser.add_argument(
        "--style-line",
        choices=["realistic_editorial", "fashion_editorial"],
    )

    render_parser = subparsers.add_parser("render", help="Render a combined prompt")
    render_parser.add_argument("--scene", required=True)
    render_parser.add_argument("--hairstyle", required=True)
    render_parser.add_argument("--outfit")
    render_parser.add_argument("--expression")
    render_parser.add_argument("--subject-action")
    render_parser.add_argument("--hairstyle-action")
    render_parser.add_argument("--seed-source")

    subparsers.add_parser("interactive", help="Interactively choose gender, scene, and hairstyle")

    return parser


def _prompt_choice(
    *,
    title: str,
    options: list[tuple[str, str, str]],
    input_func: Callable[[str], str] | None = None,
    output_func: Callable[[str], None] | None = None,
) -> str:
    input_func = input_func or input
    output_func = output_func or print
    output_func(title)
    for index, (_, label, description) in enumerate(options, start=1):
        output_func(f"{index}. {label}")
        output_func(f"   {description}")

    while True:
        raw_value = input_func(f"请输入编号 [1-{len(options)}]，输入 q 退出: ").strip().lower()
        if raw_value in {"q", "quit", "exit"}:
            raise SystemExit(0)
        if raw_value.isdigit():
            index = int(raw_value)
            if 1 <= index <= len(options):
                return options[index - 1][0]
        output_func("请输入有效编号。")


def _record_options(category: str, *, gender: str | None = None) -> list[tuple[str, str, str]]:
    records = list_records(category=category, gender=gender)
    return [
        (
            record.id,
            f"{record.title} | {STYLE_LINE_LABELS[record.styleLine]}",
            record.summary,
        )
        for record in records
    ]


def run_interactive(
    *,
    input_func: Callable[[str], str] | None = None,
    output_func: Callable[[str], None] | None = None,
) -> int:
    input_func = input_func or input
    output_func = output_func or print
    output_func("交互式提示词生成")
    output_func("按顺序选择性别、场景和发型，系统会输出一整段可直接使用的提示词。")

    gender = _prompt_choice(
        title="请选择人物性别：",
        options=[(value, label, f"显示 {label}发型库") for value, label in GENDER_CHOICES],
        input_func=input_func,
        output_func=output_func,
    )
    scene_id = _prompt_choice(
        title="请选择场景：",
        options=_record_options("scene"),
        input_func=input_func,
        output_func=output_func,
    )
    hairstyle_id = _prompt_choice(
        title="请选择发型：",
        options=_record_options("hairstyle", gender=gender),
        input_func=input_func,
        output_func=output_func,
    )

    prompt = render_prompt(scene_id, hairstyle_id)
    output_func("")
    output_func("生成结果：")
    output_func(prompt)
    output_func("")
    output_func(
        f"也可以直接复用命令：PYTHONPATH=src python3 -m faceprompt.cli render --scene {scene_id} --hairstyle {hairstyle_id}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "summary":
        summary = catalog_summary()
        for key, value in summary.items():
            print(f"{key}: {value}")
        return 0

    if args.command == "validate":
        errors = validate_catalog()
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print("catalog validation passed")
        return 0

    if args.command == "list":
        records = list_records(
            category=args.category,
            gender=args.gender,
            style_line=args.style_line,
        )
        for record in records:
            print(
                f"{record.id}\t{record.categoryType}\t{record.gender}\t"
                f"{record.styleLine}\t{record.title}"
            )
        return 0

    if args.command == "render":
        render_kwargs = {
            "outfit_override": args.outfit,
            "expression_override": args.expression,
            "subject_action_override": args.subject_action,
            "hairstyle_action_override": args.hairstyle_action,
            "seed_source": args.seed_source,
        }
        print(
            render_prompt(
                args.scene,
                args.hairstyle,
                **render_kwargs,
            )
        )
        return 0

    if args.command == "interactive":
        return run_interactive()

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
