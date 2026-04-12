# 场景与妆造系统重构方案

## Summary

把当前 `scene_only` 升级为一个更准确的模式：`identity_locked_scene_render`。
它不再被视为“纯场景库”，而是一个四层解耦的组合系统：

- `identity_lock`：身份与发型稳定层
- `scene_blocks`：场景层
- `styling_blocks`：妆造层
- `performance_blocks`：表现层

已锁定的产品决策：

- 前端用户入口：`主题优先`
- 国风第一期范围：`自然国风 + 时尚国风` 双线
- 默认 `hair_policy`：`ornament_only`
- 节气第一期：`先做基础 overlay`，不一次性上全量 24 节气
- 妆造第一期：`只做女性分流`，男性继续沿用现有默认兜底

目标不是推翻现有场景系统，而是在保留现有稳定生成链路的前提下，把“场景、妆造、动作、规则”拆成可复用、可叠加、可扩展的资产。

## Key Changes

### 1. 模式语义与接口重命名

把内部语义从 `scene_only` 迁移为 `identity_locked_scene_render`，但第一阶段保留兼容别名：

- 前端和旧接口仍可继续传 `scene_only`
- 服务层内部统一映射到新模式语义
- 所有新文档、注释、数据结构说明使用 `identity_locked_scene_render`

实现要求：

- 不要求第一阶段立刻改动所有文件名
- 但 `templates.py`、场景工具文案、后续数据文档都要明确：这是“锁身份锁发型的场景定向生图模式”，不是“只改背景”

### 2. 数据层重构为四层资产

#### A. `identity_lock`

继续保留在 prompt 组装层，不单独做用户资产库。
职责：

- 锁人物身份
- 锁当前发型主结构
- 锁刘海
- 锁发色
- 锁发丝动态边界

新增明确字段：

- `hair_policy`
  - `strict_lock`
  - `soft_lock`
  - `ornament_only`

第一期默认值：

- 国风主题默认 `ornament_only`
- 生活感与普通场景沿用当前严格锁发逻辑
- 只有在明确需要时才允许 `soft_lock`

#### B. `scene_blocks`

从现有 `scenes.json` 继续演进，但严格收敛为场景层，不再偷偷承载妆造语义。

每个 scene 必须显式包含：

- `id`
- `title`
- `sceneFamily`
- `styleLine`
- `themeTags`
- `settingTags`
- `seasonTags`
- `riskLevel`
- `shot`
- `environment`
- `lighting`
- `lightingProfile`
- `mood`
- `sceneConstraints`
- `controlProfile`
- `sampleImageIds`
- `referenceNotes`
- `referenceSourceIds`

从现有 `scenes.json` 映射关系：

- `shotAdvice` -> `shot`
- `environment` 保留
- `lighting` 保留
- `styleMood` -> `mood`
- `constraints` -> `sceneConstraints`

第一阶段不删除旧字段，但新增规范字段并在模板服务中优先读取新字段。

#### C. `styling_blocks`

把当前 `stylings.json` 从“大段文案模板”升级为“profile + blocks”。

第一期 profile 只做以下几类：

- `female_guofeng_natural_soft`
- `female_guofeng_fashion_editorial`
- `female_modern_chinese_daily`
- `unisex_natural_soft_fallback`
- `unisex_structured_editorial_fallback`
- `male_clean_natural_grooming_fallback`
- `male_sharp_editorial_fallback`

每个 styling profile 需要拆出正式字段，而不是只有文本：

- `base_makeup`
- `lip_color`
- `eye_makeup`
- `skin_finish`
- `hair_policy`
- `hair_ornament`
- `outfit_core`
- `outfit_material`
- `outfit_palette`
- `jewelry_level`
- `accessories`
- `styling_constraints`

当前 `makeupPrompt`、`outfitPrompt` 继续保留作为兼容文本输出，但生成逻辑要从结构字段拼装。

#### D. `performance_blocks`

把人物表现从 scene 内继续抽象成独立 profile 资产。

第一期建议建立：

- `guofeng_still`
- `guofeng_turn_back`
- `guofeng_hold_fan`
- `guofeng_hold_book`
- `guofeng_hold_umbrella`
- `guofeng_lean_rail`
- `guofeng_slow_walk`

字段最少包括：

- `expressionOptions`
- `actionOptions`
- `gestureConstraints`
- `bodyPoseHints`
- `handPropPolicy`

第一阶段可以先保留 scene 里的 `expressions/actions`，但新增 performance profile 解析优先级。

### 3. 规则系统升级

把 `scene_styling_rules.json` 从“默认妆造绑定”升级成三段式规则：

- `default`
- `recommended`
- `forbidden`

建议结构：

- `sceneId`
- `sceneFamily`
- `defaultStylingIds`
- `recommendedStylingIds`
- `forbiddenStylingIds`
- `defaultPerformanceIds`
- `recommendedPerformanceIds`
- `forbiddenOutfitTags`
- `requiredOutfitTags`
- `hairPolicyOverride`
- `lightingGuardrails`
- `stylingConstraints`
- `themeCompatibility`
- `settingCompatibility`

新增标签体系，供规则匹配使用：

- `theme`
  - `guofeng`
  - `modern_chinese`
  - `seasonal`
  - `solar_term`
- `tone`
  - `natural`
  - `fashion`
- `setting`
  - `indoor`
  - `courtyard`
  - `corridor`
  - `garden`
  - `waterside`
  - `snow`
  - `rain`
  - `studio`
- `risk`
  - `low`
  - `medium`
  - `high`

匹配逻辑改为：

`scene tags × user theme × style line × preferred gender -> styling/performance candidates`

不再只靠“一个 scene 对应一个默认 styling”。

### 4. 国风主题资产设计

第一期不直接做“24 个独立大场景”，而是做三层组合资产：

#### 基础 scene pack

`guofeng_natural`

- 庭院
- 廊下
- 窗边
- 竹林
- 荷塘
- 古桥
- 书房

`guofeng_fashion`

- 冷调回廊
- 暗色戏台侧区
- 高对比屏风空间
- 极简东方棚拍
- 夜色庭院
- 灯笼巷口

#### seasonal overlay

- `spring_blossom`
- `summer_lotus`
- `autumn_fallen_leaf`
- `winter_snow`

#### solar term overlay 第一阶段只做高频 8 个

- 雨水
- 清明
- 小满
- 小暑
- 白露
- 霜降
- 小雪
- 冬至

每个 overlay 只允许改这些维度：

- 局部环境元素
- 光线调性微调
- 空气状态
- 道具建议
- 色彩倾向
- 情绪标签

禁止 overlay 改动：

- 主场景骨架
- 主镜头结构
- 主发型结构
- 基础身份锁定策略

### 5. 当前数据清理与兼容迁移

#### A. 清理现有 5 个无专属 rule 的 scene

必须补齐 rule，并统一命名规范：

- `scene-35aef68d`
- `scene-98033eb1`
- `scene-41e220d6`
- `green-outdoor-b9edbc24`
- `scene-473e9e49`

要求：

- 重命名为可读、可维护、可归类的 scene id
- 补 `sceneFamily`
- 补 `default/recommended/forbidden` 规则
- 补标签体系

#### B. `build_scene_draft()` 升级

把它从“场景草案生成器”升级为“场景块提取器”。

必须完整沉淀：

- `shot`
- `environment`
- `lighting`
- `mood`
- `sceneConstraints`
- `recommendedStylingProfile`
- `themeTags`
- `settingTags`
- `riskLevel`

明确不做的事：

- 不把 `makeup` 直接塞回 scene 主体
- 不把 styling 文本继续塞进 scene 的自由字段
- 妆造只以 `recommendedStylingProfile` 或 tags 形式从 scene 指向 styling

#### C. `stylings.json` 升级但保兼容

- 旧字段 `makeupPrompt` / `outfitPrompt` 保留
- 新逻辑优先从结构化 block 渲染
- 旧接口继续能返回一段完整妆造描述文本

## Implementation Changes

### 服务层

重点修改 [templates.py](/home/lcy/AIFace/backend/app/services/templates.py)：

- 在 prompt assembly 中显式拆为：
  - `identity_lock`
  - `scene`
  - `styling`
  - `performance`
- 新增 `hair_policy` 处理逻辑
- 新增 scene/styling/performance 的推荐与禁用过滤
- `scene_only` 模式保留为兼容入口，但内部使用新模式语义
- 国风主题模式下，默认启用 `ornament_only`
- `build_scene_text()` 只读场景字段，不再读妆造语义
- `build_styling_text()` 从结构化 styling blocks 生成文本
- 新增 `build_performance_text()` 或复用现有主体表现组装逻辑，但数据来源改为 profile 优先

重点修改 [image_understanding.py](/home/lcy/AIFace/backend/app/services/image_understanding.py)：

- 保留现有理解 prompt，但输出结构升级为 scene block 草案
- `makeup` 与 `styling_constraints` 不直接落 scene 主体
- 增加 `recommendedStylingProfile` 推断
- 增加 `themeTags / settingTags / riskLevel` 推断
- `scene_draft` 输出格式与新 scene schema 对齐

### 数据文件

新增或重构的资产建议：

- `scenes.json`
  - 补规范字段
  - 清理临时 id
- `scene_styling_rules.json`
  - 升级为 default/recommended/forbidden 结构
- `stylings.json`
  - 拆成 profile + blocks
- 新增 `performance_profiles.json`
- 新增 `scene_overlays_seasonal.json`
- 新增 `scene_overlays_solar_terms.json`

第一期不要求新增单独的 `makeup_blocks.json`，但 styling profile 内部字段必须结构化，不能继续只有长文本。

### 前端

前端主题入口第一期按“主题优先”组织：

- 自然国风
- 时尚国风
- 春日
- 夏日
- 秋日
- 冬日
- 节气系列

点击路径建议：

1. 先选主题
2. 再选基础场景或节气/季节变体
3. 再选人物妆造风格
4. 后端自动解析为 scene + styling + performance + overlays

前端不暴露 `hair_policy` 技术词。
国风主题默认只给用户呈现“可加发饰/丝带/簪花”等轻装饰表达，不提示“改发型”。

## Test Plan

### 核心行为测试

- `scene_only` 旧入口仍可生成有效 prompt
- 新 `identity_locked_scene_render` 语义下，发型结构不被 scene/styling 改写
- `ornament_only` 时允许发饰，不允许主发型结构漂移
- `strict_lock` 时发饰也不会被错误加入
- `soft_lock` 仅在显式开启时生效

### 数据与规则测试

- 所有 scene 都存在 rule；不能再有无 rule 场景
- 所有 scene rule 的 `default/recommended/forbidden` id 都能解析
- styling profile 的结构字段能成功渲染为文本 prompt
- overlay 只能改允许的字段，不会重写 scene 主体
- 临时 hash 风格 scene id 被全部清理或归档

### 生成验收测试

重点抽样组合：

- 自然国风 × 庭院 × 春樱 × 女性自然国风妆造
- 自然国风 × 书房 × 白露 × 女性新中式日常
- 时尚国风 × 夜色庭院 × 霜降 × 女性时尚国风妆造
- 普通生活感 scene × 默认妆造 × `strict_lock`
- 男性现实场景 × 旧默认 styling fallback

验收标准：

- 人物身份稳定
- 主发型结构稳定
- 发饰成立但不假发化
- 妆容与场景一致
- 服饰不抢脸
- 动作与道具不破坏发型和脸部遮挡关系
- 国风感来自场景/妆造/配饰，不依赖改头换面

## Assumptions

- 第一阶段不重写整套生成链路，只做结构升级和规则升级
- 第一阶段以女性国风妆造为重点，男性继续用现有 `male-clean-natural-grooming` / `male-sharp-editorial` 兜底
- 第一阶段不做完整 24 节气，只做 8 个高频 overlay
- 第一阶段不要求把所有旧场景都国风化，只新增国风 pack 并保持现有现代场景可用
- 第一阶段保留 `scene_only` 兼容名，避免前后端接口一次性断裂
