# 发型提示词精修规范

更新时间：2026-04-06

## 1. 目标

这份规范用于约束 AIFace 当前男发结构化数据与 prompt 组装逻辑，解决以下问题：

- 发色描述混入 `structure` / `technique`，与独立发色系统冲突
- `technique` 抢占主发型定义，导致主结构辨识度下降
- 相邻发型之间缺少显式防串型约束
- 结构化字段职责不清，单个字段承载过多信息

本规范的执行范围优先覆盖：

- 男发 `structure`
- 男发 `modifier`
- 男发 `technique`
- 男发 `preset`
- 后端与 Faceprompt 的发型 prompt 组装层

## 2. 硬性规则

### 2.1 Structure 只定义主发型骨架

`structure` 负责回答“这是什么发型”。

允许定义：

- 长度
- 主轮廓
- 主走向
- 分线
- 两侧与后颈处理
- 前区基本关系

不允许定义：

- 染发颜色
- 染发工艺
- 与具体烫法强绑定的附加工艺词

### 2.2 Modifier 只定义局部修饰

`modifier` 只允许影响：

- 刘海类型
- 脸侧修饰
- 局部气质修饰
- 轻度凌乱感 / 通勤整洁感 / 港风氛围等附加修饰

`modifier` 不允许改写：

- 主结构名称
- 主长度区间
- 主分线方案
- 两侧与后颈的基础处理

### 2.3 Technique 只定义工艺和质感

`technique` 只允许影响：

- 发丝纹理
- 发根支撑
- 顶部体积
- 卷度级别
- 湿感 / 光泽 / 收束质感
- 发尾完成方式

`technique` 不允许改写：

- 主发型名称
- 主长度
- 主轮廓
- 主分线
- 两侧与后颈基础结构
- 刘海主定义

### 2.4 Hair Color 永远独立

发色系统只能由独立的 `hair_color` block 负责。

因此：

- `structure.promptCore` 不写黑色、深棕、冷棕等颜色词
- `technique.promptAddition` 不写颜色词
- `hair_shape` 子字段里不夹带染发描述
- `technique` 不再作为默认发色来源

### 2.5 Constraints 必须包含防串型约束

每条主发型结构至少需要 1 条“反串型约束”，明确说明：

- 不得变成哪些相邻款式
- 当前发型的主结构辨识度必须保持清楚

这条约束必须进入实际 prompt，而不是只存在数据层。

## 3. 字段职责规范

### 3.1 `hair_shape`

- `hair_length`：只写长度区间
- `hair_silhouette`：只写主轮廓和骨架识别点
- `hair_texture`：只写纹理、束感、卷度、湿感
- `hair_volume`：只写顶部支撑、空气感、体积
- `hair_parting`：只写分线方式
- `sideburn_nape`：只写鬓角与后颈区处理
- `hair_tail_finish`：只写发尾收口和尾部完成方式

禁止把整段自然语言散文塞进任一子字段。

### 3.2 `bangs`

- `bangs_type`：刘海类型
- `bangs_density`：厚薄
- `bangs_length`：长度落点
- `bangs_split`：开合方式
- `bangs_face_framing`：脸侧修饰关系

### 3.3 `hair_color`

- `hair_color_tone`
- `hair_color_depth`
- `hair_color_temperature`
- `hair_color_technique`
- `hair_color_distribution`

## 4. 组装优先级

固定使用：

`structure -> modifier -> technique -> hair_color -> constraints -> prompt`

解释：

1. `structure` 提供主骨架
2. `modifier` 只覆盖局部修饰字段
3. `technique` 只覆盖允许的工艺字段
4. `hair_color` 独立处理，不从 `technique` 接管
5. `constraints` 作为独立发型约束输出到 prompt

## 5. Prompt 组装规则

### 5.1 `hair_only`

必须输出：

- `identity_lock`
- `output_spec`
- `edit_scope`
- `hair_shape`
- `bangs`
- `hair_color`
- `hair_constraints`
- `quality_control`
- `negative_constraints`

### 5.2 `full_stylize`

必须输出：

- `identity_lock`
- `output_spec`
- `edit_scope`
- `hair_shape`
- `bangs`
- `hair_color`
- `hair_constraints`
- `scene`
- `styling`
- `subject_performance`
- `quality_control`
- `negative_constraints`

### 5.3 `scene_only`

`scene_only` 不再输出可编辑发型 block，而是继续使用：

- `hair_shape_lock`
- `bangs_lock`
- `hair_color_lock`
- `hair_motion_constraint`

## 6. 本轮执行项

本轮立即执行以下改造：

1. 清理男发 `technique` 中的颜色混写
2. 把男发 `technique.promptAddition` 改成“附加效果”写法
3. 为 33 条男发 `structure` 补 1 条反串型约束
4. 在后端和 Faceprompt prompt 组装层接入 `hair_constraints`
5. 同步 Faceprompt 数据和后端运行副本

## 7. 验收标准

满足以下条件视为本轮完成：

- `technique.promptAddition` 不再写“发型改为某某烫”式主结构替换语气
- `technique` 文本中不再出现发色描述
- 每条男发 `structure.constraints` 至少有 1 条 `不得变成...` 反串型约束
- `hair_only` 与 `full_stylize` 最终 prompt 中能看到“发型关键约束”或同等语义段落
- Faceprompt 与后端运行数据保持一致
