from __future__ import annotations

from collections.abc import Iterable


HAIRSTYLES = [
    {
        "id": "short-texture",
        "name": "短碎发",
        "description": "轻盈层次，适合日常街拍风。",
        "prompt": "将人物发型改为干净利落的短碎发，顶部保留自然纹理和轻微蓬松感，发丝清晰真实。",
        "palette": ("#1f4b99", "#5dd4ff"),
    },
    {
        "id": "korean-middle-part",
        "name": "韩系中分",
        "description": "柔和包裹脸型，气质偏清爽。",
        "prompt": "将人物发型改为韩系中分，发丝柔顺自然，顶部有蓬松弧度，两侧服帖但不贴头皮。",
        "palette": ("#34495e", "#89c2d9"),
    },
    {
        "id": "french-curl",
        "name": "法式卷发",
        "description": "带有随性空气感的卷度。",
        "prompt": "将人物发型改为法式卷发，卷度自然松弛，富有空气感，保持人像真实发量与受光。",
        "palette": ("#8e5a3c", "#f6bd60"),
    },
    {
        "id": "american-spiky",
        "name": "美式前刺",
        "description": "顶部前刺明显，轮廓更利落。",
        "prompt": "将人物发型改为美式前刺，顶部前额与头顶区域形成清晰刺感，两侧和后区渐变推短，整体高级且写实。",
        "palette": ("#1c1c1c", "#6f4e37"),
    },
    {
        "id": "wolf-cut",
        "name": "狼尾层次",
        "description": "有层次与方向感，偏潮流感。",
        "prompt": "将人物发型改为狼尾层次发型，顶部与后区层次明显，发尾带轻微外翻和空气感。",
        "palette": ("#2f4858", "#86bbd8"),
    },
]

SCENES = [
    {
        "id": "cafe",
        "name": "咖啡馆",
        "description": "暖色自然光，日常杂志感。",
        "prompt": "背景替换为带暖色自然光的咖啡馆，木质桌椅和轻微景深，整体有生活方式杂志感。",
        "palette": ("#6b4226", "#d9a066"),
    },
    {
        "id": "studio",
        "name": "极简棚拍",
        "description": "干净背景，更突出发型变化。",
        "prompt": "背景替换为极简摄影棚，柔和布光，浅灰或米白色背景，整体简洁高级。",
        "palette": ("#495057", "#dee2e6"),
    },
    {
        "id": "city-night",
        "name": "城市夜景",
        "description": "偏氛围感，带轻微霓虹散景。",
        "prompt": "背景替换为城市夜景，远处有柔和霓虹散景，主体依然清晰，整体电影感强。",
        "palette": ("#2b2d42", "#ef233c"),
    },
    {
        "id": "meadow",
        "name": "自然草地",
        "description": "清新通透，光线偏自然。",
        "prompt": "背景替换为户外自然草地与柔和天空，环境通透，色彩轻盈但不失真实。",
        "palette": ("#386641", "#a7c957"),
    },
    {
        "id": "lifestyle-interior",
        "name": "室内生活感",
        "description": "木质家具与自然光，居家感更强。",
        "prompt": "背景替换为生活方式室内空间，带木质家具、书架和柔和窗边自然光，氛围克制高级。",
        "palette": ("#774936", "#ddb892"),
    },
]


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
            "请基于上传照片中的同一人物进行真实感人像重绘。",
            "必须完整保留人物原生面部特征、五官比例、肤色与身份识别度，不要改变性别和年龄段。",
            hairstyle["prompt"],
            scene["prompt"],
            "保留单人肖像，不要生成第二个人，不要出现多余手指、畸形五官或重复肢体。",
            "整体风格为写实摄影作品，发型变化是主视觉重点，背景完成替换但不要喧宾夺主。",
            "构图为竖版 3:4，中近景，适合小程序分享封面，画面清晰，光线自然。",
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

