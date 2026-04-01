# Faceprompt 场景光影与妆造重构方案

## Summary

目标是把当前“场景 + 发型”为主的 prompt 体系，升级成“场景环境 + 场景光影 + 妆造 + 服饰 + 发型”的稳定组合系统，重点解决三个问题：

- 场景描述够了，但光影控制还不够强，导致同一场景出图不稳定
- 妆造与服饰已经有数据，但仍偏附属，没有成为强约束 block
- 服饰和场景常常只做弱提示，没有形成明确搭配规则，容易跳戏

重构后保留现有 block 骨架，不推翻现有数据，而是在现有 `scene_environment`、`scene_lighting`、`scene_mood`、`outfit` 基础上，新增更强的结构化来源和拼装优先级。

## Key Changes

### 1. Prompt Block 重构

保留现有 block 名称，但内部来源升级为以下结构：

- `scene_environment`
  继续负责空间元素、背景物件、景别语境、场景叙事
- `scene_lighting`
  从一句描述升级为结构化光影描述的汇总输出
- `scene_mood`
  只负责气质、情绪、风格，不再混入布光和妆造
- `makeup`
  新增独立 block，单独输出妆面
- `outfit`
  继续保留，但来源改为“场景服饰规则 + 妆造服饰规则”的组合结果
- `styling_constraints`
  新增独立 block，统一收纳妆造与服饰禁忌，不再散落到场景约束里
- `scene_constraints`
  只保留空间、布景、背景干净度、镜面风险、风感等场景约束
- `hair_constraints`
  继续只管发型，不混入妆造/服饰逻辑

建议的新拼装顺序：

1. 身份保持
2. 构图
3. 场景环境
4. 场景光影
5. 场景氛围
6. 人物表情
7. 主体动作
8. 人物妆造
9. 人物服饰
10. 发型展示动作
11. 人物发型
12. 场景约束
13. 妆造与服饰约束
14. 发型约束
15. 画质约束
16. 负面约束

### 2. 场景光影结构化

为每个场景新增一组 `lightingProfile` 字段，作为 `scene_lighting` block 的唯一结构化来源。

建议字段：

- `lightDirection`: `front` / `side` / `back` / `top` / `mixed`
- `lightQuality`: `soft` / `medium` / `hard`
- `colorTemperature`: `cool` / `neutral` / `warm` / `mixed`
- `contrastLevel`: `low` / `medium` / `high`
- `shadowDensity`: `light` / `balanced` / `deep`
- `hairHighlightMode`: `soft_edge` / `clean_rim` / `controlled_specular` / `none`
- `skinRendering`: `soft_texture` / `clean_texture` / `structured_texture`
- `exposureBias`: `slightly_under` / `neutral` / `slightly_over`
- `practicalLightsAllowed`: `true/false`

`scene_lighting` 输出规则固定，不让实现者自由发挥。建议统一模板：

“光线：主光为<方向>，整体为<光质>、<色温>、<反差>，阴影层次<描述>，发丝高光<描述>，皮肤呈现<描述>，曝光控制为<描述>。”

### 3. 妆造体系升级

把现有 `stylings.json` 明确升级为第一层“妆造模板库”，每条 styling 继续保留：

- `makeupPrompt`
- `outfitPrompt`
- `constraints`
- `detailTags`

新增建议字段：

- `id`
- `genderScope`: `female` / `male` / `unisex`
- `styleLine`
- `makeupIntensity`: `barely_there` / `light` / `defined`
- `outfitStructure`: `soft` / `clean` / `structured`
- `paletteTags`
- `compatibleSceneIds`
- `incompatibleSceneIds`
- `compatibleLightingTags`

其中：

- `makeupPrompt` 只写妆
- `outfitPrompt` 只写服饰
- `constraints` 只写妆造禁忌
- 不再把场景特有覆盖逻辑直接写死在 styling 本体里

### 4. 场景与妆造的匹配层

保留现有 `scene_styling_rules.json`，但升级成“场景到妆造的调度层”，不要再只做 override 文本。

建议每条规则包含：

- `sceneId`
- `defaultStylingIds`
- `fallbackStylingIds`
- `forbiddenStylingIds`
- `makeupOverride`
- `outfitOverride`
- `stylingConstraints`
- `lightingAdjustment`
- `requiredOutfitTags`
- `forbiddenOutfitTags`

调度优先级固定：

1. 用户显式指定妆造时，优先使用指定妆造
2. 场景规则中的 `forbiddenStylingIds` 和 `forbiddenOutfitTags` 先过滤
3. 选 `defaultStylingIds`
4. 无命中时退到 `fallbackStylingIds`
5. 再叠加该场景自己的 `makeupOverride` / `outfitOverride`
6. 最后拼接 `stylingConstraints`

### 5. 服饰规则升级

当前 `outfitHints` 太弱，建议升级为结构化服饰建议，但不强求立刻改全量 schema。最小可落地方案：

在 `scenes.json` 每个场景新增：

- `outfitPalette`
- `outfitMaterials`
- `outfitShapes`
- `outfitAvoids`

输出时仍然渲染为一句中文 `outfit` block，但来源改为结构化拼装。

建议固定输出模板：

“服饰：优先<色系>、<面料>、<版型>，避免<禁忌项>。”

### 6. 场景分组策略

后期不要全场景自由混搭，按三大组先建立默认光影与妆造逻辑：

- 生活感组
  - 适用场景：窗边、家居、咖啡馆、酒店、书房、浴室
  - 光影默认：软光、低到中反差、自然肤感
  - 妆造默认：轻透自然妆、低饱和服饰、柔软材质
- 冷感时装组
  - 适用场景：棚拍、金属空间、白盒子、强侧光
  - 光影默认：中到硬光、中高反差、轮廓清晰
  - 妆造默认：克制结构妆、黑白灰或低饱和冷色、结构化服饰
- 夜色情绪组
  - 适用场景：霓虹、酒吧、复古包厢、后台镜前、大堂
  - 光影默认：低照度局部重点光、冷暖对比、受控高光
  - 妆造默认：精致但克制的时装妆、成熟深色服饰、避免夜店感

## Implementation Changes

### 数据层

需要扩展或新增的主要数据来源：

- `scenes.json`
  新增 `lightingProfile`、`outfitPalette`、`outfitMaterials`、`outfitShapes`、`outfitAvoids`
- `stylings.json`
  新增 `genderScope`、`makeupIntensity`、`outfitStructure`、`paletteTags`、`compatibleSceneIds`、`incompatibleSceneIds`
- `scene_styling_rules.json`
  从纯文案 override 升级为“场景调度规则”

建议先只改 6 个高频场景做试点：

- `morning-window-softlight`
- `indoor-film-lifestyle`
- `hotel-room-loose`
- `studio-solid-backdrop`
- `cold-metal-space`
- `city-neon-night`

### 运行时拼装

在 `catalog.py` 中新增以下职责函数：

- `resolve_scene_lighting(scene)`
- `resolve_scene_styling(scene, gender, style_line, override)`
- `resolve_makeup_block(scene, styling)`
- `resolve_outfit_block(scene, styling, override)`
- `resolve_styling_constraints(scene, styling)`

现有 `_build_runtime_prompt_assembly` 和 `_build_scene_only_runtime_prompt_assembly` 改为显式插入 `makeup` 与 `styling_constraints` block。

### 接口与输出

需要同步更新的公开结构：

- `backend/app/schemas.py`
  - 为 block 结果增加 `makeup`
  - 可选增加 `styling_constraints`
- `backend/app/services/image_understanding.py`
  - 如果继续输出 block 级结果，也要支持这两个新字段
- CLI `blocks` / `render` / `scene-only`
  - 输出中要包含 `makeup` block，且 block 标签固定

## Test Plan

### 数据与拼装测试

- 每个试点场景都能产出非空的 `scene_lighting`
- 每个试点场景都能产出非空的 `makeup`
- 每个试点场景都能产出非空且不重复的 `outfit`
- `scene_constraints` 与 `styling_constraints` 不出现语义重叠或完全重复句子

### 组合正确性测试

- 生活感场景不会落入黑色高领、结构西装、强冷感时装妆
- 冷感时装场景不会落入奶油白家居针织、清晨素颜生活妆
- 夜色情绪场景不会落入清晨软光淡妆或过强家居服语义
- 男性场景不会误配明显女性彩妆
- 女性生活感场景不会误配厚重夜店妆或舞台妆

### 回归测试

- `full_stylize` 仍能正常输出
- `hairstyle_only` 不受影响
- `scene_only` 在锁发模式下也能输出 `makeup`、`outfit`
- 原有未试点场景在没有新字段时，仍能回退到旧逻辑默认值

## Assumptions

- 默认不改动现有发型数据结构，只补场景与妆造链路
- 新增 `makeup` block 是必须项，`styling_constraints` 也是建议同时落地
- `controlProfile` 不扩到妆造层，妆造优先通过规则调度，不做复杂推荐引擎
- 第一阶段只做 6 个试点场景，验证通过后再推广到全部 20 个场景
- 未配置新字段的旧场景，继续使用当前 `scene_lighting + outfitHints + scene_styling_rules` 的兼容回退逻辑
