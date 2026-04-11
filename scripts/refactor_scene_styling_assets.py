from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIRS = (
    ROOT / "backend" / "app" / "data" / "faceprompt",
    ROOT / "Faceprompt" / "src" / "faceprompt" / "data",
)


REALISTIC_DEFAULT_STYLINGS = [
    "female-natural-soft-glow",
    "male-clean-natural-grooming",
    "unisex-natural-soft",
]
REALISTIC_FALLBACK_STYLINGS = ["unisex-natural-soft"]
REALISTIC_FORBIDDEN_STYLINGS = [
    "female-minimal-editorial",
    "male-sharp-editorial",
    "unisex-structured-editorial",
]
FASHION_DEFAULT_STYLINGS = [
    "female-minimal-editorial",
    "male-sharp-editorial",
    "unisex-structured-editorial",
]
FASHION_FALLBACK_STYLINGS = ["unisex-structured-editorial"]
FASHION_FORBIDDEN_STYLINGS = [
    "female-natural-soft-glow",
    "female-evening-film-glow",
    "male-clean-natural-grooming",
    "unisex-natural-soft",
]

REALISTIC_MAKEUP_OVERRIDE = {
    "female": "底妆轻透干净，保留真实肤色与细微纹理，眉眼柔和清楚，唇色控制在低饱和裸粉或豆沙范围内。",
    "male": "皮肤状态干净清爽，仅轻微修饰瑕疵与黑眼圈，眉毛整洁自然，保留真实男性气质。",
}
FASHION_MAKEUP_OVERRIDE = {
    "female": "底妆干净利落，轮廓轻度提炼，眼妆与唇色有存在感但仍然克制，整体高级时装化而不过重。",
    "male": "皮肤与骨相做克制修饰，眉眼结构利落清楚，不出现厚重彩妆感，整体保持高级时装肖像质感。",
}

REALISTIC_STYLING_RECOMMENDED = {
    "hotel-room-loose": ["female-evening-film-glow", "female-natural-soft-glow", "male-clean-natural-grooming"],
    "sunset-home-backlight": ["female-evening-film-glow", "female-natural-soft-glow", "male-clean-natural-grooming"],
    "rainy-window-mood": ["female-evening-film-glow", "female-natural-soft-glow", "male-clean-natural-grooming"],
    "modern-garden-backlight": ["female-natural-soft-glow", "male-clean-natural-grooming"],
    "modern-greenery-bokeh": ["female-natural-soft-glow", "male-clean-natural-grooming"],
    "modern-cherry-blossom-spring": ["female-natural-soft-glow", "female-evening-film-glow"],
    "modern-wheatfield-goldenhour": ["female-natural-soft-glow", "male-clean-natural-grooming"],
}

SCENE_CONFIG = {
    "indoor-film-lifestyle": {
        "scene_family": "modern_interior",
        "theme_tags": ["modern"],
        "setting_tags": ["indoor"],
        "season_tags": ["all_season"],
        "risk_level": "low",
        "performance_profile_ids": ["modern-candid-pause", "modern-lean-seat"],
    },
    "morning-window-softlight": {
        "scene_family": "modern_window",
        "theme_tags": ["modern"],
        "setting_tags": ["window", "indoor"],
        "season_tags": ["all_season"],
        "risk_level": "low",
        "performance_profile_ids": ["modern-still-front", "modern-hold-cup"],
    },
    "walnut-study-portrait": {
        "scene_family": "modern_study",
        "theme_tags": ["modern"],
        "setting_tags": ["study", "indoor"],
        "season_tags": ["all_season"],
        "risk_level": "low",
        "performance_profile_ids": ["modern-study-pause", "modern-still-front"],
    },
    "cafe-candid-seat": {
        "scene_family": "modern_cafe",
        "theme_tags": ["modern"],
        "setting_tags": ["cafe", "indoor"],
        "season_tags": ["all_season"],
        "risk_level": "low",
        "performance_profile_ids": ["modern-candid-pause", "modern-hold-cup"],
    },
    "bathroom-mirror-morning": {
        "scene_family": "modern_bathroom",
        "theme_tags": ["modern"],
        "setting_tags": ["bathroom", "mirror", "indoor"],
        "season_tags": ["all_season"],
        "risk_level": "medium",
        "performance_profile_ids": ["modern-still-front"],
    },
    "hotel-room-loose": {
        "scene_family": "modern_hotel",
        "theme_tags": ["modern"],
        "setting_tags": ["hotel", "indoor"],
        "season_tags": ["all_season"],
        "risk_level": "medium",
        "performance_profile_ids": ["modern-lean-seat", "modern-candid-pause"],
    },
    "sunset-home-backlight": {
        "scene_family": "modern_home",
        "theme_tags": ["modern"],
        "setting_tags": ["indoor", "window"],
        "season_tags": ["all_season"],
        "risk_level": "medium",
        "performance_profile_ids": ["modern-still-front", "modern-turn-back"],
    },
    "hallway-quiet-frame": {
        "scene_family": "modern_corridor",
        "theme_tags": ["modern"],
        "setting_tags": ["corridor", "indoor"],
        "season_tags": ["all_season"],
        "risk_level": "medium",
        "performance_profile_ids": ["modern-still-front"],
    },
    "rainy-window-mood": {
        "scene_family": "modern_window",
        "theme_tags": ["modern", "seasonal"],
        "setting_tags": ["window", "indoor", "rain"],
        "season_tags": ["all_season"],
        "risk_level": "medium",
        "performance_profile_ids": ["modern-still-front", "modern-turn-back"],
    },
    "studio-solid-backdrop": {
        "scene_family": "modern_studio",
        "theme_tags": ["modern"],
        "setting_tags": ["studio"],
        "season_tags": ["all_season"],
        "risk_level": "low",
        "performance_profile_ids": ["modern-editorial-strong"],
    },
    "retro-cinema-box": {
        "scene_family": "modern_stage",
        "theme_tags": ["modern"],
        "setting_tags": ["stage", "indoor"],
        "season_tags": ["all_season"],
        "risk_level": "medium",
        "performance_profile_ids": ["modern-editorial-seat"],
    },
    "city-neon-night": {
        "scene_family": "modern_city",
        "theme_tags": ["modern"],
        "setting_tags": ["night", "city"],
        "season_tags": ["all_season"],
        "risk_level": "high",
        "performance_profile_ids": ["modern-editorial-strong"],
    },
    "gallery-white-cube": {
        "scene_family": "modern_gallery",
        "theme_tags": ["modern"],
        "setting_tags": ["studio", "indoor"],
        "season_tags": ["all_season"],
        "risk_level": "medium",
        "performance_profile_ids": ["modern-editorial-strong"],
    },
    "dramatic-side-light": {
        "scene_family": "modern_studio",
        "theme_tags": ["modern"],
        "setting_tags": ["studio"],
        "season_tags": ["all_season"],
        "risk_level": "medium",
        "performance_profile_ids": ["modern-editorial-strong"],
    },
    "rooftop-wind": {
        "scene_family": "modern_rooftop",
        "theme_tags": ["modern"],
        "setting_tags": ["rooftop"],
        "season_tags": ["all_season"],
        "risk_level": "high",
        "performance_profile_ids": ["modern-editorial-strong", "modern-turn-back"],
    },
    "moody-bar-counter": {
        "scene_family": "modern_bar",
        "theme_tags": ["modern"],
        "setting_tags": ["bar", "indoor"],
        "season_tags": ["all_season"],
        "risk_level": "high",
        "performance_profile_ids": ["modern-editorial-seat"],
    },
    "backstage-vanity-mirror": {
        "scene_family": "modern_backstage",
        "theme_tags": ["modern"],
        "setting_tags": ["mirror", "stage", "indoor"],
        "season_tags": ["all_season"],
        "risk_level": "high",
        "performance_profile_ids": ["modern-editorial-seat"],
    },
    "scene-35aef68d": {
        "new_id": "modern-garden-backlight",
        "new_title": "绿植花园逆光人像",
        "scene_family": "modern_garden",
        "theme_tags": ["modern"],
        "setting_tags": ["garden"],
        "season_tags": ["spring", "summer"],
        "risk_level": "low",
        "performance_profile_ids": ["modern-outdoor-natural"],
    },
    "scene-98033eb1": {
        "new_id": "modern-bar-flash",
        "new_title": "暗调酒馆直闪人像",
        "scene_family": "modern_bar",
        "theme_tags": ["modern"],
        "setting_tags": ["bar", "indoor"],
        "season_tags": ["all_season"],
        "risk_level": "high",
        "performance_profile_ids": ["modern-editorial-seat"],
    },
    "scene-41e220d6": {
        "new_id": "modern-wheatfield-goldenhour",
        "new_title": "麦田黄金时刻人像",
        "scene_family": "modern_field",
        "theme_tags": ["modern", "seasonal"],
        "setting_tags": ["field", "outdoor"],
        "season_tags": ["summer", "autumn"],
        "risk_level": "low",
        "performance_profile_ids": ["modern-outdoor-natural"],
    },
    "green-outdoor-b9edbc24": {
        "new_id": "modern-greenery-bokeh",
        "new_title": "绿意光斑清新人像",
        "scene_family": "modern_garden",
        "theme_tags": ["modern", "seasonal"],
        "setting_tags": ["garden", "outdoor"],
        "season_tags": ["spring", "summer"],
        "risk_level": "medium",
        "performance_profile_ids": ["modern-outdoor-natural"],
    },
    "scene-473e9e49": {
        "new_id": "modern-cherry-blossom-spring",
        "new_title": "春日樱花回眸人像",
        "scene_family": "modern_garden",
        "theme_tags": ["modern", "seasonal"],
        "setting_tags": ["garden", "outdoor"],
        "season_tags": ["spring"],
        "risk_level": "medium",
        "performance_profile_ids": ["modern-turn-back"],
    },
}

STYLING_CONFIG = {
    "female-natural-soft-glow": {
        "profile_id": "female_modern_daily_soft",
        "profile_label": "女性现代日常柔光",
        "theme_tags": ["modern"],
        "tone_tags": ["natural"],
        "supported_scene_families": [
            "modern_interior", "modern_window", "modern_study", "modern_cafe", "modern_bathroom", "modern_hotel", "modern_home", "modern_corridor", "modern_garden", "modern_field",
        ],
        "base_makeup": "轻透自然底妆，修饰泛红与瑕疵，保留真实微光泽与细腻纹理",
        "lip_color": "低饱和裸粉或豆沙唇色",
        "eye_makeup": "眉形柔和整洁，眼妆干净克制，睫毛自然分明",
        "skin_finish": "清透柔光、干净自然",
        "hair_policy": "strict_lock",
        "hair_ornament": "",
        "outfit_core": "宽松衬衫、针织上衣、简洁背心或吊带",
        "outfit_material": "柔软针织、轻薄棉质、细腻棉麻",
        "outfit_palette_structured": ["米白", "奶油白", "浅灰", "浅卡其"],
        "jewelry_level": "minimal",
        "accessories": [],
    },
    "female-evening-film-glow": {
        "profile_id": "female_modern_evening_soft",
        "profile_label": "女性傍晚胶片柔光",
        "theme_tags": ["modern"],
        "tone_tags": ["natural"],
        "supported_scene_families": ["modern_hotel", "modern_home", "modern_window", "modern_garden"],
        "base_makeup": "底妆轻透但带暖调统一感，修饰暗沉与倦态，保持真实皮肤呼吸感",
        "lip_color": "低饱和玫瑰豆沙或奶茶唇色",
        "eye_makeup": "眉眼细节柔和，局部提亮克制，不做锐利时装眼妆",
        "skin_finish": "柔和胶片感、暖调通透",
        "hair_policy": "strict_lock",
        "hair_ornament": "",
        "outfit_core": "米白针织、浅卡其衬衫、裸色背心或柔软家居感上衣",
        "outfit_material": "柔软针织、轻薄棉布、松弛家居面料",
        "outfit_palette_structured": ["米白", "燕麦色", "浅卡其", "裸色"],
        "jewelry_level": "minimal",
        "accessories": [],
    },
    "male-clean-natural-grooming": {
        "profile_id": "male_clean_natural_grooming_fallback",
        "profile_label": "男性干净自然兜底",
        "theme_tags": ["modern"],
        "tone_tags": ["natural"],
        "supported_scene_families": [
            "modern_interior", "modern_window", "modern_study", "modern_cafe", "modern_bathroom", "modern_hotel", "modern_home", "modern_corridor", "modern_garden", "modern_field",
        ],
        "base_makeup": "仅做轻微底妆修饰与局部提亮，整体强调清洁感和精神状态",
        "lip_color": "嘴唇自然保湿，不额外强调颜色",
        "eye_makeup": "眉形干净整齐，不加入明显彩妆痕迹",
        "skin_finish": "干净清爽、真实细节适度保留",
        "hair_policy": "strict_lock",
        "hair_ornament": "",
        "outfit_core": "基础色衬衫、针织或简洁 T 恤",
        "outfit_material": "棉质、细针织、轻薄基础面料",
        "outfit_palette_structured": ["白色", "浅灰", "深灰", "卡其"],
        "jewelry_level": "minimal",
        "accessories": [],
    },
    "female-minimal-editorial": {
        "profile_id": "female_modern_editorial_structured",
        "profile_label": "女性现代极简时装",
        "theme_tags": ["modern"],
        "tone_tags": ["fashion"],
        "supported_scene_families": [
            "modern_studio", "modern_stage", "modern_gallery", "modern_city", "modern_rooftop", "modern_bar", "modern_backstage",
        ],
        "base_makeup": "底妆平整高级，结构清晰，轮廓修饰克制而精准",
        "lip_color": "低饱和裸棕、烟粉或冷调豆沙唇色",
        "eye_makeup": "眼妆利落克制，眉眼线条更干净，强调骨相与镜头可读性",
        "skin_finish": "高级半哑光、干净清晰",
        "hair_policy": "strict_lock",
        "hair_ornament": "",
        "outfit_core": "极简利落上衣、修身针织、结构型时装单品",
        "outfit_material": "细腻针织、哑光缎面、结构化时装面料",
        "outfit_palette_structured": ["黑色", "灰白", "冷棕", "酒红"],
        "jewelry_level": "controlled",
        "accessories": ["细项链", "简洁戒指"],
    },
    "male-sharp-editorial": {
        "profile_id": "male_sharp_editorial_fallback",
        "profile_label": "男性利落时装兜底",
        "theme_tags": ["modern"],
        "tone_tags": ["fashion"],
        "supported_scene_families": [
            "modern_studio", "modern_stage", "modern_gallery", "modern_city", "modern_rooftop", "modern_bar", "modern_backstage",
        ],
        "base_makeup": "皮肤与骨相做克制修饰，重点是利落和镜头识别度",
        "lip_color": "嘴唇自然轻润，不额外强调颜色",
        "eye_makeup": "眉眼结构更清晰，避免明显彩妆痕迹",
        "skin_finish": "清晰半哑光、骨相立体",
        "hair_policy": "strict_lock",
        "hair_ornament": "",
        "outfit_core": "利落衬衫、结构外套、简洁高领或深色针织",
        "outfit_material": "西装面料、挺括棉布、哑光针织",
        "outfit_palette_structured": ["黑色", "深灰", "冷棕", "酒红"],
        "jewelry_level": "minimal",
        "accessories": [],
    },
    "unisex-natural-soft": {
        "profile_id": "unisex_natural_soft_fallback",
        "profile_label": "通用自然软光兜底",
        "theme_tags": ["modern"],
        "tone_tags": ["natural"],
        "supported_scene_families": [
            "modern_interior", "modern_window", "modern_study", "modern_cafe", "modern_bathroom", "modern_hotel", "modern_home", "modern_corridor", "modern_garden", "modern_field",
        ],
        "base_makeup": "以真实干净为第一优先级，底妆轻薄，修饰瑕疵但保留人物真实感",
        "lip_color": "唇色保持自然低饱和",
        "eye_makeup": "眉眼干净整洁，不额外叠加强存在感彩妆",
        "skin_finish": "自然柔光、纹理可读",
        "hair_policy": "strict_lock",
        "hair_ornament": "",
        "outfit_core": "低饱和、简洁、生活化上衣",
        "outfit_material": "棉布、针织、轻薄基础面料",
        "outfit_palette_structured": ["白色", "米白", "浅灰", "卡其"],
        "jewelry_level": "minimal",
        "accessories": [],
    },
    "unisex-structured-editorial": {
        "profile_id": "unisex_structured_editorial_fallback",
        "profile_label": "通用结构时装兜底",
        "theme_tags": ["modern"],
        "tone_tags": ["fashion"],
        "supported_scene_families": [
            "modern_studio", "modern_stage", "modern_gallery", "modern_city", "modern_rooftop", "modern_bar", "modern_backstage",
        ],
        "base_makeup": "底妆平整清晰，面部结构更明确，整体呈现高级镜头质感",
        "lip_color": "唇色低饱和并服从整体时装色调",
        "eye_makeup": "眉眼轮廓干净利落，避免花哨彩妆堆叠",
        "skin_finish": "高级半哑光、清晰干净",
        "hair_policy": "strict_lock",
        "hair_ornament": "",
        "outfit_core": "结构明确的黑白灰时装单品或利落针织",
        "outfit_material": "西装面料、哑光缎面、结构针织",
        "outfit_palette_structured": ["黑色", "白色", "深灰", "冷棕"],
        "jewelry_level": "controlled",
        "accessories": ["简洁金属配饰"],
    },
}

PERFORMANCE_PROFILES = [
    {"id": "modern-still-front", "title": "现代静态正面", "summary": "适合近景写实场景的稳定正面表现。", "themeTags": ["modern"], "styleLines": ["realistic_editorial"], "compatibleSceneFamilies": ["modern_window", "modern_study", "modern_bathroom", "modern_corridor", "modern_home"], "expressionOptions": ["自然看向镜头", "安静地垂眼微笑", "温和地看镜头"], "actionOptions": ["自然站立或静止停顿", "平视镜头、肩颈轻微放松"], "gestureConstraints": ["主体动作优先，不要叠加第二套手部动作", "手部必须符合真实解剖结构，十指分明，禁止手指融合"], "bodyPoseHints": ["肩颈放松，躯干保持稳定，不要夸张扭转"], "handPropPolicy": "无明确道具需求时，不额外添加杯子、书本或花束。"},
    {"id": "modern-candid-pause", "title": "现代抓拍停顿", "summary": "适合生活化空间的轻抓拍表现。", "themeTags": ["modern"], "styleLines": ["realistic_editorial"], "compatibleSceneFamilies": ["modern_interior", "modern_cafe", "modern_hotel"], "expressionOptions": ["若有所思地停顿", "眼神放空", "慵懒看镜头"], "actionOptions": ["停在自然抓拍瞬间", "轻微前倾停顿", "半侧身放松停顿"], "gestureConstraints": ["动作必须像抓拍截帧，不做刻意摆拍", "不要叠加抓头发、拨头发这类额外手部动作"], "bodyPoseHints": ["重心自然落在一侧，肩线略有倾斜但不要变形"], "handPropPolicy": "只有当场景明确提供桌面或坐具时，才允许少量手部支撑动作。"},
    {"id": "modern-lean-seat", "title": "现代倚靠坐姿", "summary": "适合椅背、沙发、床边等有依靠面的松弛表现。", "themeTags": ["modern"], "styleLines": ["realistic_editorial"], "compatibleSceneFamilies": ["modern_interior", "modern_hotel", "modern_home"], "expressionOptions": ["神情松弛", "轻轻走神", "温和地看向镜头"], "actionOptions": ["靠在椅背上微侧身", "靠坐在椅子上微微前倾", "停在自然倚靠瞬间"], "gestureConstraints": ["动作优先体现倚靠关系，不要再叠加复杂手势", "肘部与肩颈角度要自然，不要出现反关节姿态"], "bodyPoseHints": ["依靠面要明确，腰背角度自然，不做大幅拧转"], "handPropPolicy": "如果主体动作已经占用手部，不额外叠加杯子、手机等小道具。"},
    {"id": "modern-hold-cup", "title": "现代持杯停顿", "summary": "适合窗边、咖啡馆等能自然持杯的生活化表现。", "themeTags": ["modern"], "styleLines": ["realistic_editorial"], "compatibleSceneFamilies": ["modern_window", "modern_cafe"], "expressionOptions": ["安静地垂眼微笑", "温和看向镜头", "若有所思地停顿"], "actionOptions": ["双手轻握杯子停顿", "单手扶杯看向侧前方"], "gestureConstraints": ["杯子只能作为一个主道具，不要再叠加其它手部动作", "手指要完整可读，杯子与手部接触关系自然真实"], "bodyPoseHints": ["胸肩放松，手肘角度自然，避免端杯僵硬感"], "handPropPolicy": "仅允许一个透明杯或马克杯作为主道具。"},
    {"id": "modern-study-pause", "title": "现代书房停顿", "summary": "适合书房与静物环境的知性表现。", "themeTags": ["modern"], "styleLines": ["realistic_editorial"], "compatibleSceneFamilies": ["modern_study"], "expressionOptions": ["专注后抬眼", "若有所思地轻抿嘴唇", "温和地看镜头"], "actionOptions": ["低头翻书后抬眼", "手扶椅背微侧身", "单手托住下巴短暂停顿"], "gestureConstraints": ["书本或椅背动作只保留一种，不要互相叠加", "避免高强度摆拍感，保持安静可信的知识感"], "bodyPoseHints": ["肩线平稳，头颈关系自然，动作幅度小而准确"], "handPropPolicy": "如果使用书本或椅背动作，不再叠加第二件道具。"},
    {"id": "modern-turn-back", "title": "现代回眸停顿", "summary": "适合户外或带空间纵深的回身表现。", "themeTags": ["modern", "seasonal"], "styleLines": ["realistic_editorial", "fashion_editorial"], "compatibleSceneFamilies": ["modern_home", "modern_rooftop", "modern_garden"], "expressionOptions": ["回头看向镜头", "眼神清澈温柔", "略带情绪地停顿"], "actionOptions": ["上半身轻微侧转并回头凝视镜头", "半转身停在回眸瞬间"], "gestureConstraints": ["回眸动作只保留一个主方向，不要叠加大幅手臂动作", "肩颈与脖子线条必须干净，不要因为动作制造不合理褶皱或遮挡"], "bodyPoseHints": ["转身幅度控制在半身范围内，重心稳定，肩颈线条清楚"], "handPropPolicy": "无必要时不要加道具，优先保证回眸主动作完整。"},
    {"id": "modern-outdoor-natural", "title": "现代户外自然", "summary": "适合花园、麦田、绿意等户外自然场景。", "themeTags": ["modern", "seasonal"], "styleLines": ["realistic_editorial"], "compatibleSceneFamilies": ["modern_garden", "modern_field"], "expressionOptions": ["温柔微笑", "平静直视镜头", "神态自然灵动"], "actionOptions": ["静静地站在场景中", "身体微微侧向镜头", "轻松站立停顿"], "gestureConstraints": ["动作保持轻盈自然，不要做夸张肢体摆拍", "若带花束或包袋，只保留一组稳定手部关系"], "bodyPoseHints": ["肩线舒展，肢体轻松，保留自然呼吸感"], "handPropPolicy": "只有当场景明确需要花束、包袋时才加入，并确保主体仍然是人物。"},
    {"id": "modern-editorial-strong", "title": "现代强结构时装", "summary": "适合高反差、强布光和空间感明确的时装场景。", "themeTags": ["modern"], "styleLines": ["fashion_editorial"], "compatibleSceneFamilies": ["modern_studio", "modern_city", "modern_gallery", "modern_rooftop"], "expressionOptions": ["平静直视镜头", "冷静停顿", "神情克制但有张力"], "actionOptions": ["正面站立定格", "半侧身停在镜头前", "肩颈轻微转向形成结构线"], "gestureConstraints": ["动作必须服务轮廓，不要加入生活化零碎小动作", "手部只允许一组简单清晰姿态，禁止手指融合和重复"], "bodyPoseHints": ["肩线和颈线要干净利落，姿态稳定，强调结构可读性"], "handPropPolicy": "无明确道具需求时，不添加任何手持物。"},
    {"id": "modern-editorial-seat", "title": "现代时装坐姿", "summary": "适合酒吧、后台、戏台或暗场空间的时装坐姿表现。", "themeTags": ["modern"], "styleLines": ["fashion_editorial"], "compatibleSceneFamilies": ["modern_stage", "modern_bar", "modern_backstage"], "expressionOptions": ["平静直视", "带轻微疏离感", "专注而克制"], "actionOptions": ["端坐桌前停顿", "坐在镜前微侧身", "坐姿支撑上半身形成稳定轮廓"], "gestureConstraints": ["坐姿以轮廓清晰为主，不叠加第二组手部动作", "若有杯子、镜前灯等元素，只保留单一明确关系"], "bodyPoseHints": ["上半身挺拔但不要僵硬，肩颈角度清楚，坐姿结构完整"], "handPropPolicy": "允许一个主道具，但必须保证手部和道具关系自然、十指分明。"},
    {"id": "guofeng-still-front", "title": "国风静态正面", "summary": "国风基础静态表现。", "themeTags": ["guofeng"], "styleLines": ["realistic_editorial", "fashion_editorial"], "compatibleSceneFamilies": [], "expressionOptions": ["安静看向镜头", "含蓄垂眼停顿"], "actionOptions": ["自然静立", "半身停顿"], "gestureConstraints": ["动作克制，不做现代生活化手势"], "bodyPoseHints": ["姿态端正但不僵硬，保留东方含蓄感"], "handPropPolicy": "无道具时保持手部简洁，不额外制造复杂动作。"},
    {"id": "guofeng-turn-back", "title": "国风回身回眸", "summary": "国风回身动作。", "themeTags": ["guofeng"], "styleLines": ["realistic_editorial", "fashion_editorial"], "compatibleSceneFamilies": [], "expressionOptions": ["含蓄回眸", "静静回望"], "actionOptions": ["半转身回眸停顿"], "gestureConstraints": ["回身动作轻缓，不叠加多余手部动作"], "bodyPoseHints": ["衣摆和身体方向统一，动作不要过猛"], "handPropPolicy": "无明确道具时保持手部低存在感。"},
    {"id": "guofeng-hold-fan", "title": "国风执扇", "summary": "国风执扇动作。", "themeTags": ["guofeng"], "styleLines": ["realistic_editorial", "fashion_editorial"], "compatibleSceneFamilies": [], "expressionOptions": ["低眉停顿", "安静看向镜头"], "actionOptions": ["单手执扇停顿"], "gestureConstraints": ["扇子只能作为唯一主道具，不叠加其它手部动作"], "bodyPoseHints": ["手臂角度自然，扇子与脸部保持合理距离"], "handPropPolicy": "仅允许一把扇子作为主道具。"},
    {"id": "guofeng-hold-book", "title": "国风持书", "summary": "国风持书动作。", "themeTags": ["guofeng"], "styleLines": ["realistic_editorial", "fashion_editorial"], "compatibleSceneFamilies": [], "expressionOptions": ["若有所思", "安静垂眼"], "actionOptions": ["双手持书停顿", "单手扶书回看镜头"], "gestureConstraints": ["书本只能作为唯一主道具，不叠加其它手部动作"], "bodyPoseHints": ["书本与身体关系稳定，不要悬空错位"], "handPropPolicy": "仅允许一本书作为主道具。"},
    {"id": "guofeng-hold-umbrella", "title": "国风执伞", "summary": "国风执伞动作。", "themeTags": ["guofeng"], "styleLines": ["realistic_editorial", "fashion_editorial"], "compatibleSceneFamilies": [], "expressionOptions": ["含蓄停顿", "安静回望"], "actionOptions": ["单手执伞停顿"], "gestureConstraints": ["伞只能作为唯一主道具，手部关系必须自然稳定"], "bodyPoseHints": ["伞柄方向明确，手臂与肩线不要扭曲"], "handPropPolicy": "仅允许一把伞作为主道具。"},
    {"id": "guofeng-lean-rail", "title": "国风倚栏", "summary": "国风倚栏动作。", "themeTags": ["guofeng"], "styleLines": ["realistic_editorial", "fashion_editorial"], "compatibleSceneFamilies": [], "expressionOptions": ["若有所思", "安静侧望"], "actionOptions": ["轻倚栏杆停顿"], "gestureConstraints": ["倚靠关系明确，不叠加第二组手部动作"], "bodyPoseHints": ["身体和栏杆关系自然，肩线舒展"], "handPropPolicy": "以栏杆支撑为主，不再叠加其它道具。"},
    {"id": "guofeng-slow-walk", "title": "国风缓步", "summary": "国风缓步动作。", "themeTags": ["guofeng"], "styleLines": ["realistic_editorial", "fashion_editorial"], "compatibleSceneFamilies": [], "expressionOptions": ["安静前行", "轻微回看"], "actionOptions": ["缓步前行定格"], "gestureConstraints": ["动作节奏轻缓，不允许奔跑或大幅摆臂"], "bodyPoseHints": ["步态轻稳，衣摆和身体方向协调"], "handPropPolicy": "如无必要不加道具，优先保持步态干净。"},
]

def _read_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))

def _write_json(path: Path, payload: list[dict]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def _dedupe(items):
    seen = set()
    result = []
    for item in items:
        cleaned = str(item).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result

def _scene_style_defaults(scene):
    if scene["styleLine"] == "fashion_editorial":
        return list(FASHION_DEFAULT_STYLINGS), list(FASHION_FALLBACK_STYLINGS), list(FASHION_FORBIDDEN_STYLINGS)
    return list(REALISTIC_DEFAULT_STYLINGS), list(REALISTIC_FALLBACK_STYLINGS), list(REALISTIC_FORBIDDEN_STYLINGS)

def _build_scene_record(scene):
    record = deepcopy(scene)
    config = SCENE_CONFIG[scene["id"]]
    record["id"] = config.get("new_id", scene["id"])
    if config.get("new_title"):
        record["title"] = config["new_title"]
    record["sceneFamily"] = config["scene_family"]
    record["themeTags"] = config["theme_tags"]
    record["settingTags"] = config["setting_tags"]
    record["seasonTags"] = config["season_tags"]
    record["riskLevel"] = config["risk_level"]
    record["shot"] = record.get("shot") or record.get("shotAdvice", "")
    record["mood"] = record.get("mood") or record.get("styleMood", "")
    record["sceneConstraints"] = _dedupe(record.get("sceneConstraints") or record.get("constraints") or [])
    record["performanceProfileIds"] = config["performance_profile_ids"]
    return record

def _build_styling_record(styling):
    record = deepcopy(styling)
    config = STYLING_CONFIG[styling["id"]]
    record["profileId"] = config["profile_id"]
    record["profileLabel"] = config["profile_label"]
    record["themeTags"] = config["theme_tags"]
    record["toneTags"] = config["tone_tags"]
    record["supportedSceneFamilies"] = config["supported_scene_families"]
    record["baseMakeup"] = config["base_makeup"]
    record["lipColor"] = config["lip_color"]
    record["eyeMakeup"] = config["eye_makeup"]
    record["skinFinish"] = config["skin_finish"]
    record["hairPolicy"] = config["hair_policy"]
    record["hairOrnament"] = config["hair_ornament"]
    record["outfitCore"] = config["outfit_core"]
    record["outfitMaterial"] = config["outfit_material"]
    record["outfitPaletteStructured"] = config["outfit_palette_structured"]
    record["jewelryLevel"] = config["jewelry_level"]
    record["accessories"] = config["accessories"]
    record["stylingConstraints"] = _dedupe(record.get("stylingConstraints") or record.get("constraints") or [])
    return record

def _default_rule_from_scene(scene):
    scene_id = scene["id"]
    default_stylings, fallback_stylings, forbidden_stylings = _scene_style_defaults(scene)
    recommended_stylings = REALISTIC_STYLING_RECOMMENDED.get(scene_id, default_stylings)
    default_performance = scene.get("performanceProfileIds") or []
    required_tags = _dedupe([*scene.get("settingTags", []), *scene.get("outfitPalette", [])])[:4]
    forbidden_tags = _dedupe(scene.get("outfitAvoids", []))[:4]
    outfit_hint = _dedupe(scene.get("outfitHints", []))
    lighting_adjustment = _dedupe(scene.get("constraints", []))[:2]
    makeup_override = FASHION_MAKEUP_OVERRIDE if scene["styleLine"] == "fashion_editorial" else REALISTIC_MAKEUP_OVERRIDE
    return {
        "sceneId": scene_id,
        "sceneFamily": scene["sceneFamily"],
        "defaultStylingId": default_stylings[0] if default_stylings else "",
        "defaultStylingIds": default_stylings,
        "recommendedStylingIds": recommended_stylings,
        "fallbackStylingIds": fallback_stylings,
        "forbiddenStylingIds": forbidden_stylings,
        "allowedStylingIds": _dedupe([*default_stylings, *recommended_stylings, *fallback_stylings]),
        "genderStylingIds": ({"female": "female-minimal-editorial", "male": "male-sharp-editorial"} if scene["styleLine"] == "fashion_editorial" else {"female": "female-natural-soft-glow", "male": "male-clean-natural-grooming"}),
        "makeupOverride": makeup_override,
        "outfitOverride": {"default": outfit_hint[0]} if outfit_hint else None,
        "stylingConstraintAdditions": {"default": _dedupe(scene.get("constraints", []))[:2]},
        "stylingConstraints": _dedupe(scene.get("constraints", []))[:2],
        "lightingGuardrails": lighting_adjustment,
        "lightingAdjustment": lighting_adjustment,
        "recommendedHairstyleCategoryKeys": {},
        "requiredOutfitTags": required_tags,
        "forbiddenOutfitTags": forbidden_tags,
        "defaultPerformanceIds": default_performance[:1],
        "recommendedPerformanceIds": default_performance,
        "forbiddenPerformanceIds": [],
        "hairPolicyOverride": "strict_lock",
        "themeCompatibility": scene.get("themeTags", []),
        "settingCompatibility": scene.get("settingTags", []),
    }

def _build_rule_records(scenes, rules):
    original_rule_map = {rule["sceneId"]: deepcopy(rule) for rule in rules}
    renamed_scene_map = {old_id: config.get("new_id", old_id) for old_id, config in SCENE_CONFIG.items()}
    updated_rules = []
    for scene in scenes:
        original_scene_id = next(old_id for old_id, new_id in renamed_scene_map.items() if new_id == scene["id"])
        base_rule = original_rule_map.get(original_scene_id)
        if base_rule is None:
            rule = _default_rule_from_scene(scene)
        else:
            rule = deepcopy(base_rule)
            default_stylings, fallback_stylings, forbidden_stylings = _scene_style_defaults(scene)
            rule["sceneId"] = scene["id"]
            rule["sceneFamily"] = scene["sceneFamily"]
            rule["defaultStylingIds"] = _dedupe(rule.get("defaultStylingIds") or [rule.get("defaultStylingId")] or default_stylings) or default_stylings
            rule["fallbackStylingIds"] = _dedupe(rule.get("fallbackStylingIds") or fallback_stylings)
            rule["forbiddenStylingIds"] = _dedupe(rule.get("forbiddenStylingIds") or forbidden_stylings)
            rule["recommendedStylingIds"] = _dedupe(rule.get("recommendedStylingIds") or REALISTIC_STYLING_RECOMMENDED.get(scene["id"], rule.get("defaultStylingIds") or default_stylings))
            rule["defaultPerformanceIds"] = _dedupe(rule.get("defaultPerformanceIds") or (scene.get("performanceProfileIds") or [])[:1])
            rule["recommendedPerformanceIds"] = _dedupe(rule.get("recommendedPerformanceIds") or scene.get("performanceProfileIds") or [])
            rule["forbiddenPerformanceIds"] = _dedupe(rule.get("forbiddenPerformanceIds") or [])
            rule["hairPolicyOverride"] = str(rule.get("hairPolicyOverride") or "strict_lock")
            rule["themeCompatibility"] = _dedupe(rule.get("themeCompatibility") or scene.get("themeTags") or [])
            rule["settingCompatibility"] = _dedupe(rule.get("settingCompatibility") or scene.get("settingTags") or [])
            rule["requiredOutfitTags"] = _dedupe(rule.get("requiredOutfitTags") or scene.get("outfitPalette") or [])[:4]
            rule["forbiddenOutfitTags"] = _dedupe(rule.get("forbiddenOutfitTags") or scene.get("outfitAvoids") or [])[:4]
        updated_rules.append(rule)
    return updated_rules

def transform_directory(data_dir: Path):
    scenes = _read_json(data_dir / "scenes.json")
    stylings = _read_json(data_dir / "stylings.json")
    rules = _read_json(data_dir / "scene_styling_rules.json")
    updated_scenes = [_build_scene_record(scene) for scene in scenes]
    updated_stylings = [_build_styling_record(styling) for styling in stylings]
    updated_rules = _build_rule_records(updated_scenes, rules)
    _write_json(data_dir / "scenes.json", updated_scenes)
    _write_json(data_dir / "stylings.json", updated_stylings)
    _write_json(data_dir / "scene_styling_rules.json", updated_rules)
    _write_json(data_dir / "performance_profiles.json", PERFORMANCE_PROFILES)

def main():
    for data_dir in DATA_DIRS:
        transform_directory(data_dir)
        print(f"[scene_styling_refactor] updated {data_dir}")

if __name__ == "__main__":
    main()
