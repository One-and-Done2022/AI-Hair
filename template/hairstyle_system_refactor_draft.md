# AIFace 发型系统重构草案

更新时间：2026-04-01

## 1. 草案定位

这份文档用于把当前 AIFace 的发型能力，从“完整发型模板库”升级为“结构化发型系统”。

目标不是立刻推翻现有后端，而是先确定一套可落地的中间草案，方便后续继续拆成：

- JSON schema
- 数据字典
- preset 配置表
- prompt 组装逻辑
- 旧版发型的兼容映射

## 2. 当前系统现状

当前后端真实生效发型数据：

- 男发 23 类
- 女发 33 类
- 合计 56 类

当前系统特点：

- 以完整发型条目为主，不是可组合系统
- 主分类依赖 `gender + categoryKey/categoryLabel`
- 每条发型附带 `styleLine` 与 `detailTags`
- 刘海未被拆成独立维度
- 发色不是独立结构化模块

这套模式适合 MVP，但不适合高精度 prompt 控制。主要问题：

- 发型特征耦合严重，长度、层次、卷度、前区走向混在一个标签里
- 展示名难以稳定映射到底层 prompt
- 后续做筛选、推荐、A/B 测试、算法对齐时扩展成本高

## 3. 重构目标

新系统需要同时满足四个目标：

1. 机器可控
   底层维度必须足够结构化，能稳定拼 prompt。
2. 前端好用
   用户看到的仍然应该是易懂、好看的“成品发型名”。
3. 兼容旧数据
   现有完整发型条目不能直接作废，应该作为 preset 层保留并映射。
4. 便于扩展
   后续新增热门发型、发色、场景妆造时，不应重新推翻分类框架。

## 4. 设计原则

### 4.1 正交拆分

把发型拆成尽量独立的维度，避免一个字段同时表达多个特征。

### 4.2 双轨命名

每个发型组合同时维护：

- `system_id`
  结构化、稳定、给后端和 prompt 用
- `display_name`
  面向用户展示的商业化命名

### 4.3 旧库降级为 preset

当前后端已有的“前刺头”“辛芷蕾锁骨发”“法式慵懒卷”等，不再作为底层 ontology 主干，而是作为：

- `preset_recipe`
- `display preset`
- `legacy mapping target`

### 4.4 前端极简，后端硬核

前端不开放多维自由拼装，避免用户拼出不合理组合。

系统策略应为：

- 前端只展示高质量 preset
- 后端保存多维结构化参数
- prompt 使用结构化 recipe 组装

### 4.5 兼容规则先于全量开放

维度拆开后，必须同步维护：

- `compatibility_rules`
- `preset_recipe`

否则系统虽然可组合，但生成结果会失控。

## 5. 新系统分层

建议把发型系统拆成 5 层：

### 5.1 L1：性别作用域

- `male`
- `female`
- `unisex`

### 5.2 L2：发型主干维度

这一层只维护“形态骨架”，不直接承载商业化命名。

### 5.3 L3：附加维度

用于表达刘海、发色、染发工艺、局部修饰等附加信息。

### 5.4 L4：兼容规则

限制哪些维度可以组合，哪些组合应禁止或降权。

### 5.5 L5：成品预设

供前端直接点击和展示的高质量成品组合。

## 6. 女发主干草案

女发建议采用 `3D 主干 + 可选刘海 + 可选发色/染发工艺`。

### 6.1 维度 A：基础长度 `base_length`

- `pixie`
  超短
- `jaw`
  下颌长度
- `collarbone`
  锁骨长度
- `midlong`
  中长发
- `long`
  长发
- `waist`
  及腰长发

### 6.2 维度 B：层次结构 `layer_structure`

- `blunt`
  一刀切、零层次
- `low_layer`
  低层次
- `high_layer`
  高层次
- `feather`
  羽毛感层次
- `wolf`
  狼剪系层次
- `hime`
  公主切结构
- `jellyfish`
  水母剪结构

### 6.3 维度 C：质感工艺 `texture_pattern`

- `straight`
  直发
- `inner_curl`
  发尾内扣
- `soft_wave`
  柔卷
- `big_wave`
  大波浪
- `water_wave`
  水波纹
- `mermaid_wave`
  人鱼卷
- `wool_curl`
  羊毛卷
- `cloud_perm`
  云朵烫
- `egg_roll`
  蛋卷感卷度

### 6.4 可选维度 D：刘海 `bangs`

这层建议在 schema 里预留，但可分阶段上线。

- `none`
- `air`
- `french`
- `curtain`
- `full`
- `side_swept`

说明：

- 女发可以保留独立刘海维度
- 当前如果产品不打算开放 UI，可以先底层保留、前端隐藏
- 后续如要做修脸能力增强，再逐步放出

## 7. 男发主干草案

男发建议采用 `4D 骨架 + 可选发色/染发工艺`，但这里的重点不是“可选刘海”，而是“前区设计必须作为隐式维度存在”。

### 7.1 男发产品原则

男发不建议在前端暴露独立刘海选择 UI。

原因：

- 男发用户不适合做细粒度自由拼装
- 男发前区设计和顶部长度、两侧处理耦合很强
- 一旦把刘海单独开放，极容易拼出不符合审美和头骨逻辑的组合

因此男发应采用：

- 前端只开放 preset
- 后端保留结构化维度
- `front_design` 由 preset 隐式封装

### 7.2 维度 A：两侧与后颈 `side_back_profile`

- `uniform_short`
  两侧后区统一保留
- `soft_taper`
  轻渐变
- `skin_fade`
  贴皮渐变
- `undercut`
  明显两边铲
- `down_perm_taper`
  服帖保留、顺贴侧区
- `mullet_back`
  后区保留狼尾

### 7.3 维度 B：顶部长度与轮廓 `top_shape`

- `buzz`
  极短寸头
- `short_textured`
  短碎发
- `crop`
  盖片短发
- `medium_fringe`
  中等长度碎盖
- `medium_long`
  顶部长一点的中长轮廓
- `long_parting`
  可明显偏分或向后梳理的长度
- `long_artistic`
  艺术长发

### 7.4 维度 C：表面质感与工艺 `texture_finish`

- `natural_straight`
  自然直发
- `flow_perm`
  气流感纹理烫
- `texture_perm`
  纹理烫
- `air_cushion_perm`
  气垫烫
- `spiky_perm`
  硬挺前刺质感
- `clip_perm`
  钢夹烫感
- `wool_perm`
  羊毛卷
- `foil_perm`
  锡纸烫
- `soft_wave_perm`
  微卷流向烫

### 7.5 维度 D：前区设计 `front_design`

这不是给用户单独选择的“刘海款式”，而是男发成型里必须保留的前区控制参数。

- `exposed`
  露额
- `forward_cover`
  向前覆盖
- `spiky_up`
  前刺向上
- `comma_part`
  逗号分
- `middle_part`
  中分或微分
- `side_part`
  侧分
- `slick_back`
  全部向后梳

### 7.6 可选补充维度：后区轮廓 `rear_profile`

当某些男发需要强调后颈轮廓时，建议单独预留：

- `clean_nape`
- `natural_nape`
- `mullet_tail`

说明：

- 第一阶段可以不放进所有 system_id
- 但像狼尾、长尾、艺术后区时，最好不要硬塞进 `side_back_profile`

## 8. 发色与染发工艺草案

发色建议独立为全局模块，不属于男发或女发主干。

### 8.1 发色基调 `color_tone`

- `natural_black`
- `soft_black`
- `dark_brown`
- `chestnut_brown`
- `ash_brown`
- `cold_gray_brown`
- `linen_blonde`
- `platinum_silver`
- `rose_pink`
- `wine_red`

### 8.2 染发工艺 `color_technique`

- `solid`
  全头纯染
- `highlight`
  线条挑染
- `balayage`
  画染
- `earloop`
  挂耳染
- `gradient`
  渐层染

### 8.3 使用原则

- 发色模块默认可为空
- 没指定时走 `natural_black` 或品牌默认自然色
- 染发工艺不能脱离发色单独存在

## 9. 双轨命名草案

### 9.1 `system_id` 规则

建议按结构化字段拼接生成：

女发：

`female_<base_length>_<layer_structure>_<texture_pattern>_<bangs?>_<color_tone?>_<color_technique?>`

男发：

`male_<side_back_profile>_<top_shape>_<texture_finish>_<front_design>_<rear_profile?>_<color_tone?>_<color_technique?>`

示例：

- `female_collarbone_high_layer_soft_wave_french_ash_brown_balayage`
- `male_skin_fade_short_textured_spiky_perm_spiky_up_platinum_silver_solid`
- `male_down_perm_taper_medium_fringe_flow_perm_middle_part_natural_black`

### 9.2 `display_name` 规则

`display_name` 不要求完全结构化，但必须满足：

- 可读
- 简短
- 有商业感
- 不与 system_id 强绑定

示例：

- 银灰高街前刺
- 法式氛围锁骨卷
- 韩系微分碎盖

## 10. 男发 preset 封装策略

男发最适合做“前端一键预设，后端隐式封装”。

### 10.1 前端展示层

前端只展示：

- 封面图
- 展示名
- 气质标签
- 适用人群说明

前端请求只传：

- `preset_id`

### 10.2 后端展开层

后端收到 `preset_id` 后，展开为结构化 recipe，例如：

```json
{
  "preset_id": "male_kstreet_spiky_01",
  "display_name": "高街前刺",
  "base_recipe": {
    "side_back_profile": "skin_fade",
    "top_shape": "short_textured",
    "texture_finish": "spiky_perm",
    "front_design": "spiky_up"
  }
}
```

### 10.3 核心价值

这样做的结果是：

- 用户不需要理解专业发型术语
- 前端不会开放危险的自由拼装
- 后端仍然保留可控、可验证的结构化参数
- 算法侧可以稳定做 prompt block 组装和质量校准

## 11. 男发核心预设草案

以下是男发一键生成预设的首批核心映射示例。

### 11.1 高街前刺

- `preset_id`: `male_kstreet_spiky_01`
- `display_name`: `高街前刺`
- `base_recipe`:
  - `side_back_profile = skin_fade`
  - `top_shape = short_textured`
  - `texture_finish = spiky_perm`
  - `front_design = spiky_up`

### 11.2 韩系微分碎盖

- `preset_id`: `male_korean_textured_fringe_01`
- `display_name`: `韩系微分碎盖`
- `base_recipe`:
  - `side_back_profile = down_perm_taper`
  - `top_shape = medium_fringe`
  - `texture_finish = flow_perm`
  - `front_design = middle_part`

### 11.3 痞帅逗号分

- `preset_id`: `male_comma_part_01`
- `display_name`: `痞帅逗号分`
- `base_recipe`:
  - `side_back_profile = down_perm_taper`
  - `top_shape = medium_long`
  - `texture_finish = natural_straight` 或 `flow_perm`
  - `front_design = comma_part`

### 11.4 美式复古油头

- `preset_id`: `male_vintage_slickback_01`
- `display_name`: `美式复古油头`
- `base_recipe`:
  - `side_back_profile = undercut`
  - `top_shape = long_parting`
  - `texture_finish = natural_straight`
  - `front_design = slick_back`

### 11.5 日系雅痞狼尾

- `preset_id`: `male_japanese_mullet_01`
- `display_name`: `日系雅痞狼尾`
- `base_recipe`:
  - `side_back_profile = soft_taper` 或 `skin_fade`
  - `top_shape = medium_long`
  - `texture_finish = flow_perm` 或 `soft_wave_perm`
  - `front_design = forward_cover` 或 `middle_part`
  - `rear_profile = mullet_tail`

## 12. 兼容旧 56 类的策略

旧版完整发型不建议直接废弃，而应变成“预设层”。

### 12.1 保留内容

继续保留旧字段：

- `id`
- `gender`
- `categoryKey`
- `categoryLabel`
- `styleLine`
- `detailTags`

### 12.2 新增映射字段

每个旧发型条目增加：

- `preset_id`
- `system_recipe`
- `legacy_aliases`
- `display_priority`
- `status`

### 12.3 映射方式

例如：

- “前刺头”
  映射到：
  `male_skin_fade_short_textured_spiky_perm_spiky_up`
- “辛芷蕾锁骨发”
  映射到：
  `female_collarbone_high_layer_straight_none`
- “法式慵懒卷”
  映射到：
  `female_midlong_low_layer_soft_wave_french`

说明：

- 旧名字继续给前端展示也可以
- 后端和 prompt 组装逐步切换为读取 `system_recipe`

## 13. `preset_recipe` 草案

真正给用户使用的，不应该是任意自由组合，而应该是高质量预设。

### 13.1 结构建议

每个 preset 至少包含：

- `preset_id`
- `gender_scope`
- `display_name`
- `base_recipe`
- `optional_variants`
- `style_line`
- `detail_tags`
- `hero_prompt_hint`
- `priority`
- `is_legacy_compatible`

### 13.2 男发 preset 示例

```json
{
  "preset_id": "male_korean_textured_fringe_01",
  "gender_scope": "male",
  "display_name": "韩系微分碎盖",
  "base_recipe": {
    "side_back_profile": "down_perm_taper",
    "top_shape": "medium_fringe",
    "texture_finish": "flow_perm",
    "front_design": "middle_part",
    "color_tone": "natural_black"
  },
  "style_line": "realistic_editorial",
  "detail_tags": ["韩系", "修饰脸型", "少年感", "自然蓬松"],
  "priority": 95,
  "is_legacy_compatible": true
}
```

### 13.3 预设职责

预设负责：

- 给前端展示
- 给运营做推荐位
- 给算法做重点校准
- 给旧版分类做平滑迁移

## 14. `compatibility_rules` 草案

这个模块是新系统能否稳定运行的关键。

### 14.1 规则类型

建议至少包含 4 类：

- `allowed`
  明确允许
- `forbidden`
  明确禁止
- `discouraged`
  技术上可生成，但不建议默认放出
- `preferred`
  在同类可选项中优先组合

### 14.2 典型规则示例

#### 女发

- `pixie` 不优先搭配 `balayage`
- `jellyfish` 默认不搭配 `inner_curl`
- `waist + wool_curl` 设为 `discouraged`
- `hime` 优先搭配 `straight`

#### 男发

- `comma_part` 必须要求顶部长度至少 `medium_fringe`
- `spiky_up` 不应搭配 `down_perm_taper + heavy cover`
- `slick_back` 必须要求露额，且顶部长度不能过短
- `buzz` 禁止搭配 `wool_perm`
- `skin_fade` 优先搭配 `spiky_up` 或 `exposed`
- `mullet_tail` 优先搭配 `soft_wave_perm` 或 `flow_perm`
- `down_perm_taper` 不建议搭配过强 `foil_perm`

#### 发色

- `earloop` 只对中长以上发型开放
- `platinum_silver` 默认不作为品牌通用默认色
- `highlight` 更适合层次明显或卷度明显的发型

## 15. Prompt 组装建议

发型相关 prompt 不建议继续直接读取“完整中文名”，而建议按 block 组装。

推荐拆成：

- `hair_base_shape`
- `hair_surface_texture`
- `hair_front_design`
- `hair_rear_profile`
- `hair_color`
- `hair_constraints`

### 15.1 女发组装逻辑

1. 长度
2. 层次
3. 质感
4. 刘海
5. 发色
6. 约束

### 15.2 男发组装逻辑

1. 两侧与后区基础处理
2. 顶部轮廓
3. 质感工艺
4. 前区设计
5. 后区轮廓
6. 发色
7. 约束

### 15.3 关键约束

- 男发 `front_design` 必须由 preset 驱动，不建议裸露给用户自由拼装
- 发色词汇要单独加权，避免污染服饰和背景
- 刘海描述不要和前区走向重复
- 卷度词汇不要重复叠加
- 旧版 preset 的商业名称不要直接进最终 prompt 主体

## 16. 建议的数据模型骨架

草案阶段建议先做 JSON ontology，而不是立刻做数据库。

### 16.1 基础字典层

- `hair_dimensions_male.json`
- `hair_dimensions_female.json`
- `hair_color_taxonomy.json`
- `hair_compatibility_rules.json`

### 16.2 预设层

- `hair_presets_male.json`
- `hair_presets_female.json`
- `hair_presets_legacy_mapping.json`

### 16.3 运行时输出层

运行时给接口输出的还是“成品发型卡片”，但每张卡片背后挂结构化 recipe。

## 17. 分阶段落地建议

### Phase 1：冻结 ontology

只做：

- 男发 4D 骨架
- 女发 3D 主干
- 发色模块
- 女发预留刘海模块
- 男发固化 `front_design`
- 定义 `system_id` 规则

输出物：

- schema 草案
- 维度词典
- 兼容规则草案

### Phase 2：构建高价值 preset

只挑最常用、最好看的 30 到 50 个预设先做。

输出物：

- 热门男发 preset
- 热门女发 preset
- 旧 56 类映射表

### Phase 3：小规模生图验证

重点验证：

- 是否更稳定
- 是否更容易控脸型修饰
- 是否减少词汇冲突

### Phase 4：后端接入

再去改：

- 数据文件
- schema
- catalog 拼装逻辑
- 前端筛选接口

## 18. 第一阶段推荐范围

如果要控制复杂度，第一阶段建议先这样收敛：

- 暂不开放用户自由组合
- 暂不开放男发独立刘海选择 UI
- 女发刘海先保留底层字段，不急着开放
- 暂不开放全量发色筛选 UI
- 先内部使用结构化 recipe 驱动 preset

也就是说：

- 底层先结构化
- 用户侧仍然点击“成品发型”

这样风险最小，也最容易验证效果。

## 19. 对当前项目最重要的结论

这次重构不应该理解为“新增更多发型名字”，而应该理解为：

- 把发型从“名称库”升级成“参数系统”

其中男发的核心原则是：

- 前端不开放独立刘海
- 后端必须保留 `front_design`
- 通过 preset 隐式封装前区修饰逻辑

当前最合理的推进顺序：

1. 先定 ontology / schema
2. 再定 compatibility rules
3. 再做 preset recipe
4. 再做小规模生图验证
5. 最后改后端与前端

## 20. 下一步建议

基于这份草案，下一步最值得继续做的是二选一：

### 方向 A：直接细化成 JSON Schema 草案

适合给后端和另一个 agent 继续实现。

### 方向 B：先做旧 56 类到新 recipe 的映射表

适合先解决兼容问题，让当前系统能平滑过渡。

如果继续往下推进，建议优先做方向 A，再补方向 B。
