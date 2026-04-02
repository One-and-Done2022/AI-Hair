# Block Preset 规则表

这份文档用于统一 AIFace 当前的提示词 block 设计、preset 展开方式和三种生成模式的组装规则。它的目标不是描述自然语言 prompt，而是先把“结构层”固定下来，后续 `faceprompt`、后端组装器和前端选择项都按这份结构对齐。

## 核心原则

- `hair_only` 只处理头发系统
- `scene_only` 只处理场景、妆造、动作系统
- `full_stylize` 只作为补充模式，不作为主流程
- 发型 preset 和场景 preset 都不是 block，本质上是 block 的组合包
- 刘海必须从发型里拆出来，做独立 block
- 发色必须独立，不能继续混在发型描述里
- `scene_only` 必须显式锁定发型、刘海、发色
- preset 先展开，再按模式裁剪，不能直接把整个 preset 原样丢给 prompt

## 正式一级 Block

| key | 中文 label | 作用 | 典型二级字段 | `hair_only` | `scene_only` | `full_stylize` | 是否建议前端直接开放 |
|---|---|---|---|---|---|---|---|
| `identity_lock` | 身份锁定 | 锁定同一人物，不换脸不漂移 | 人脸、五官比例、年龄感、肤色、性别表达 | 必带 | 必带 | 必带 | 否 |
| `output_spec` | 输出规格 | 控制单张、多宫格、比例、输出形式 | 单张、比例、拼图禁止 | 必带 | 必带 | 必带 | 部分开放 |
| `edit_scope` | 编辑范围 | 定义本次允许改什么 | `hair_only` / `scene_only` / `full_stylize` | 必带 | 必带 | 必带 | 否 |
| `hair_shape` | 主发型结构 | 定义发型主体，不含刘海、不含发色 | 发长、轮廓、纹理、蓬松度、分线、鬓角、后颈区、发尾收口 | 必带 | 禁止 | 必带 | 通过发型 preset 间接开放 |
| `bangs` | 刘海系统 | 独立控制刘海类型和脸侧修饰 | 刘海类型、厚薄、长度、开合方式、脸侧修饰 | 必带 | 禁止 | 必带 | 第一版不独立开放或少量开放 |
| `hair_color` | 发色系统 | 独立控制发色与染发方式 | 色调、深浅、冷暖、工艺、分布方式 | 必带 | 禁止 | 必带 | 建议开放 |
| `scene` | 场景系统 | 只定义环境和光线，不碰头发 | 构图、环境、布光、氛围、场景约束 | 禁止 | 必带 | 必带 | 通过场景 preset 间接开放 |
| `styling` | 妆造系统 | 人物妆容、服饰、配饰 | 妆容、服饰、配饰、妆造约束 | 禁止 | 必带 | 必带 | 第一版不独立开放 |
| `subject_performance` | 人物表现系统 | 控制表情和动作 | 表情、主体动作、手势约束 | 禁止 | 必带 | 必带 | 第一版不独立开放 |
| `quality_control` | 质量控制 | 控制肤质、发丝、清晰度、光影完成度 | 皮肤纹理、发丝细节、对焦、成片质感 | 必带 | 必带 | 必带 | 否 |
| `negative_constraints` | 负面约束 | 统一处理伪影和物理逻辑问题 | 身份伪影、物理逻辑、渲染伪影 | 必带 | 必带 | 必带 | 否 |

## 锁定 Block

这些不是常规内容 block，而是 `scene_only` 专用锁定块。

| key | 中文 label | 作用 | `hair_only` | `scene_only` | `full_stylize` |
|---|---|---|---|---|---|
| `hair_shape_lock` | 发型锁定 | 锁定发长、轮廓、卷度、分线、鬓角、后颈区 | 禁止 | 必带 | 禁止 |
| `bangs_lock` | 刘海锁定 | 锁定刘海类型、厚薄、长度、开合方式 | 禁止 | 必带 | 禁止 |
| `hair_color_lock` | 发色锁定 | 锁定发色、冷暖、深浅、挑染和过渡 | 禁止 | 必带 | 禁止 |

## 推荐二级字段结构

| 一级 block | 二级字段 |
|---|---|
| `hair_shape` | `hair_length`, `hair_silhouette`, `hair_texture`, `hair_volume`, `hair_parting`, `sideburn_nape`, `hair_tail_finish` |
| `bangs` | `bangs_type`, `bangs_density`, `bangs_length`, `bangs_split`, `bangs_face_framing` |
| `hair_color` | `hair_color_tone`, `hair_color_depth`, `hair_color_temperature`, `hair_color_technique`, `hair_color_distribution` |
| `scene` | `shot`, `scene_environment`, `scene_lighting`, `scene_mood`, `scene_constraints` |
| `styling` | `makeup`, `outfit`, `accessories`, `styling_constraints` |
| `subject_performance` | `expression`, `subject_action`, `gesture_constraints` |
| `quality_control` | `skin_texture`, `hair_detail`, `focus_finish`, `lighting_finish` |
| `negative_constraints` | `negative_identity_artifact`, `negative_physical_logic`, `negative_render_artifact` |

## 三种模式的正式组装规则

| 模式 | 必带 block | 禁止 block | 说明 |
|---|---|---|---|
| `hair_only` | `identity_lock`, `output_spec`, `edit_scope`, `hair_shape`, `bangs`, `hair_color`, `quality_control`, `negative_constraints` | `scene`, `styling`, `subject_performance`, 所有 lock block | 只改头发，不改背景、服饰、表情、动作、构图 |
| `scene_only` | `identity_lock`, `output_spec`, `edit_scope`, `scene`, `styling`, `subject_performance`, `hair_shape_lock`, `bangs_lock`, `hair_color_lock`, `quality_control`, `negative_constraints` | `hair_shape`, `bangs`, `hair_color` | 只改场景和妆造，不改头发任何结构 |
| `full_stylize` | `identity_lock`, `output_spec`, `edit_scope`, `hair_shape`, `bangs`, `hair_color`, `scene`, `styling`, `subject_performance`, `quality_control`, `negative_constraints` | 所有 lock block | 一步全改，风险最高，不建议作为主流程 |

## Preset 和 Block 的关系

这部分必须固定，不然后面会继续混乱。

| 类型 | 本质 | 是否等于 block | 正确处理方式 |
|---|---|---|---|
| 发型 preset | 头发系统的组合包 | 否 | 展开成 `hair_shape + bangs + 推荐 hair_color` |
| 场景 preset | 场景系统的组合包 | 否 | 展开成 `scene + styling + subject_performance` |
| 妆造风格 preset | 妆造组合包 | 否 | 展开成 `styling`，必要时影响 `subject_performance` |

## 覆盖优先级与模式裁剪规则

### 覆盖优先级

统一使用下面这条优先级：

`用户显式选择 > preset 默认值 > 系统推荐值`

应用说明：

- 用户手动选择的发色、刘海变体、场景永远优先
- preset 自带的是默认展开值，不是强绑定
- 系统推荐只在用户没选、preset 没给时作为兜底

### 模式裁剪规则

preset 不会直接进入 prompt，而是遵循下面的流程：

1. 先展开 preset
2. 再按模式裁剪 block
3. 再写入 prompt 组装层

固定规则：

- 发型 preset 展开后，`hair_only` 只取 `hair_shape + bangs + hair_color`
- 场景 preset 展开后，`scene_only` 只取 `scene + styling + subject_performance`
- `scene_only` 不允许把发型 preset 里的编辑 block 带进去，只能带 lock block
- `full_stylize` 可以同时带两套 block，但不建议作为主流程

## Block 输入示例

下面的示例是“结构输入示例”，不是最终自然语言 prompt。字段名固定使用英文 key，解释使用中文。

### `identity_lock`

用途：锁定同一人物身份特征，防止换脸、年龄漂移、性别表达变化。

```json
{
  "preserve_identity": true,
  "single_subject_only": true,
  "preserve_face_geometry": true,
  "preserve_skin_tone": true,
  "preserve_age_impression": true,
  "preserve_gender_expression": true
}
```

### `output_spec`

用途：定义输出数量、比例和排版约束。

```json
{
  "image_count": 1,
  "aspect_ratio": "3:4",
  "response_layout": "single_frame",
  "forbid_collage": true,
  "forbid_multi_panel": true,
  "forbid_multi_version_in_one_frame": true
}
```

### `edit_scope`

用途：定义这次生成的权限边界。

```json
{
  "mode": "hair_only",
  "preserve_background": true,
  "preserve_outfit": true,
  "preserve_expression": true,
  "preserve_action": true,
  "preserve_composition": true
}
```

### `hair_shape`

用途：定义发型主体结构，不含刘海和发色。

```json
{
  "hair_length": "medium_long",
  "hair_silhouette": "soft_oval_layers",
  "hair_texture": "loose_large_waves",
  "hair_volume": "airy_root_lift",
  "hair_parting": "soft_middle_part",
  "sideburn_nape": "soft_face_framing_nape",
  "hair_tail_finish": "light_tapered_ends"
}
```

### `bangs`

用途：单独控制刘海和脸侧修饰关系。

```json
{
  "bangs_type": "curtain_bangs",
  "bangs_density": "light",
  "bangs_length": "cheekbone_level",
  "bangs_split": "soft_center_split",
  "bangs_face_framing": "cheekbone_frame"
}
```

### `hair_color`

用途：控制发色基调、深浅、冷暖和染发工艺。

```json
{
  "hair_color_tone": "mocha_brown",
  "hair_color_depth": "medium",
  "hair_color_temperature": "neutral_warm",
  "hair_color_technique": "balayage",
  "hair_color_distribution": "mid_to_end_lift"
}
```

### `scene`

用途：定义构图、空间环境、光线和场景约束。

```json
{
  "shot": "chest_up_near_portrait",
  "scene_environment": "cafe_window_seat",
  "scene_lighting": "soft_side_backlight",
  "scene_mood": "relaxed_warm_candid",
  "scene_constraints": "clean_background_no_visual_clutter"
}
```

### `styling`

用途：定义妆容、服饰和配饰，不碰头发结构。

```json
{
  "makeup": "clean_glowy_soft_blush",
  "outfit": "ivory_knit_top",
  "accessories": "minimal_earrings",
  "styling_constraints": "keep_styling_consistent_with_soft_warm_scene"
}
```

说明：

- 发夹如果是发型识别特征，优先放进 `hair_shape` 或 `bangs`
- 普通耳环、项链、衣服放进 `styling`

### `subject_performance`

用途：定义表情、主体动作和手势约束。

```json
{
  "expression": "gentle_closed_lip_smile",
  "subject_action": "slight_side_turn_seated_pause",
  "gesture_constraints": "no_extra_hand_action_conflicting_with_main_pose"
}
```

### `quality_control`

用途：约束肤质、发丝、对焦和成片完成度。

```json
{
  "skin_texture": "real_clean_natural",
  "hair_detail": "strand_level_clear_without_wig_effect",
  "focus_finish": "sharp_face_and_eye_focus",
  "lighting_finish": "natural_transition_no_harsh_conflict"
}
```

### `negative_constraints`

用途：统一处理身份伪影、肢体物理错误和渲染异常。

```json
{
  "negative_identity_artifact": [
    "no_face_swap",
    "no_identity_drift",
    "no_second_person",
    "no_ai_face"
  ],
  "negative_physical_logic": [
    "no_extra_hands",
    "no_fused_fingers",
    "no_deformed_ears"
  ],
  "negative_render_artifact": [
    "no_over_smoothing",
    "no_plastic_skin",
    "no_text_watermark"
  ]
}
```

### `hair_shape_lock`

用途：在 `scene_only` 阶段锁定当前已生成发型结构。

```json
{
  "lock_source": "current_generated_preview",
  "preserve_fields": [
    "hair_length",
    "hair_silhouette",
    "hair_texture",
    "hair_volume",
    "hair_parting",
    "sideburn_nape",
    "hair_tail_finish"
  ],
  "forbid_changes": [
    "change_haircut",
    "change_wave_pattern",
    "change_parting"
  ]
}
```

### `bangs_lock`

用途：在 `scene_only` 阶段锁定刘海结构。

```json
{
  "lock_source": "current_generated_preview",
  "preserve_fields": [
    "bangs_type",
    "bangs_density",
    "bangs_length",
    "bangs_split",
    "bangs_face_framing"
  ],
  "forbid_changes": [
    "change_bangs_type",
    "change_bangs_length",
    "change_face_framing"
  ]
}
```

### `hair_color_lock`

用途：在 `scene_only` 阶段锁定发色与染发层次。

```json
{
  "lock_source": "current_generated_preview",
  "preserve_fields": [
    "hair_color_tone",
    "hair_color_depth",
    "hair_color_temperature",
    "hair_color_technique",
    "hair_color_distribution"
  ],
  "forbid_changes": [
    "change_hair_color_tone",
    "change_dye_technique",
    "change_color_transition"
  ]
}
```

## Preset 展开示例

下面给出 4 组示例，风格优先当前热门女向。它们是规范样例，不等于最终线上模板库的全部字段。

### 发型 preset 1：`french_lazy_waves`

中文定位：法式慵懒卷  
目标效果：松弛、柔软、偏轻法式氛围，重点是自然大弯和轻空气感。

#### 展开结果

```json
{
  "hair_shape": {
    "hair_length": "medium_long",
    "hair_silhouette": "soft_oval_layers",
    "hair_texture": "loose_large_waves",
    "hair_volume": "airy_root_lift",
    "hair_parting": "soft_middle_part",
    "sideburn_nape": "soft_face_framing_nape",
    "hair_tail_finish": "light_tapered_ends"
  },
  "bangs": {
    "bangs_type": "curtain_bangs",
    "bangs_density": "light",
    "bangs_length": "cheekbone_level",
    "bangs_split": "soft_center_split",
    "bangs_face_framing": "cheekbone_frame"
  },
  "recommended_hair_color": {
    "hair_color_tone": "dark_brown",
    "hair_color_depth": "medium",
    "hair_color_temperature": "neutral_warm",
    "hair_color_technique": "solid",
    "hair_color_distribution": "uniform"
  }
}
```

#### 用户可覆盖项

- `hair_color`
- `bangs` 的少量变体
- 不建议在同一 preset 下覆盖 `hair_shape` 的主体轮廓

#### 模式裁剪

- `hair_only`：取 `hair_shape + bangs + hair_color`
- `scene_only`：不带这三个编辑 block，只带对应 lock block

### 发型 preset 2：`soft_collarbone_layers`

中文定位：轻羽锁骨层次发  
目标效果：清透、修脸、日常通用，适合柔和女性用户主流审美。

#### 展开结果

```json
{
  "hair_shape": {
    "hair_length": "collarbone",
    "hair_silhouette": "light_face_framing_layers",
    "hair_texture": "soft_straight_with_minor_bend",
    "hair_volume": "natural_top_volume",
    "hair_parting": "soft_side_part",
    "sideburn_nape": "cheek_and_jawline_frame",
    "hair_tail_finish": "feathered_soft_ends"
  },
  "bangs": {
    "bangs_type": "air_bangs",
    "bangs_density": "light",
    "bangs_length": "brow_level",
    "bangs_split": "natural_scatter",
    "bangs_face_framing": "jawline_frame"
  },
  "recommended_hair_color": {
    "hair_color_tone": "mocha_brown",
    "hair_color_depth": "medium",
    "hair_color_temperature": "neutral",
    "hair_color_technique": "solid",
    "hair_color_distribution": "uniform"
  }
}
```

#### 用户可覆盖项

- `hair_color`
- `bangs` 从空气刘海切换到无刘海或八字刘海
- 不建议覆盖 `hair_length`

#### 模式裁剪

- `hair_only`：取 `hair_shape + bangs + hair_color`
- `scene_only`：取 lock block，不取编辑 block

### 场景 preset 1：`cafe_candid`

中文定位：咖啡馆抓拍  
目标效果：松弛、生活流、轻熟温柔，适合日常分享型写真。

#### 展开结果

```json
{
  "scene": {
    "shot": "chest_up_near_portrait",
    "scene_environment": "cafe_window_seat",
    "scene_lighting": "soft_side_backlight",
    "scene_mood": "relaxed_warm_candid",
    "scene_constraints": "clean_tabletop_background_no_clutter"
  },
  "styling": {
    "makeup": "clean_glowy_soft_blush",
    "outfit": "ivory_knit_top_or_light_beige_shirt",
    "accessories": "minimal_earrings",
    "styling_constraints": "keep_makeup_and_outfit_soft_natural"
  },
  "subject_performance": {
    "expression": "gentle_closed_lip_smile",
    "subject_action": "seated_side_pause_with_relaxed_shoulders",
    "gesture_constraints": "no_conflicting_secondary_hand_action"
  }
}
```

#### 用户可覆盖项

- `expression`
- `subject_action`
- 小范围 `outfit` 风格

#### 模式裁剪

- `scene_only`：取 `scene + styling + subject_performance`
- 同时强制附带 `hair_shape_lock + bangs_lock + hair_color_lock`

### 场景 preset 2：`morning_window_softlight`

中文定位：清晨窗边软光  
目标效果：清透、轻情绪、柔和治愈，适合女向自然感模板。

#### 展开结果

```json
{
  "scene": {
    "shot": "chest_up_close_portrait",
    "scene_environment": "bedroom_or_livingroom_window_side",
    "scene_lighting": "soft_window_side_light",
    "scene_mood": "fresh_quiet_morning",
    "scene_constraints": "bright_clean_background_with_soft_air"
  },
  "styling": {
    "makeup": "transparent_base_soft_peach_blush",
    "outfit": "white_or_oatmeal_homewear_knit",
    "accessories": "none_or_minimal",
    "styling_constraints": "keep_homewear_soft_light_and_unforced"
  },
  "subject_performance": {
    "expression": "calm_thoughtful_soft_smile",
    "subject_action": "slight_turn_by_window_pause",
    "gesture_constraints": "avoid_hair_touching_gesture"
  }
}
```

#### 用户可覆盖项

- `expression`
- `subject_action`
- `outfit` 的轻微材质变化

#### 模式裁剪

- `scene_only`：取 `scene + styling + subject_performance`
- 同时强制附带 `hair_shape_lock + bangs_lock + hair_color_lock`

## 强约束规则

这些建议直接写成规则表或校验器。

| 规则编号 | 规则 |
|---|---|
| `R1` | `scene_only` 不允许出现 `hair_shape`、`bangs`、`hair_color` |
| `R2` | `scene_only` 必须出现 `hair_shape_lock`、`bangs_lock`、`hair_color_lock` |
| `R3` | `hair_only` 不允许出现 `scene`、`styling`、`subject_performance` |
| `R4` | 发型 preset 可以带推荐发色，但不能带场景和服饰 |
| `R5` | 场景 preset 不能带发型、刘海、发色 |
| `R6` | 刘海不能再混写进发型描述里，必须有独立 `bangs` 结构 |
| `R7` | 发色不能再混写成一句附属文案，必须有独立 `hair_color` 结构 |
| `R8` | `full_stylize` 里不能再出现 lock block |
| `R9` | `scene_only` 阶段禁止任何“改发色、改刘海、改发型轮廓”的语义 |
| `R10` | `hair_only` 阶段禁止任何“改背景、改服饰、改表情、改动作”的语义 |
| `R11` | 发型 preset 必须先展开为结构 block，再进入模式裁剪层 |
| `R12` | 场景 preset 必须先展开为结构 block，再进入模式裁剪层 |
| `R13` | 发色推荐值不能覆盖用户显式发色选择 |

## 推荐的前端开放层

| 用户可选项 | 后端实际映射 |
|---|---|
| 发型 | `hair_shape + bangs + 推荐 hair_color` |
| 发色基调 | `hair_color.hair_color_tone` |
| 染发工艺 | `hair_color.hair_color_technique` |
| 场景 | `scene + styling + subject_performance` |

## 第一版最推荐的实际业务流程

1. 用户选择发型 preset
2. 后端展开为 `hair_shape + bangs`
3. 用户选择发色和染发工艺
4. 后端补成完整 `hair_color`
5. 第一阶段执行 `hair_only`
6. 用户选择场景 preset
7. 后端展开为 `scene + styling + subject_performance`
8. 第二阶段执行 `scene_only`
9. 同时带上 `hair_shape_lock + bangs_lock + hair_color_lock`

## 一句话版本

只要始终坚持下面这条线，block 逻辑就不会再乱：

- 发型、刘海、发色 = 头发系统
- 场景、妆造、动作表情 = 场景系统
- `hair_only` 只改头发系统
- `scene_only` 只改场景系统，并锁死头发系统
