# 男生发型系统重构交付文档

## 1. 文档目的

这份文档用于交付给另一个 agent，继续完成男生发型系统从“旧单层发型库”向“前端展示预设 + 后端结构主库 + modifier 库 + 工艺库”的重构工作。

本文档覆盖四件事：

- 前端用户最终看到的发型选择方式与分类方案
- 后端对应的 block 拆分方式与 Prompt 装配逻辑
- 如何补充并替换原有男生发型库的规则与具体做法
- 后续获授权后，如何补充展示图/生成图，以及生成结果的验收标准

## 2. 当前结论与边界

### 2.1 已完成的分析结论

- 已从即山川 B 站合集 `126` 条视频中整理出男生发型数据。
- `126` 是视频数，不是发型类数。
- 去重归并后形成：
  - `33` 个主发型子类
  - `7` 个 modifier
- 当前正式后端男发库为单文件，只有 `23` 条。
- 当前前端展示映射已整理出 `48` 个展示预设。

### 2.2 关键原则

- 推荐层保留用户语言和细分别名。
- 生成层只吃结构化组合，不直接吃营销词。
- 不能把 `括号刘海 / 逗号刘海 / 港风 / 凌乱纹理` 直接当唯一主发型。
- 不能把“工艺”和“结构”继续混在一个单层列表里。
- 在用户没有明确允许之前，不执行新的图片生成。

### 2.3 当前相关文件

- 正式旧库：
  - `/home/lcy/AIFace/backend/app/data/faceprompt/hairstyles_male.json`
- 新结构草案：
  - `/home/lcy/AIFace/template/male_hairstyle_expanded.json`
- Prompt block 草案：
  - `/home/lcy/AIFace/template/male_hairstyle_prompt_block_draft.json`
  - `/home/lcy/AIFace/template/male_hairstyle_prompt_block_draft.md`
- 前端展示名映射草案：
  - `/home/lcy/AIFace/template/male_frontend_display_mapping.json`
  - `/home/lcy/AIFace/template/male_frontend_display_mapping.md`
- 分类分析来源：
  - `/home/lcy/AIFace/template/jishanchuan_refined_prompt_safe_taxonomy.json`
  - `/home/lcy/AIFace/template/jishanchuan_refined_prompt_safe_taxonomy.md`

## 3. 前端用户选择方案

### 3.1 用户最终看到的一级分类

前端一级分类采用更接近用户语言的 5 类：

- `清爽短发`
- `韩系分线`
- `轻熟背头`
- `个性长发`
- `烫卷造型`

这是展示层分类，不等于后端底层分类。

### 3.2 当前展示预设数量

- 清爽短发：14
- 韩系分线：10
- 轻熟背头：10
- 个性长发：7
- 烫卷造型：7
- 合计：48

### 3.3 用户交互路径

推荐的前端交互路径：

1. 用户先选择一级分类。
2. 用户在该分类下选择一个展示预设名。
3. 前端将该展示预设名对应的 `preset_id` 或映射对象提交给后端。
4. 后端把这个展示预设展开为：
   - `structure_id`
   - `modifier_ids`
   - `technique_ids`
5. 后端再组装成最终 Prompt block，参与生成。

### 3.4 前端展示层不应该直接暴露给用户的内容

以下内容不建议以一级卡片或独立主发型形式直接展示给用户：

- `modifier_bracket_fringe`
- `modifier_comma_fringe`
- `modifier_long_fringe`
- `modifier_side_fringe`
- `modifier_hk_vibe`
- `modifier_messy_texture`
- `modifier_commute_clean`

这些应该隐藏在预设组合逻辑里，或者只做高级筛选标签，不做主卡片。

## 4. 后端目标架构

## 4.1 目标拆分

后端男生发型数据不应继续维持单层 `hairstyles_male.json` 模式，而应拆成至少 4 层：

1. `hairstyle_structures_male.json`
2. `hairstyle_modifiers_male.json`
3. `hairstyle_techniques_male.json`
4. `hairstyle_presets_male.json`

其中：

- `structures` 决定骨架
- `modifiers` 决定局部修饰和风格
- `techniques` 决定烫发工艺和发丝质感来源
- `presets` 决定前端展示名到后端真实组合的映射

### 4.2 结构主库定义

结构主库是“骨架库”，必须单独拿出来就能稳定生图。

它主要控制：

- 长度
- 主轮廓
- 前区/露额关系
- 分线方式
- 两侧和后颈处理
- 顶区体积与走向

#### 推荐纳入结构主库的 33 个主发型子类

前刺刺感类：

- 立体前刺
- 纹理前刺
- 美式前刺
- 凌乱抓刺
- 微分前刺
- 前刺老虎头
- 三七背刺

碎盖盖片类：

- 立体碎盖
- 短碎栗子头
- 微分碎盖

分线偏分类：

- 长纹理侧分
- 微分纹理
- 基础侧分
- 纹理三七分
- 二八侧分
- 偏分三七
- 韩式三七分
- 三七侧分
- 港风分线

背头侧背油头类：

- 纹理背头
- 三七侧背
- 侧背短发
- 复古油头
- 长纹理侧背
- 龙须背头
- 湿发侧背
- 蓬松侧背
- 四六分侧背
- 长刘海侧背

基础短发类：

- 基础短发
- 韩式小平头

中长发/港风类：

- 港风纹理
- 港风中长发

说明：

- 上述 33 类已经整理到 `/home/lcy/AIFace/template/male_hairstyle_expanded.json`。
- 其中有些名称仍带风格或局部特征，但在本阶段可先作为“结构预设 ID”落地，后续再继续拆纯化。

### 4.3 Modifier 库定义

modifier 是“局部修饰库”，不能单独生图，只能叠加在结构之上。

第一期直接使用当前已整理的 7 个：

- `modifier_bracket_fringe`
- `modifier_comma_fringe`
- `modifier_long_fringe`
- `modifier_side_fringe`
- `modifier_hk_vibe`
- `modifier_messy_texture`
- `modifier_commute_clean`

建议第二期再补 3 个：

- `modifier_wet_finish`
- `modifier_pomade_gloss`
- `modifier_dragon_whisker_front`

### 4.4 工艺库定义

工艺库是“做法库”，描述的是头发如何被烫出、撑起、产生卷度或纹理，不是发型骨架本身。

建议迁入工艺库的条目：

- `male-texture-perm`
- `male-air-cushion-perm`
- `male-root-lift-perm`
- `male-clip-perm`
- `male-tin-foil-perm`
- `male-wool-perm`
- `male-french-lazy-perm`

建议降级为 legacy：

- `male-firework-perm`

### 4.5 展示预设库定义

展示预设库用于承接前端显示词，不直接参与图像骨架控制。

一个展示预设至少包含：

- `displayName`
- `displayGroup`
- `categoryKey`
- `categoryLabel`
- `structureId`
- `modifierIds`
- `techniqueIds`
- `notes`

当前整理好的映射文件是：

- `/home/lcy/AIFace/template/male_frontend_display_mapping.json`

## 5. Prompt block 装配规则

### 5.1 装配顺序

后端组装 Prompt block 时，推荐固定顺序：

1. 主结构 block
2. modifier block
3. 工艺 block
4. 发色 block
5. 场景 block
6. 光影 block
7. 妆造 block
8. 服饰 block
9. 构图与镜头 block

其中发型相关只负责前 1 到 3 层。

### 5.2 主结构 block 应包含的核心字段

建议最少包含：

- `hair_length`
- `hair_silhouette`
- `hair_texture`
- `hair_volume`
- `hair_parting`
- `sideburn_nape`
- `hair_tail_finish`
- `bangs_type`
- `bangs_density`
- `bangs_length`
- `bangs_split`
- `bangs_face_framing`

### 5.3 Modifier block 负责的内容

modifier 只允许调整以下内容：

- 刘海 opening 方式
- 前区修脸方式
- 凌乱程度
- 通勤清爽程度
- 港风氛围
- 局部湿发效果
- 局部油头光泽

禁止 modifier 直接重写：

- 头发主长度
- 主轮廓
- 基础分线方式
- 两侧和后颈结构

### 5.4 工艺 block 负责的内容

工艺 block 只能影响：

- 发丝卷度
- 发丝束感
- 根部支撑
- 蓬松方式
- 烫后纹理感

禁止工艺 block 直接把“前刺”改成“中分”，或把“短发”改成“中长发”。

## 6. 替换旧男发库的规则

### 6.1 当前旧库问题

当前 `/home/lcy/AIFace/backend/app/data/faceprompt/hairstyles_male.json` 的 23 条数据存在几个问题：

- 把结构、工艺、风格混在同一层
- 粒度不一致
- 很多热门细分类没有被单独表达
- 一些老旧工艺词还在主库里

### 6.2 旧库迁移原则

不要做“23 + 33 直接拼接”。

正确做法是：

1. 保留旧 ID 的兼容层
2. 新增结构主库、modifier 库、工艺库、展示预设库
3. 由展示预设去引用新结构和旧兼容项
4. 模板服务逐步改成按预设解析，不再直接依赖单层发型库

### 6.3 旧库条目的迁移建议

#### 应拆分升级的旧条目

- `male-forward-spikes`
- `male-french-short-texture`
- `male-micro-part-cover`
- `male-chestnut-head`
- `male-korean-37-part`
- `male-middle-micro-part`
- `male-vintage-slick-back`
- `male-side-part-pomade`

#### 应保留为独立结构的旧条目

- `male-american-buzz`
- `male-flat-short-cut`
- `male-fade-buzz`
- `male-mullet`
- `male-wolf-tail`
- `male-japanese-wavy-long`
- `male-samurai-half-bun`

#### 应迁移到工艺库的旧条目

- `male-texture-perm`
- `male-air-cushion-perm`
- `male-root-lift-perm`
- `male-clip-perm`
- `male-tin-foil-perm`
- `male-wool-perm`
- `male-french-lazy-perm`
- `male-firework-perm`

### 6.4 兼容策略

第一阶段不能直接删除旧 `hairstyles_male.json`，而应该：

- 保留旧文件给历史接口兜底
- 新增解析层，把前端展示预设展开成结构化组合
- 在模板服务中支持：
  - 旧 `hairstyle_id`
  - 新 `preset_id`

建议在服务层新增一个解析函数，例如：

- `resolve_male_hairstyle_preset()`

该函数职责：

1. 输入 `preset_id`
2. 读取 `hairstyle_presets_male.json`
3. 找到 `structureId / modifierIds / techniqueIds`
4. 读取各自库文件
5. 合并为最终发型 Prompt block

## 7. 具体实施步骤

### 7.1 数据落库

由另一个 agent 完成以下数据文件：

- `backend/app/data/faceprompt/hairstyle_structures_male.json`
- `backend/app/data/faceprompt/hairstyle_modifiers_male.json`
- `backend/app/data/faceprompt/hairstyle_techniques_male.json`
- `backend/app/data/faceprompt/hairstyle_presets_male.json`

初始数据来源分别为：

- structures：`/home/lcy/AIFace/template/male_hairstyle_expanded.json`
- modifiers：`/home/lcy/AIFace/template/male_hairstyle_prompt_block_draft.json`
- presets：`/home/lcy/AIFace/template/male_frontend_display_mapping.json`
- techniques：从旧 `hairstyles_male.json` 拆出烫发类

### 7.2 服务层改造

建议改造文件：

- `/home/lcy/AIFace/backend/app/services/templates.py`

要完成的事情：

- 增加对新四库的加载逻辑
- 增加 `preset -> structure/modifier/technique` 的解析逻辑
- 兼容旧 `hairstyle_id` 请求
- 返回给前端的展示信息优先使用预设库

### 7.3 前端改造

前端应优先读取预设库而不是直接读取底层结构库。

前端层应该拿到的是：

- 分组名
- 展示名
- 封面图
- 简短描述
- preset id

前端不需要知道 modifier 和工艺的完整细节。

### 7.4 测试要求

至少完成以下验证：

- 能根据 `preset_id` 正确解析出结构组合
- 旧 `hairstyle_id` 不报错
- 同一展示名多次请求时生成 Prompt 稳定
- modifier 不会改坏主结构
- technique 不会改坏主结构
- 返回给前端的分组名正确

## 8. 生图与展示图补充规则

### 8.1 当前状态

当前阶段尚未获准执行新的图片生成，因此只完成了数据结构和 Prompt block 设计。

### 8.2 后续获授权后应做的事

另一位 agent 在得到用户授权后，可以继续完成以下工作：

1. 为前端展示预设补封面图
2. 为重点结构款补示意图
3. 为高频款做 Prompt 校验图
4. 抽样验证 modifier 和工艺叠加后的稳定性

### 8.3 生图优先级建议

第一优先级先做前端首发高频款，建议优先：

- 美式前刺
- 立体前刺
- 纹理前刺
- 微分碎盖
- 短碎栗子头
- 韩式三七分
- 括号三七
- 逗号侧分
- 基础侧分
- 微分纹理
- 纹理背头
- 三七侧背
- 复古油头
- 湿发侧背
- 港风中长发

### 8.4 生成验收标准

每张图至少要满足以下要求：

- 主结构一眼可辨认
- modifier 只做局部修饰，不改坏主骨架
- 工艺感与结构兼容，不出现冲突
- 发型轮廓稳定，不能塌
- 发型长度、分线、露额程度与预设一致
- 两侧与后颈处理符合预期
- 发色不要污染背景和服饰
- 场景、妆造、服饰不要喧宾夺主，必须服务于发型展示

### 8.5 展示图建议镜头

为了让用户容易理解发型差异，建议展示图默认采用：

- 正面半身或胸像
- 三分之二侧脸
- 头顶与前区清晰可见
- 背头和侧背类可以额外补一个侧后角度
- 烫卷造型必须看得清卷度和根部体积

## 9. 交付给另一个 agent 的明确任务

另一个 agent 的工作目标应明确为：

1. 按本文档拆出男发四库
2. 保持旧接口兼容
3. 让前端改成读展示预设而不是旧单层发型库
4. 完成 `preset -> block` 的组装逻辑
5. 完成最小测试覆盖
6. 在得到用户授权后，再补封面图或生图验证

## 10. 推荐执行顺序

推荐另一个 agent 按如下顺序执行：

1. 整理并落库四份 JSON
2. 改服务层解析逻辑
3. 做后端测试
4. 改前端读取展示预设
5. 联调前后端
6. 用户确认后，再补展示图和生图验证

## 11. 最终目标

最终目标不是把男发类目“堆得更多”，而是把系统改造成：

- 前端对用户更友好
- 后端对 Prompt 更可控
- 推荐算法可以保留细粒度语言
- 生图算法只吃结构化参数
- 后续可以无痛扩展到发色、场景、妆造、服饰与光影系统
