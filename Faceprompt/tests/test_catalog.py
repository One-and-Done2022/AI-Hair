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
    get_professional_hair_color,
    get_prompt_block_labels,
    get_prompt_rule_table,
    list_records,
    load_professional_hair_color_catalog,
    load_professional_hair_color_series,
    recommend_pairings,
    render_hairstyle_only_prompt,
    render_prompt,
    render_scene_only_prompt,
    validate_catalog,
)


class CatalogTests(unittest.TestCase):
    def test_summary_counts_match_plan(self) -> None:
        summary = catalog_summary()
        self.assertEqual(summary["scene_count"], 22)
        self.assertEqual(summary["hairstyle_count"], 56)
        self.assertEqual(summary["male_hairstyles"], 23)
        self.assertEqual(summary["female_hairstyles"], 33)
        self.assertEqual(summary["total_records"], 78)
        self.assertGreaterEqual(summary["structured_hairstyle_controls"], 5)
        self.assertGreaterEqual(summary["structured_scene_controls"], 10)

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
        self.assertIn("输出规格：只输出 1 张完整成片", prompt)
        self.assertIn("主发型结构：发型改为法式慵懒卷", prompt)
        self.assertIn("场景系统：构图：3:4 竖构图", prompt)
        self.assertIn("妆造系统：", prompt)
        self.assertIn("人物表现系统：人物表情固定为", prompt)
        self.assertIn("质量控制：", prompt)
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

        self.assertIn("人物表现系统：人物表情固定为", prompt)
        self.assertIn("人物动作固定为双手轻握杯子停顿。", prompt)
        self.assertNotIn("单手抓起头顶前区发束", prompt)

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
                "output_spec",
                "edit_scope",
                "hair_shape",
                "bangs",
                "hair_color",
                "scene",
                "styling",
                "subject_performance",
                "quality_control",
                "negative_constraints",
            ],
        )
        self.assertEqual(assembly.render(), render_prompt("morning-window-softlight", "male-forward-spikes", seed_source="assembly-order"))
        self.assertEqual(assembly.blocks[0].label, "身份锁定")
        self.assertEqual(assembly.blocks[3].label, "主发型结构")

    def test_prompt_block_labels_use_english_keys_and_chinese_labels(self) -> None:
        labels = get_prompt_block_labels()

        self.assertEqual(labels["identity_lock"], "身份锁定")
        self.assertEqual(labels["scene"], "场景系统")
        self.assertEqual(labels["hair_shape_lock"], "发型锁定")
        self.assertEqual(labels["hair_motion_constraint"], "风感约束")
        self.assertEqual(labels["negative_constraints"], "负面约束")

    def test_prompt_rule_table_declares_scene_only_and_hairstyle_only_boundaries(self) -> None:
        rules = get_prompt_rule_table()

        self.assertIn("scene_only", rules)
        self.assertIn("hair_only", rules)
        self.assertIn("hairstyle_only", rules)
        self.assertIn("hair_shape_lock", rules["scene_only"].required_blocks)
        self.assertIn("bangs_lock", rules["scene_only"].required_blocks)
        self.assertIn("hair_color_lock", rules["scene_only"].required_blocks)
        self.assertIn("hair_motion_constraint", rules["scene_only"].required_blocks)
        self.assertIn("hair_shape", rules["hairstyle_only"].required_blocks)
        self.assertIn("bangs", rules["hairstyle_only"].required_blocks)
        self.assertIn("hair_color", rules["hairstyle_only"].required_blocks)
        self.assertIn("hair_shape", rules["scene_only"].forbidden_blocks)
        self.assertIn("scene", rules["hairstyle_only"].forbidden_blocks)
        self.assertIn("styling", rules["hairstyle_only"].forbidden_blocks)
        self.assertIn("subject_performance", rules["hairstyle_only"].forbidden_blocks)

    def test_professional_hair_color_catalog_exposes_recommended_series(self) -> None:
        options = load_professional_hair_color_catalog(recommended_only=True)
        series = load_professional_hair_color_series(recommended_only=True)

        self.assertGreaterEqual(len(options), 10)
        self.assertTrue(all(item["is_recommended_for_generation"] for item in options))
        self.assertGreaterEqual(len(series), 4)
        self.assertTrue(any(item["id"] == "cool_mist" for item in series))

    def test_professional_hair_color_lookup_preserves_mapping(self) -> None:
        color = get_professional_hair_color("solutor-cool-mist-5-72")

        self.assertIsNotNone(color)
        self.assertEqual(color["series_name"], "烟熏冷雾系列")
        self.assertEqual(color["mapped_tone_id"], "ash_brown")
        self.assertIn("balayage", color["mapped_technique_ids"])

    def test_render_hairstyle_only_prompt_contains_identity_and_preserve_rules(self) -> None:
        prompt = render_hairstyle_only_prompt("male-forward-spikes")

        self.assertIn("只更换图中人物的发型", prompt)
        self.assertIn("编辑范围：本次仅允许修改头发系统", prompt)
        self.assertIn("主发型结构：发型改为前刺头", prompt)
        self.assertIn("刘海系统：", prompt)
        self.assertIn("发色系统：发色调整为深棕", prompt)
        self.assertIn("负面约束：不要换脸、不要改变性别表达、不要生成第二个人", prompt)

    def test_render_prompt_uses_structured_blocks_for_preset_output(self) -> None:
        prompt = render_prompt(
            "morning-window-softlight",
            "female-korean-air-cushion-perm",
            face_shape="long",
            forehead="broad",
            jawline="soft",
            cheekbone="prominent",
        )

        self.assertIn("主发型结构：", prompt)
        self.assertIn("刘海系统：", prompt)
        self.assertIn("发色系统：", prompt)
        self.assertIn("场景系统：", prompt)
        self.assertIn("人物表现系统：", prompt)

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
        self.assertIn("编辑范围：本次仅允许修改头发系统", output)
        self.assertIn("主发型结构：发型改为云朵烫", output)

    def test_render_scene_only_prompt_locks_existing_hairstyle(self) -> None:
        prompt = render_scene_only_prompt(
            "morning-window-softlight",
            seed_source="scene-only-lock",
        )

        self.assertIn("不改变人物的脸型、五官比例、眼距、鼻梁、嘴型、肤色、年龄感和整体气质和发型", prompt)
        self.assertIn("忽略原照片中的背景、原服饰、原有动作", prompt)
        self.assertIn("发型锁定：保持参考图中静态打理完成的当前主发型结构不变", prompt)
        self.assertIn("刘海锁定：保持参考图中静态完成的当前刘海状态不变", prompt)
        self.assertIn("发色锁定：保持参考图中静态完成的当前发色、明度层级与染发层次不变", prompt)
        self.assertIn("风感约束：", prompt)
        self.assertNotIn("抬手整理窗边发丝", prompt)

    def test_scene_only_assembly_uses_hair_lock_blocks(self) -> None:
        assembly = build_prompt_assembly(
            mode="scene_only",
            scene_id="walnut-study-portrait",
            seed_source="scene-only-assembly",
        )

        self.assertEqual(assembly.mode, "scene_only")
        self.assertEqual(
            [block.key for block in assembly.blocks[:7]],
            [
                "identity_lock",
                "output_spec",
                "edit_scope",
                "hair_shape_lock",
                "bangs_lock",
                "hair_color_lock",
                "hair_motion_constraint",
            ],
        )
        hair_blocks = [block.text for block in assembly.blocks if block.key == "hair_shape_lock"]
        self.assertEqual(len(hair_blocks), 1)
        self.assertIn("保持参考图中静态打理完成的当前主发型结构不变", hair_blocks[0])
        self.assertTrue(any(block.key == "bangs_lock" for block in assembly.blocks))
        self.assertTrue(any(block.key == "hair_color_lock" for block in assembly.blocks))
        motion_blocks = [block.text for block in assembly.blocks if block.key == "hair_motion_constraint"]
        self.assertEqual(len(motion_blocks), 1)
        self.assertIn("禁止风力、动作或镜头变化改变主发型结构", motion_blocks[0])


    def test_rooftop_wind_scene_only_prompt_sanitizes_hair_motion_conflicts(self) -> None:
        prompt = render_scene_only_prompt(
            "rooftop-wind",
            seed_source="catalog-rooftop-wind",
        )

        self.assertNotIn("发型动态是视觉关键", prompt)
        self.assertNotIn("突出风感发丝", prompt)
        self.assertNotIn("头部轻微转动让发丝被风掀起", prompt)
        self.assertIn("风感约束：", prompt)
        self.assertIn("风主要作用于衣角与空气流动，只允许极少量边缘碎发轻微摆动", prompt)
        self.assertIn("禁止风力、动作或镜头变化改变主发型结构", prompt)


    def test_scene_only_prompt_ignores_conflicting_subject_action_override(self) -> None:
        prompt = render_scene_only_prompt(
            "morning-window-softlight",
            subject_action_override="抬手整理窗边发丝",
            seed_source="catalog-scene-only-override",
        )

        self.assertNotIn("抬手整理窗边发丝", prompt)
        self.assertIn("人物动作固定为", prompt)

    def test_scene_only_prompt_sanitizes_dynamic_scene_lighting_language(self) -> None:
        prompt = render_scene_only_prompt(
            "dramatic-side-light",
            seed_source="catalog-dramatic-side-light",
        )

        self.assertNotIn("单侧硬光切过脸部和发型", prompt)
        self.assertNotIn("发丝纹理被明显勾出", prompt)
        self.assertIn("单侧硬光切过脸部与肩颈轮廓", prompt)

    def test_render_scene_only_command_prints_prompt(self) -> None:
        stdout = StringIO()
        with patch("sys.stdout", stdout):
            exit_code = main(["render-scene-only", "--scene", "walnut-study-portrait"])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("主体必须始终是同一位单人肖像，仅对场景、动作、表情和服装进行艺术化创作", output)
        self.assertIn("发型锁定：保持参考图中静态打理完成的当前主发型结构不变", output)

    def test_blocks_command_prints_hairstyle_only_blocks(self) -> None:
        stdout = StringIO()
        with patch("sys.stdout", stdout):
            exit_code = main(["blocks", "--mode", "hairstyle_only", "--hairstyle", "female-cloud-perm"])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("共 8 个 block：", output)
        self.assertIn("编辑范围 [edit_scope]", output)
        self.assertIn("主发型结构 [hair_shape]", output)
        self.assertIn("主发型结构：发型改为云朵烫", output)

    def test_interactive_blocks_command_prints_scene_blocks(self) -> None:
        stdout = StringIO()
        with patch("builtins.input", side_effect=["2", "1"]), patch("sys.stdout", stdout):
            exit_code = main(["interactive-blocks"])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("交互式 block 输出", output)
        self.assertIn("Block 结果：", output)
        self.assertIn("场景系统 [scene]", output)
        self.assertIn("发型锁定 [hair_shape_lock]", output)
        self.assertIn(
            "也可以直接复用命令：PYTHONPATH=src python3 -m faceprompt.cli blocks --mode scene_only --scene",
            output,
        )


if __name__ == "__main__":
    unittest.main()
