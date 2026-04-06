from __future__ import annotations

import json
import shutil
from pathlib import Path

SOURCE_DIR = Path('Faceprompt/src/faceprompt/data')
BACKEND_DIR = Path('backend/app/data/faceprompt')
FILES_TO_SYNC = (
    'hairstyle_structures_male.json',
    'hairstyle_modifiers_male.json',
    'hairstyle_techniques_male.json',
    'hairstyle_presets_male.json',
)

REFINED_TECHNIQUES = {
    'male-texture-perm': {
        'promptAddition': '在不改变主结构的前提下，叠加纹理烫效果：整体加入柔和、自然的弯曲纹理，重点增强头顶与前区的走向感和层次感，不做明显卷束；发根保持适度支撑，发尾自然回落，两侧和后区继续服从原结构收短关系，整体蓬松、干净、自然。',
        'hair_tail_finish': '发根保持适度支撑，发尾自然回落，两侧和后区继续服从原结构收短关系，整体收口干净自然',
    },
    'male-air-cushion-perm': {
        'promptAddition': '在不改变主结构的前提下，叠加气垫烫效果：重点提升发根支撑和顶部蓬松度，形成自然高颅顶和轻微头包脸轮廓；前区与顶部带柔和弯曲纹理，但不出现明显小卷束感，两侧和后区继续保持整洁收短，整体走向轻盈自然。',
        'hair_tail_finish': '发尾收口与整体轮廓保持一致，发根支撑清楚但不要形成僵硬炸蓬效果',
    },
    'male-root-lift-perm': {
        'promptAddition': '在不改变主结构的前提下，叠加定位烫效果：重点增加发根支撑和头顶轮廓定型，顶部与前区形成自然蓬松弧度，但不做明显卷束；发尾保持轻微弯曲后自然回落，两侧和后区继续整洁收短，整体线条自然服帖又不塌。',
        'hair_tail_finish': '发尾保持轻微弯曲后自然回落，整体收尾服帖干净，不要出现刻意卷束',
    },
    'male-clip-perm': {
        'promptAddition': '在不改变主结构的前提下，叠加钢夹烫效果：通过更自然的纹理弯曲提升层次，发根被撑起，头顶保留空气感和层次感；卷束之间保持一定松散距离，不做过密条束，两侧和后区继续服从原结构的收短关系。',
        'hair_tail_finish': '发尾收口与整体轮廓保持一致，卷束间距自然松散，不要炸开或结成硬条束',
    },
    'male-tin-foil-perm': {
        'promptAddition': '在不改变主结构的前提下，叠加锡纸烫效果：整头形成细密、分明的条状螺旋卷束，卷束从发根开始立起并向外扩散，整体发量感显著提升；两侧可适度收短以控制轮廓，但不要改写原有分区和长度关系。',
        'hair_tail_finish': '发尾收口与整体轮廓保持一致，细密卷束要清楚立起但不要糊成一片',
    },
    'male-wool-perm': {
        'promptAddition': '在不改变主结构的前提下，叠加男士羊毛卷效果：从发根开始建立细小、均匀的卷度，整体发量感明显提升，头顶与两侧都带松软蓬起的复古卷束，轮廓圆润但保留空气感。',
        'hair_tail_finish': '发尾收口与整体轮廓保持一致，卷束圆润均匀，整体蓬松但不要炸开失控',
    },
    'male-french-lazy-perm': {
        'promptAddition': '在不改变主结构的前提下，叠加法式慵懒卷效果：顶部与两侧形成自然松散的弧度和轻微卷感，不追求整齐卷束；发丝之间保留空隙和自然凌乱感，前区只允许少量轻垂碎发作为氛围修饰，整体松弛、文艺、柔和。',
        'hair_tail_finish': '发尾收口与整体轮廓保持一致，卷度松散有空隙，结尾要轻而不乱',
    },
    'male-firework-perm': {
        'promptAddition': '在不改变主结构的前提下，叠加烟花烫效果：整头发丝从发根开始形成极小、极密、极蓬松的炸裂卷度，顶部和两侧都被明显撑开，整体轮廓像向外绽放的烟花，发量感极强。',
        'hair_tail_finish': '发尾收口与整体轮廓保持一致，炸裂卷度张力要清楚，但仍需保留真实发丝边界',
    },
}

GENERIC_TECHNIQUE_CONSTRAINT = '只允许改变纹理、支撑、卷度、湿感或尾部质感，不得改写主结构长度、主轮廓、分线和两侧后颈基础处理。'


def _load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def _dump_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _family_peers(structures: list[dict]) -> dict[str, list[str]]:
    groups: dict[tuple[str, str], list[dict]] = {}
    for item in structures:
        key = (str(item.get('categoryKey') or '').strip(), str(item.get('familyKey') or '').strip())
        groups.setdefault(key, []).append(item)
    result: dict[str, list[str]] = {}
    for items in groups.values():
        titles = [str(item.get('title') or '').strip() for item in items if str(item.get('title') or '').strip()]
        for item in items:
            title = str(item.get('title') or '').strip()
            peers = [candidate for candidate in titles if candidate and candidate != title][:3]
            result[str(item.get('id') or '').strip()] = peers
    return result


def refine_structures(structures: list[dict]) -> int:
    peer_map = _family_peers(structures)
    changed = 0
    for item in structures:
        constraints = [str(value).strip() for value in item.get('constraints', []) if str(value).strip()]
        if any('不得变成' in value for value in constraints):
            continue
        peers = peer_map.get(str(item.get('id') or '').strip(), [])
        if peers:
            peer_text = '、'.join(peers)
            anti_confusion = f'不得变成{peer_text}这类相邻款式，当前{item["title"]}的主结构辨识度必须保持清楚。'
        else:
            anti_confusion = f'不得偏成其他相邻发型，当前{item["title"]}的主结构辨识度必须保持清楚。'
        constraints.append(anti_confusion)
        item['constraints'] = constraints
        changed += 1
    return changed


def refine_techniques(techniques: list[dict]) -> int:
    changed = 0
    for item in techniques:
        technique_id = str(item.get('id') or '').strip()
        refined = REFINED_TECHNIQUES.get(technique_id)
        if refined is None:
            continue
        if item.get('promptAddition') != refined['promptAddition']:
            item['promptAddition'] = refined['promptAddition']
            changed += 1
        hair_shape = ((item.get('presetBlocks') or {}).get('hair_shape') or {})
        if hair_shape.get('hair_tail_finish') != refined['hair_tail_finish']:
            hair_shape['hair_tail_finish'] = refined['hair_tail_finish']
            changed += 1
        constraints = [str(value).strip() for value in item.get('constraints', []) if str(value).strip()]
        if GENERIC_TECHNIQUE_CONSTRAINT not in constraints:
            constraints.insert(0, GENERIC_TECHNIQUE_CONSTRAINT)
            item['constraints'] = constraints
            changed += 1
    return changed


def main() -> None:
    structures_path = SOURCE_DIR / 'hairstyle_structures_male.json'
    techniques_path = SOURCE_DIR / 'hairstyle_techniques_male.json'
    structures = _load_json(structures_path)
    techniques = _load_json(techniques_path)

    structure_changes = refine_structures(structures)
    technique_changes = refine_techniques(techniques)

    _dump_json(structures_path, structures)
    _dump_json(techniques_path, techniques)

    for name in FILES_TO_SYNC:
        shutil.copy2(SOURCE_DIR / name, BACKEND_DIR / name)

    print(f'structures_refined={structure_changes}')
    print(f'techniques_refined={technique_changes}')
    print('synced_to_backend=1')


if __name__ == '__main__':
    main()
