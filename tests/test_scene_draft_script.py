from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT_DIR / "scripts" / "add_scene_draft.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("add_scene_draft", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _build_scene_payload(scene_id: str = "window-softlight-demo") -> dict:
    return {
        "scene_draft": {
            "id": scene_id,
            "title": "窗边自然光人像",
            "styleLine": "realistic_editorial",
            "summary": "窗边自然光与留白背景构成稳定的生活化人像环境。",
            "environment": "室内留白墙面与木质家具背景，窗边区域干净克制。",
            "lighting": "窗边柔和自然光从侧前方进入，整体亮部通透。",
            "lightingProfile": {
                "lightDirection": "side",
                "lightQuality": "soft",
                "colorTemperature": "neutral",
                "contrastLevel": "low",
                "shadowDensity": "light",
                "hairHighlightMode": "soft_edge",
                "skinRendering": "soft_texture",
                "exposureBias": "slightly_over",
                "practicalLightsAllowed": False,
            },
            "styleMood": "安静、松弛、生活感高级。",
            "detailTags": ["室内", "窗边", "自然光"],
            "expressions": ["温和看向镜头"],
            "actions": ["靠坐在椅子上轻微侧身"],
            "outfitHints": ["米白色针织上衣"],
            "outfitPalette": ["白色", "浅灰", "米白"],
            "outfitMaterials": ["轻薄棉质", "柔软针织"],
            "outfitShapes": ["宽松衬衫", "简洁背心"],
            "outfitAvoids": ["高饱和撞色", "复杂配饰"],
            "pairingAdvice": ["法式慵懒卷", "蓬松锁骨发"],
            "shotAdvice": "3:4 竖构图，胸口以上近景，平视镜头。",
            "constraints": ["背景保持简洁留白", "不要加入复杂前景"],
            "controlProfile": {
                "windLevel": "still",
                "humidityLook": "balanced",
                "backgroundComplexity": "low",
                "lightingHardness": "soft",
                "mirrorRisk": "none",
                "compatibleHairstyleTags": ["lifestyle_softlight"],
            },
            "sampleImageIds": {"female": ["female3"], "male": ["male2"]},
            "referenceNotes": "由场景理解接口自动生成，建议人工复核后再入库。",
            "referenceSourceIds": ["scene-understanding-api"],
        }
    }


def test_append_scene_draft_accepts_full_api_response(tmp_path):
    module = _load_module()
    catalog_path = tmp_path / "scenes.json"
    catalog_path.write_text("[]\n", encoding="utf-8")

    appended = module.append_scene_draft(
        catalog_path=catalog_path,
        payload=_build_scene_payload(),
    )

    saved = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert appended["id"] == "window-softlight-demo"
    assert len(saved) == 1
    assert saved[0]["title"] == "窗边自然光人像"
    assert saved[0]["controlProfile"]["recommendedHairstyleIds"] == []
    assert saved[0]["lightingProfile"]["lightDirection"] == "side"
    assert saved[0]["sampleImageIds"]["female"] == ["female3"]


def test_append_scene_draft_rejects_duplicate_id(tmp_path):
    module = _load_module()
    catalog_path = tmp_path / "scenes.json"
    catalog_path.write_text(
        json.dumps([_build_scene_payload()["scene_draft"]], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    try:
        module.append_scene_draft(
            catalog_path=catalog_path,
            payload=_build_scene_payload(),
        )
    except ValueError as exc:
        assert "场景 id 已存在" in str(exc)
    else:
        raise AssertionError("expected duplicate scene id to raise ValueError")
