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

STRUCTURE_ANTI_CONFUSION = {
    'male-dimensional_forward_spike': '不得变成纹理前刺、美式前刺、凌乱抓刺这类相邻款式；必须保持更竖直的顶部支撑和干净短碎前区，不要增加明显分线或过度凌乱纹理。',
    'male-textured_forward_spike': '不得变成立体前刺、美式前刺、凌乱抓刺这类相邻款式；必须保持更密的纹理束感和上扬短束，不要做成大块厚束或无纹理直立刺。',
    'male-american_forward_spike': '不得变成纹理前刺、立体前刺、前刺老虎头这类相邻款式；必须保持低渐变贴紧两侧、前高后低和哑光 clean 轮廓，不要增加厚重顶区或过密纹理。',
    'male-messy_forward_spike': '不得变成美式前刺、立体前刺、前刺老虎头这类相邻款式；必须保持不规则松散短刺和轻遮发际线感，不要做成工整露额或顶部厚束聚拢结构。',
    'male-micro_part_forward_spike': '不得变成立体前刺、纹理前刺、韩式三七分这类相邻款式；必须保留轻微微分和两束向前上扬的前区，不要改成完全无分线前刺或标准三七分。',
    'male-tiger_head_spike': '不得变成美式前刺、凌乱抓刺、纹理前刺这类相邻款式；必须保持顶部更高更圆、前区聚拢厚束的老虎头轮廓，不要做成松散碎刺或贴头清爽前刺。',
    'male-three_seven_back_spike': '不得变成三七侧背、纹理三七分、微分前刺这类相邻款式；必须保留一侧后带、一侧上刺的混合走向，不要改成纯侧分或纯背头。',
    'male-textured_cover': '不得变成短碎栗子头、微分碎盖、基础短发这类相邻款式；必须保持轻盖额头但顶区更饱满立体，不要塌成圆短盖或普通短碎发。',
    'male-chestnut_crop': '不得变成立体碎盖、微分碎盖、基础短发这类相邻款式；必须保持圆润柔和、短碎贴额的栗子头轮廓，不要做出明显分线和过高顶区。',
    'male-micro_part_cover': '不得变成立体碎盖、短碎栗子头、微分纹理这类相邻款式；必须保留轻微分缝的碎盖前区，不要改成无分线圆盖或中分侧分结构。',
    'male-textured_side_part': '不得变成基础侧分、长纹理侧背、港风分线这类相邻款式；必须保持更长顶区、明显流向和层次，不要做成规整贴顺通勤侧分或直接后梳侧背。',
    'male-micro_middle_part': '不得变成韩式三七分、港风中长发、长纹理侧分这类相邻款式；必须保持中分或微中分打开前区、两侧自然垂落，不要改成明显侧分或真正长发披散。',
    'male-clean_side_part': '不得变成长纹理侧分、偏分三七、纹理三七分这类相邻款式；必须保持简洁干净、轻侧分、不过度纹理，不要做成氛围感长侧分或明显韩系三七。',
    'male-textured_37_part': '不得变成韩式三七分、偏分三七、三七侧分这类相邻款式；必须保持三七分线上的纹理束感和更松更立体的顶区，不要做成平顺贴服的通勤三七。',
    'male-two_eight_part': '不得变成偏分三七、基础侧分、复古油头这类相邻款式；必须保持偏分更明显、露额更多的一侧重分配，不要改成均衡三七或整齐油头。',
    'male-clean_37_part': '不得变成韩式三七分、二八侧分、基础侧分这类相邻款式；必须保持更简单、更清爽的偏三七结构，不要做成蓬松纹理韩系三七或成熟二八分。',
    'male-korean_37_part': '不得变成偏分三七、纹理三七分、三七侧分这类相邻款式；必须保持韩系三七分的自然量感和轻露额，不要做成过硬朗偏分或明显纹理束感。',
    'male-soft_37_part': '不得变成韩式三七分、长刘海侧背、微分纹理这类相邻款式；必须保持三七分后向侧前自然垂落和更柔和的修脸前区，不要变成后梳侧背或中分垂落。',
    'male-hongkong_parted_style': '不得变成长纹理侧分、港风中长发、复古油头这类相邻款式；必须保持复古松弛、不太服帖的分线轮廓，不要做成现代通勤侧分或真正中长发披落。',
    'male-textured_slick_back': '不得变成复古油头、蓬松侧背、龙须背头这类相邻款式；必须保持后梳但保留空气纹理，不要变成高光整齐油头或前区保留明显碎发。',
    'male-three_seven_side_back': '不得变成纹理三七分、四六分侧背、龙须背头这类相邻款式；必须保持沿三七分线向侧后梳理的成熟结构，不要让前区回落成侧分刘海或保留龙须碎发。',
    'male-short_side_back': '不得变成三七侧背、基础短发、纹理背头这类相邻款式；必须保持紧凑短侧背和短前区不遮眼，不要做成普通短发或更长的侧背。',
    'male-vintage_pomade': '不得变成纹理背头、湿发侧背、港风分线这类相邻款式；必须保持规整分线、完整露额和轻光泽油头质感，不要做成蓬松纹理背头或松弛港风分线。',
    'male-long_textured_side_back': '不得变成长刘海侧背、纹理背头、港风分线这类相邻款式；必须保持更长顶区和明显流动侧后梳理，不要让前区垂落成刘海或整体收得过短。',
    'male-dragon_whisker_back': '不得变成纹理背头、三七侧背、长刘海侧背这类相邻款式；必须保留额前两三缕龙须碎发和后带主体，不要做成纯露额背头或大片长刘海。',
    'male-wet_side_back': '不得变成复古油头、纹理背头、三七侧背这类相邻款式；必须保持湿发收束和侧后梳理的湿润完成感，不要做成干爽蓬松背头或规整分线油头。',
    'male-fluffy_side_back': '不得变成纹理背头、三七侧背、龙须背头这类相邻款式；必须保持侧背方向下的高顶区空气感，不要让前区保留龙须碎发或把整体压成规整背头。',
    'male-six_four_side_back': '不得变成三七侧背、二八侧分、复古油头这类相邻款式；必须保持四六分比例和更规整成熟的侧背，不要改成强偏分侧分或高光整齐油头。',
    'male-long_fringe_side_back': '不得变成长纹理侧背、龙须背头、三七侧分这类相邻款式；必须保持侧后梳理主体下的长刘海修饰，不要变成纯背头或普通侧分。',
    'male-textured_short_foundation': '不得变成韩式小平头、短碎栗子头、立体前刺这类相邻款式；必须保持普通短发底层的轻纹理和低风险轮廓，不要做出明确前刺、盖额或平头结构。',
    'male-korean_flat_crop': '不得变成基础短发、短碎栗子头、立体碎盖这类相邻款式；必须保持极简平整短轮廓和后区整齐推短，不要做出前区碎盖或明显纹理。',
    'male-hongkong_texture': '不得变成港风中长发、港风分线、长纹理侧分这类相邻款式；必须保持港风纹理的松弛复古感，但长度仍然服从中短到中长发，不要披落成长发。',
    'male-hongkong_medium_long': '不得变成港风分线、微分纹理、长纹理侧分这类相邻款式；必须保持中长长度和松弛下垂量感，不要收短成侧分或只保留顶部长度。',
}


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
    changed = 0
    for item in structures:
        structure_id = str(item.get('id') or '').strip()
        anti_confusion = STRUCTURE_ANTI_CONFUSION.get(structure_id)
        if anti_confusion is None:
            continue
        constraints = [str(value).strip() for value in item.get('constraints', []) if str(value).strip()]
        existing_index = next(
            (
                index
                for index, value in enumerate(constraints)
                if '不得变成' in value or '不得偏成' in value
            ),
            None,
        )
        if existing_index is None:
            constraints.append(anti_confusion)
            item['constraints'] = constraints
            changed += 1
            continue
        if constraints[existing_index] != anti_confusion:
            constraints[existing_index] = anti_confusion
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
