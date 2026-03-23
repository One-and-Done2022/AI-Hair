from __future__ import annotations

import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from faceprompt.cli import main
from faceprompt.catalog import (
    build_prompt_assembly,
    catalog_summary,
    get_prompt_block_labels,
    get_prompt_rule_table,
    list_records,
    recommend_pairings,
    render_hairstyle_only_prompt,
    render_prompt,
    render_scene_only_prompt,
    validate_catalog,
)


class CatalogTests(unittest.TestCase):
    def test_summary_counts_match_plan(self) -> None:
        summary = catalog_summary()
        self.assertEqual(summary["scene_count"], 20)
        self.assertEqual(summary["hairstyle_count"], 40)
        self.assertEqual(summary["male_hairstyles"], 20)
        self.assertEqual(summary["female_hairstyles"], 20)
        self.assertEqual(summary["total_records"], 60)
        self.assertGreaterEqual(summary["structured_hairstyle_controls"], 6)
        self.assertGreaterEqual(summary["structured_scene_controls"], 6)

    def test_validator_passes(self) -> None:
        self.assertEqual(validate_catalog(), [])

    def test_scene_and_hairstyle_examples_exist(self) -> None:
        for record in list_records():
            self.assertTrue(record.exampleFinalPrompt.startswith("请基于上传参考图中的同一人物生成 1 张高相似度"))
            self.assertTrue(record.referenceSources)
            self.assertTrue(record.promptCore)
            self.assertTrue(record.constraints)

    def test_render_prompt_contains_core_segments(self) -> None:
        prompt = render_prompt("indoor-film-lifestyle", "female-french-lazy-waves")
        self.assertIn("请基于上传参考图中的同一人物生成 1 张高相似度、写实风格的人像写真", prompt)
        self.assertIn("第一优先级是严格保留参考人物的真实身份特征", prompt)
        self.assertIn("不改变人物的脸型、五官比例、眼距、鼻梁、嘴型、肤色、年龄感和整体气质", prompt)
        self.assertIn("不换脸，不生成第二个人", prompt)
        self.assertIn("只输出 1 张完整成片", prompt)
        self.assertIn("人物发型：发型改为法式慵懒卷", prompt)
        self.assertIn("场景：浅色墙面、胡桃木门框", prompt)
        self.assertIn("人物动作：单张图中只选择 1 种主体动作，本张图固定为：", prompt)
        self.assertIn("发型展示动作参考：", prompt)
        self.assertIn("后端每次只选 1 个主体动作", prompt)
        self.assertIn("不可以有不符合物理逻辑的身体部位", prompt)
        self.assertIn("负面约束：不要换脸、不要改变性别表达、不要生成第二个人", prompt)
        self.assertIn("不要背景杂乱", prompt)
        self.assertIn("不要过强滤镜", prompt)
        self.assertIn("不要文字水印", prompt)

    def test_render_prompt_filters_hand_conflicting_hairstyle_action(self) -> None:
        prompt = render_prompt(
            "morning-window-softlight",
            "male-forward-spikes",
            subject_action_override="双手轻握杯子停顿",
            seed_source="hand-conflict-check",
        )

        self.assertIn("人物动作：单张图中只选择 1 种主体动作，本张图固定为：双手轻握杯子停顿。", prompt)
        self.assertNotIn("固定为：单手抓起头顶前区发束。", prompt)

    def test_build_prompt_assembly_exposes_stable_block_order(self) -> None:
        assembly = build_prompt_assembly(
            mode="full_stylize",
            scene_id="morning-window-softlight",
            hairstyle_id="male-forward-spikes",
            seed_source="assembly-order",
        )

        self.assertEqual(assembly.mode, "full_stylize")
        self.assertEqual(
            [block.key for block in assembly.blocks],
            [
                "identity_lock",
                "output_format",
                "face_strategy",
                "shot",
                "scene_environment",
                "scene_lighting",
                "scene_mood",
                "scene_control",
                "expression",
                "subject_action",
                "hairstyle_action",
                "outfit",
                "hair_target",
                "scene_constraints",
                "hair_constraints",
                "motion_safety_constraints",
                "quality_skin_texture",
                "quality_image_finish",
                "negative_identity_artifact",
                "negative_physical_logic",
            ],
        )
        self.assertEqual(assembly.render(), render_prompt("morning-window-softlight", "male-forward-spikes", seed_source="assembly-order"))
        self.assertEqual(assembly.blocks[0].label, "身份锁定")
        self.assertEqual(assembly.blocks[4].label, "场景环境")

    def test_prompt_block_labels_use_english_keys_and_chinese_labels(self) -> None:
        labels = get_prompt_block_labels()

        self.assertEqual(labels["identity_lock"], "身份锁定")
        self.assertEqual(labels["scene_environment"], "场景环境")
        self.assertEqual(labels["hair_lock"], "发型锁定")
        self.assertEqual(labels["negative_physical_logic"], "物理逻辑负面约束")

    def test_prompt_rule_table_declares_scene_only_and_hairstyle_only_boundaries(self) -> None:
        rules = get_prompt_rule_table()

        self.assertIn("scene_only", rules)
        self.assertIn("hairstyle_only", rules)
        self.assertIn("hair_lock", rules["scene_only"].required_blocks)
        self.assertIn("hair_target", rules["hairstyle_only"].required_blocks)
        self.assertIn("hair_target", rules["scene_only"].forbidden_blocks)
        self.assertIn("scene_environment", rules["hairstyle_only"].forbidden_blocks)
        self.assertIn("shot", rules["hairstyle_only"].forbidden_blocks)
        self.assertIn("scene_control", rules["hairstyle_only"].forbidden_blocks)
        self.assertIn("face_strategy", rules["hairstyle_only"].forbidden_blocks)

    def test_render_hairstyle_only_prompt_contains_identity_and_preserve_rules(self) -> None:
        prompt = render_hairstyle_only_prompt("male-forward-spikes")

        self.assertIn("只更换图中人物的发型", prompt)
        self.assertIn("换发目标：只更换图中人物的发型为：前刺头。", prompt)
        self.assertIn("人物发型：发型改为前刺头", prompt)
        self.assertIn("尽量保持原图中的背景、服饰、姿态、表情、构图、镜头距离、光线和氛围不变", prompt)
        self.assertIn("不能把新发型做成悬浮假发", prompt)
        self.assertIn("负面约束：不要换脸、不要改变性别表达、不要生成第二个人", prompt)

    def test_render_prompt_includes_face_strategy_for_structured_pilot(self) -> None:
        prompt = render_prompt(
            "morning-window-softlight",
            "female-korean-air-cushion-perm",
            face_shape="long",
            forehead="broad",
            jawline="soft",
            cheekbone="prominent",
        )

        self.assertIn("脸型修饰策略：", prompt)
        self.assertIn("参考人物特征：长脸，额头偏宽，下颌线柔和，颧骨较突出", prompt)
        self.assertIn("场景控制：风力：静止无风", prompt)
        self.assertIn("适配判断：当前发型优先用于长脸", prompt)

    def test_recommend_pairings_prefers_structured_scene_and_face_match(self) -> None:
        recommendations = recommend_pairings(
            gender="female",
            face_shape="round",
            forehead="broad",
            jawline="soft",
            cheekbone="prominent",
            limit=1,
        )

        self.assertEqual(len(recommendations), 1)
        self.assertEqual(recommendations[0].hairstyleId, "female-collarbone-xinzhilei")
        self.assertEqual(recommendations[0].sceneId, "indoor-film-lifestyle")
        self.assertIn("--face-shape round", recommendations[0].exampleCommand)

    def test_recommend_command_prints_ranked_pairings(self) -> None:
        stdout = StringIO()
        with patch("sys.stdout", stdout):
            exit_code = main(
                [
                    "recommend",
                    "--gender",
                    "female",
                    "--face-shape",
                    "round",
                    "--forehead",
                    "broad",
                    "--jawline",
                    "soft",
                    "--cheekbone",
                    "prominent",
                    "--limit",
                    "2",
                ]
            )

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("发型：辛芷蕾锁骨发", output)
        self.assertIn("场景：室内生活感胶片写真", output)
        self.assertIn("命令：PYTHONPATH=src python3 -m faceprompt.cli render --scene", output)

    def test_interactive_command_renders_prompt(self) -> None:
        stdout = StringIO()
        with patch("builtins.input", side_effect=["1", "1", "1"]), patch("sys.stdout", stdout):
            exit_code = main(["interactive"])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("交互式提示词生成", output)
        self.assertIn("生成结果：", output)
        self.assertIn("请基于上传参考图中的同一人物生成 1 张高相似度、写实风格的人像写真", output)
        self.assertIn("也可以直接复用命令：PYTHONPATH=src python3 -m faceprompt.cli render --scene", output)
        self.assertIn("--hairstyle", output)

    def test_interactive_command_reprompts_invalid_choice(self) -> None:
        stdout = StringIO()
        with patch("builtins.input", side_effect=["0", "2", "1", "1"]), patch("sys.stdout", stdout):
            exit_code = main(["interactive"])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("请输入有效编号。", output)

    def test_render_hairstyle_only_command_prints_prompt(self) -> None:
        stdout = StringIO()
        with patch("sys.stdout", stdout):
            exit_code = main(["render-hairstyle-only", "--hairstyle", "female-cloud-perm"])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("换发目标：只更换图中人物的发型为：云朵烫。", output)
        self.assertIn("人物发型：发型改为云朵烫", output)

    def test_render_scene_only_prompt_locks_existing_hairstyle(self) -> None:
        prompt = render_scene_only_prompt(
            "morning-window-softlight",
            seed_source="scene-only-lock",
        )

        self.assertIn("不改变人物的脸型、五官比例、眼距、鼻梁、嘴型、肤色、年龄感和整体气质和发型", prompt)
        self.assertIn("忽略原照片中的背景、原服饰、原有动作", prompt)
        self.assertIn("人物发型：保持参考图中已经生成完成的发型不变", prompt)
        self.assertIn("不要因为动作、风感或镜头变化把当前发型改成另一种发型", prompt)
        self.assertNotIn("抬手整理窗边发丝", prompt)

    def test_scene_only_assembly_uses_hair_lock_block(self) -> None:
        assembly = build_prompt_assembly(
            mode="scene_only",
            scene_id="walnut-study-portrait",
            seed_source="scene-only-assembly",
        )

        self.assertEqual(assembly.mode, "scene_only")
        hair_blocks = [block.text for block in assembly.blocks if block.key == "hair_lock"]
        self.assertEqual(len(hair_blocks), 1)
        self.assertIn("保持参考图中已经生成完成的发型不变", hair_blocks[0])

    def test_render_scene_only_command_prints_prompt(self) -> None:
        stdout = StringIO()
        with patch("sys.stdout", stdout):
            exit_code = main(["render-scene-only", "--scene", "walnut-study-portrait"])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("主体必须始终是同一位单人肖像，仅对场景、动作、表情和服装进行艺术化创作", output)
        self.assertIn("人物发型：保持参考图中已经生成完成的发型不变", output)


if __name__ == "__main__":
    unittest.main()
