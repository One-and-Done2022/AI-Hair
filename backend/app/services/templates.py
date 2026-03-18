from __future__ import annotations

from collections.abc import Iterable


HAIRSTYLES = [
    {
        "id": "short-texture",
        "name": "短碎发",
        "description": "轻盈层次，适合日常街拍风。",
        "prompt": "人物发型改为干净利落的短碎发，顶部保留自然纹理与轻微蓬松感，层次清晰、发丝真实，整体利落但不僵硬。",
        "palette": ("#1f4b99", "#5dd4ff"),
    },
    {
        "id": "korean-middle-part",
        "name": "韩系中分",
        "description": "柔和包裹脸型，气质偏清爽。",
        "prompt": "人物发型改为韩系中分，发丝柔顺自然，顶部保留柔和蓬松弧度，两侧顺着脸型落下但不贴头皮，气质干净清爽。",
        "palette": ("#34495e", "#89c2d9"),
    },
    {
        "id": "french-curl",
        "name": "法式卷发",
        "description": "带有随性空气感的卷度。",
        "prompt": "人物发型改为法式卷发，卷度自然松弛、富有空气感，发量真实，卷发受光自然，整体慵懒但高级。",
        "palette": ("#8e5a3c", "#f6bd60"),
    },
    {
        "id": "american-spiky",
        "name": "美式前刺",
        "description": "顶部前刺明显，轮廓更利落。",
        "prompt": "人物发型改为美式前刺。前额与头顶约 3 到 5 厘米，是整个造型的视觉核心，顶部发丝直立，具有明确刺感、方向感和层次感；两侧与后区渐变推短，长度约 1 到 2 厘米，贴合头皮，与顶部蓬松感形成清晰对比。发色为自然黑色或深棕色，少量碎发可以掠过额头和脸侧，但不能遮挡五官识别度。",
        "palette": ("#1c1c1c", "#6f4e37"),
    },
    {
        "id": "wolf-cut",
        "name": "狼尾层次",
        "description": "有层次与方向感，偏潮流感。",
        "prompt": "人物发型改为狼尾层次发型，顶部、侧区与后区层次明确，发尾带轻微外翻和空气感，方向感鲜明但保持真实发丝质感。",
        "palette": ("#2f4858", "#86bbd8"),
    },
]

SCENES = [
    {
        "id": "cafe",
        "name": "咖啡馆",
        "description": "暖色自然光，日常杂志感。",
        "prompt": "背景替换为暖色自然光下的咖啡馆，保留木质桌椅与轻微景深，整体像生活方式杂志抓拍，背景简洁不抢主体。",
        "palette": ("#6b4226", "#d9a066"),
    },
    {
        "id": "studio",
        "name": "极简棚拍",
        "description": "干净背景，更突出发型变化。",
        "prompt": "背景替换为极简摄影棚，使用柔和布光和浅灰或米白色背景，画面简洁克制，以人物脸部与发型为唯一重点。",
        "palette": ("#495057", "#dee2e6"),
    },
    {
        "id": "city-night",
        "name": "城市夜景",
        "description": "偏氛围感，带轻微霓虹散景。",
        "prompt": "背景替换为城市夜景，远处有柔和霓虹散景，主体保持清晰，对比适中，整体具备克制的电影感。",
        "palette": ("#2b2d42", "#ef233c"),
    },
    {
        "id": "meadow",
        "name": "自然草地",
        "description": "清新通透，光线偏自然。",
        "prompt": "背景替换为户外自然草地与柔和天空，环境通透，光线自然，色彩轻盈但不失真实，整体氛围安静自然。",
        "palette": ("#386641", "#a7c957"),
    },
    {
        "id": "lifestyle-interior",
        "name": "室内生活感",
        "description": "木质家具与自然光，居家感更强。",
        "prompt": "背景替换为室内生活感空间，浅色墙面，柔和自然窗光，前景可以有少量浅色虚化遮挡；背景虚化中可见实木书架、书本、杯子、实木抽纸盒、黑色木框中的墨绿色装饰画与绿色枝叶，整体安静、克制、高级。",
        "palette": ("#774936", "#ddb892"),
    },
]


IDENTITY_LOCK_SECTION = (
    "请基于上传参考图中的同一人物生成 1 张高相似度、写实风格的人像写真。"
    "第一优先级是严格保留参考人物的真实身份特征，不改变人物的脸型、五官比例、"
    "眼距、鼻梁、嘴型、肤色、年龄感和整体气质，保证一眼看出是同一个人；"
    "不要换脸，不要改变性别表达，不要生成第二个人。"
)

SUBJECT_REFRAME_SECTION = (
    "忽略原照片中的背景、原服饰、原发型和原有动作，仅保留参考人物本身，"
    "进行换发和换背景创作。主体必须始终是同一位单人肖像。"
)

CAMERA_AND_POSE_SECTION = (
    "画面设定为竖构图，3:4 比例，胸口以上近景或半身近景，镜头轻微靠近。"
    "人物看向镜头，微微歪头，一只手自然轻触头发，动作自然，像室内生活感抓拍，"
    "不刻意摆拍。"
)

STYLING_SECTION = (
    "服饰设定为白色宽松衬衫，领口自然微敞，内搭浅色上衣，整体简洁、干净、生活化，"
    "服饰不能喧宾夺主，重点仍然是人物脸部与发型。"
)

EMOTION_SECTION = (
    "人物情绪为慵懒、微醺、若有所思，眼神略微放空，嘴唇微张，不刻意微笑；"
    "皮肤真实自然，不过度磨皮，不过度妆感。"
)

VISUAL_QUALITY_SECTION = (
    "成片应具备真实摄影质感、轻胶片氛围与克制色调，发型细节清晰，脸部对焦准确，"
    "光线自然，整体高级耐看。"
)

NEGATIVE_CONSTRAINTS_SECTION = (
    "负向约束：不要改变人物身份，不要生成第二个人，不要夸张美颜，不要网红脸，"
    "不要卡通感，不要动漫风，不要多余手指，不要畸形手部，不要五官错位，"
    "不要脸部模糊，不要背景杂乱，不要过强滤镜，不要文字水印。"
)


def _find_template(items: Iterable[dict], template_id: str) -> dict | None:
    for item in items:
        if item["id"] == template_id:
            return item
    return None


def get_hairstyle(template_id: str) -> dict | None:
    return _find_template(HAIRSTYLES, template_id)


def get_scene(template_id: str) -> dict | None:
    return _find_template(SCENES, template_id)


def build_prompt(hairstyle: dict, scene: dict) -> str:
    return "\n".join(
        [
            IDENTITY_LOCK_SECTION,
            SUBJECT_REFRAME_SECTION,
            CAMERA_AND_POSE_SECTION,
            hairstyle["prompt"],
            STYLING_SECTION,
            EMOTION_SECTION,
            scene["prompt"],
            VISUAL_QUALITY_SECTION,
            NEGATIVE_CONSTRAINTS_SECTION,
        ]
    )


def template_cover_svg(category: str, template: dict) -> str:
    color_a, color_b = template["palette"]
    title = template["name"]
    label = "HAIR" if category == "hairstyles" else "SCENE"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="720" height="480" viewBox="0 0 720 480">
  <defs>
    <linearGradient id="bg" x1="0%" x2="100%" y1="0%" y2="100%">
      <stop offset="0%" stop-color="{color_a}" />
      <stop offset="100%" stop-color="{color_b}" />
    </linearGradient>
  </defs>
  <rect width="720" height="480" rx="32" fill="url(#bg)" />
  <circle cx="580" cy="120" r="92" fill="rgba(255,255,255,0.12)" />
  <circle cx="140" cy="380" r="120" fill="rgba(255,255,255,0.08)" />
  <text x="56" y="96" fill="#ffffff" font-size="28" font-family="Arial, sans-serif" opacity="0.82">{label}</text>
  <text x="56" y="210" fill="#ffffff" font-size="58" font-family="Arial, sans-serif" font-weight="700">{title}</text>
  <text x="56" y="272" fill="#ffffff" font-size="24" font-family="Arial, sans-serif" opacity="0.85">{template["description"]}</text>
  <rect x="56" y="336" width="180" height="52" rx="26" fill="rgba(255,255,255,0.18)" />
  <text x="90" y="370" fill="#ffffff" font-size="22" font-family="Arial, sans-serif">AI Remix</text>
</svg>"""
