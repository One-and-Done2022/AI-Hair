from __future__ import annotations

import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from faceprompt.cli import main
from faceprompt.catalog import catalog_summary, list_records, render_prompt, validate_catalog


class CatalogTests(unittest.TestCase):
    def test_summary_counts_match_plan(self) -> None:
        summary = catalog_summary()
        self.assertEqual(summary["scene_count"], 20)
        self.assertEqual(summary["hairstyle_count"], 40)
        self.assertEqual(summary["male_hairstyles"], 20)
        self.assertEqual(summary["female_hairstyles"], 20)
        self.assertEqual(summary["total_records"], 60)

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


if __name__ == "__main__":
    unittest.main()
