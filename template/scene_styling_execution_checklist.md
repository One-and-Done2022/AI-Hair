# 场景与妆造系统执行清单

## 1. 文档目的

这份文档是对 [scene_styling_refactor_plan.md](/home/lcy/AIFace/template/scene_styling_refactor_plan.md) 的执行拆解版。

用途：

- 把“大方案”拆成另一个 agent 可按阶段执行的 checklist
- 在不改代码的前提下，先完成规划层面的分类、命名、资产清洗和交付物定义
- 把后续实现前必须锁住的命名与分类规则一次性定清楚，避免后面边做边改

当前阶段只做：

- 分类整理
- 命名规范
- 资产映射
- JSON / Markdown 草案规划
- 交付物清单

当前阶段不做：

- 不改后端代码
- 不改前端代码
- 不改现有正式 JSON 数据
- 不补新图片
- 不执行生图

## 2. 当前基线

当前已知资产现状：

- `scenes.json`：22 条 scene
- `stylings.json`：7 条 styling
- `scene_styling_rules.json`：17 条 rule
- 当前有 5 条 scene 没有专属 rule，且命名不规范

当前正式文件：

- `/home/lcy/AIFace/backend/app/data/faceprompt/scenes.json`
- `/home/lcy/AIFace/backend/app/data/faceprompt/stylings.json`
- `/home/lcy/AIFace/backend/app/data/faceprompt/scene_styling_rules.json`

当前规划主文档：

- `/home/lcy/AIFace/template/scene_styling_refactor_plan.md`

## 3. 分类方案

### 3.1 内部资产分类

后续内部资产统一按 4 个层级分类：

- `identity_lock`
- `scene_blocks`
- `styling_blocks`
- `performance_blocks`

这是工程层，不直接面向用户。

### 3.2 scene 的内部分类维度

每个 scene 未来都要落到以下维度：

- `theme`
  - `modern`
  - `guofeng`
  - `modern_chinese`
  - `seasonal_overlay`
  - `solar_term_overlay`
- `tone`
  - `natural`
  - `fashion`
- `setting`
  - `indoor`
  - `window`
  - `courtyard`
  - `corridor`
  - `garden`
  - `bamboo`
  - `waterside`
  - `bridge`
  - `study`
  - `rooftop`
  - `bar`
  - `stage`
  - `studio`
  - `snow`
  - `rain`
- `season`
  - `all_season`
  - `spring`
  - `summer`
  - `autumn`
  - `winter`
- `risk`
  - `low`
  - `medium`
  - `high`

### 3.3 用户侧分类

用户侧入口按“主题优先”组织，第一期规划如下：

- `自然国风`
- `时尚国风`
- `春日`
- `夏日`
- `秋日`
- `冬日`
- `节气系列`

现有现代 scene 暂不删，作为内部保留与兼容资产，后续如果继续对外展示，单独归到：

- `现代写真`

### 3.4 styling 的内部分类

第一期 styling profile 规划为：

- `female_guofeng_natural_soft`
- `female_guofeng_fashion_editorial`
- `female_modern_chinese_daily`
- `unisex_natural_soft_fallback`
- `unisex_structured_editorial_fallback`
- `male_clean_natural_grooming_fallback`
- `male_sharp_editorial_fallback`

styling 内部还要再拆 block 维度：

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

### 3.5 performance 的内部分类

第一期 performance profile 规划为：

- `guofeng_still`
- `guofeng_turn_back`
- `guofeng_hold_fan`
- `guofeng_hold_book`
- `guofeng_hold_umbrella`
- `guofeng_lean_rail`
- `guofeng_slow_walk`

## 4. 命名规范

### 4.1 通用规则

- 所有内部 `id` 使用英文 `kebab-case`
- 所有 `family` / `enum` / `tag` 使用英文 `snake_case`
- 所有用户可见标题使用中文
- 所有 `title` 都必须能被产品直接使用，不允许保留临时标题
- 不允许再出现 `scene-<hash>` 这类不可读 id

### 4.2 scene id 规则

scene id 统一格式：

`<theme>-<setting>-<tone-or-lighting>`

示例：

- `modern-window-softlight`
- `modern-cafe-candid`
- `guofeng-courtyard-natural`
- `guofeng-corridor-editorial`
- `modern-bar-flash`

说明：

- `theme` 只表达资产主题，不表达季节
- `setting` 只表达空间类型
- 最后一段优先表达最关键的光线/气质区分

### 4.3 scene family 规则

scene family 统一格式：

`<theme>_<setting>`

示例：

- `modern_window`
- `modern_cafe`
- `guofeng_courtyard`
- `guofeng_corridor`
- `guofeng_study`

scene family 的作用是：

- 给 rules 做归类
- 给 overlay 做可叠加范围控制
- 减少多个近似 scene 的重复配置

### 4.4 styling id 规则

styling id 统一格式：

`<gender_scope>-<theme>-<tone>-<profile>`

示例：

- `female-guofeng-natural-soft`
- `female-guofeng-fashion-editorial`
- `female-modern-chinese-daily`
- `unisex-natural-soft-fallback`
- `male-clean-natural-fallback`

### 4.5 performance id 规则

performance id 统一格式：

`<theme>-<action>-<pose>`

示例：

- `guofeng-still-front`
- `guofeng-turn-back`
- `guofeng-hold-fan`
- `guofeng-hold-book`
- `guofeng-lean-rail`

### 4.6 overlay id 规则

季节 overlay：

- `season-spring-blossom`
- `season-summer-lotus`
- `season-autumn-leaf`
- `season-winter-snow`

节气 overlay：

- `solarterm-yushui`
- `solarterm-qingming`
- `solarterm-xiaoman`
- `solarterm-xiaoshu`
- `solarterm-bailu`
- `solarterm-shuangjiang`
- `solarterm-xiaoxue`
- `solarterm-dongzhi`

## 5. 当前资产命名清洗建议

以下 5 条 scene 需要优先清洗：

| 当前 id | 当前 title | 建议新 id | 建议 family | 备注 |
| --- | --- | --- | --- | --- |
| `scene-35aef68d` | 绿植花园清透人像 | `modern-garden-backlight` | `modern_garden` | 户外绿植花园、自然逆光、清新甜感 |
| `scene-98033eb1` | 暗调酒馆闪光人像 | `modern-bar-flash` | `modern_bar` | 餐吧/酒馆、直闪、时装感 |
| `scene-41e220d6` | 生活感人像 | `modern-wheatfield-goldenhour` | `modern_field` | 麦田、黄金时刻、治愈系 |
| `green-outdoor-b9edbc24` | 绿意清新人像 | `modern-greenery-bokeh` | `modern_garden` | 绿色树叶 + 逆光光斑 |
| `scene-473e9e49` | 生活感人像 | `modern-cherry-blossom-spring` | `modern_garden` | 春日樱花、近景回眸 |

清洗要求：

- 新 id 必须一眼能读懂
- title 需要能区分，不允许两个都叫“生活感人像”
- family 要统一进入规则系统

## 6. 可执行清单

### Phase 0. 冻结命名和分类规范

- [ ] 冻结 scene 的内部分类维度：`theme / tone / setting / season / risk`
- [ ] 冻结用户侧一级分类：`自然国风 / 时尚国风 / 春夏秋冬 / 节气系列`
- [ ] 冻结 `scene id / scene family / styling id / performance id / overlay id` 命名规则
- [ ] 冻结 `hair_policy` 三档：`strict_lock / soft_lock / ornament_only`
- [ ] 明确当前阶段不改代码，只整理规划稿

交付物：

- 一个命名规范文档
- 一个分类枚举草案

### Phase 1. 现有资产盘点与映射

- [ ] 盘点现有 22 条 scene 的分类归属
- [ ] 盘点现有 7 条 styling 的兼容定位
- [ ] 盘点现有 17 条 rule 覆盖范围
- [ ] 标记无 rule 的 scene
- [ ] 标记 title 重复、id 不规范、family 缺失的 scene

交付物：

- `scene_inventory_audit.md`
- `scene_rename_mapping.md`
- `scene_rule_gap_checklist.md`

### Phase 2. 规划 scene 新分类

- [ ] 按内部分类把现有现代 scene 归到 `modern` 体系
- [ ] 新建 `guofeng_natural` 基础场景包清单
- [ ] 新建 `guofeng_fashion` 基础场景包清单
- [ ] 给每个基础 scene 预填 `theme / tone / setting / season / risk`
- [ ] 区分“基础 scene”与“overlay”，不允许混写

第一期基础 scene 建议清单：

`guofeng_natural`

- [ ] 庭院
- [ ] 廊下
- [ ] 窗边
- [ ] 竹林
- [ ] 荷塘
- [ ] 古桥
- [ ] 书房

`guofeng_fashion`

- [ ] 冷调回廊
- [ ] 暗色戏台侧区
- [ ] 高对比屏风空间
- [ ] 极简东方棚拍
- [ ] 夜色庭院
- [ ] 灯笼巷口

交付物：

- `scene_taxonomy_draft.md`
- `scene_pack_guofeng_natural_draft.md`
- `scene_pack_guofeng_fashion_draft.md`

### Phase 3. 规划 overlay 分类

- [ ] 冻结四季 overlay：春樱 / 夏荷 / 秋叶 / 冬雪
- [ ] 冻结第一期 8 个节气 overlay
- [ ] 为每个 overlay 明确可改字段
- [ ] 为每个 overlay 明确禁止改字段
- [ ] 建立 `overlay -> compatible_scene_family` 映射规则

overlay 可改字段：

- 环境附加元素
- 光线调性微调
- 空气状态
- 道具建议
- 色彩倾向
- 情绪标签

overlay 禁改字段：

- 主 scene 骨架
- 主镜头结构
- 主发型结构
- 身份锁定策略

交付物：

- `scene_overlay_seasonal_draft.md`
- `scene_overlay_solar_terms_draft.md`
- `overlay_compatibility_matrix.md`

### Phase 4. 规划 styling 分类与命名

- [ ] 把现有 7 条 styling 归到“保留 / fallback / 待拆分”三类
- [ ] 明确第一期只做女性国风分流
- [ ] 给每个新 styling profile 定中文标题和英文 id
- [ ] 给每个 styling profile 规划 block 字段
- [ ] 明确哪些字段属于妆容、哪些属于服饰、哪些属于发饰

建议第一期新 styling profile：

- [ ] `female-guofeng-natural-soft`
- [ ] `female-guofeng-fashion-editorial`
- [ ] `female-modern-chinese-daily`
- [ ] `unisex-natural-soft-fallback`
- [ ] `unisex-structured-editorial-fallback`
- [ ] `male-clean-natural-fallback`
- [ ] `male-sharp-editorial-fallback`

交付物：

- `styling_profile_taxonomy.md`
- `styling_profile_naming.md`
- `styling_block_schema_draft.md`

### Phase 5. 规划 performance 分类与命名

- [ ] 冻结第一期 performance profile 数量
- [ ] 统一 performance id 命名规则
- [ ] 为每个 profile 补中文标题、动作描述和姿态边界
- [ ] 明确哪些动作需要道具
- [ ] 明确哪些动作和某些 scene family 不兼容

交付物：

- `performance_profile_draft.md`
- `performance_scene_compatibility.md`

### Phase 6. 规划 rule 体系

- [ ] 把现有 rule 结构升级为 `default / recommended / forbidden`
- [ ] 给每个 scene family 规划默认 styling 候选
- [ ] 给每个 theme 规划推荐 styling 候选
- [ ] 给每个 scene 规划 performance 候选
- [ ] 给高风险 scene 补禁用项

rule 第一阶段至少要能回答的问题：

- 这个 scene 默认应该配什么 styling
- 推荐配什么 styling
- 绝对不能配什么 styling
- 默认动作是什么
- 推荐动作是什么
- 哪些 outfit tag 禁止出现
- 是否要覆盖 `hair_policy`

交付物：

- `scene_rule_matrix_draft.md`
- `scene_styling_rule_upgrade_spec.md`

### Phase 7. 迁移映射规划

- [ ] 把当前 scene 映射到新 family
- [ ] 把当前 styling 映射到新 profile 体系
- [ ] 标出可直接沿用项
- [ ] 标出必须重命名项
- [ ] 标出后续代码实现时的读取优先级

交付物：

- `scene_migration_mapping.md`
- `styling_migration_mapping.md`
- `compatibility_read_order_spec.md`

## 7. 优先级排序

必须先做：

1. 命名规范冻结
2. 现有 scene 清洗映射
3. scene family 分类
4. styling profile 分类
5. rule 升级草案

第二批再做：

6. 国风基础 scene pack 细化
7. seasonal overlay
8. solar term overlay
9. performance profile

最后再做：

10. 前端用户侧分类文案
11. 后端实现顺序
12. 实际代码改造

## 8. 本阶段完成标准

本阶段算完成，至少要满足以下条件：

- 所有 scene 都被分到明确的内部分类
- 所有不规范 id 都有明确的新命名建议
- 所有 styling 都被明确归类为“保留 / fallback / 待拆”
- 国风基础 scene pack 清单冻结
- 四季与节气 overlay 清单冻结
- rule 新结构冻结
- 另一个 agent 拿到这些文档后，不需要再自行决定命名规则和分类框架

## 9. 建议新增的规划文档

这一轮整理建议最终产出以下文档，不改代码，只补规划稿：

- `scene_inventory_audit.md`
- `scene_rename_mapping.md`
- `scene_taxonomy_draft.md`
- `scene_pack_guofeng_natural_draft.md`
- `scene_pack_guofeng_fashion_draft.md`
- `scene_overlay_seasonal_draft.md`
- `scene_overlay_solar_terms_draft.md`
- `styling_profile_taxonomy.md`
- `styling_block_schema_draft.md`
- `performance_profile_draft.md`
- `scene_rule_matrix_draft.md`
- `scene_migration_mapping.md`

如果只做最小集，优先先补这 5 份：

- `scene_rename_mapping.md`
- `scene_taxonomy_draft.md`
- `styling_profile_taxonomy.md`
- `scene_rule_matrix_draft.md`
- `scene_overlay_seasonal_draft.md`
