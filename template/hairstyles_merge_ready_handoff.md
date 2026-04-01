# 发型 Merge Ready 交付说明

更新时间：2026-03-28

## 可直接替换的文件

- 男发完整 merge 版：
  [hairstyles_male_merge_ready.json](/home/lcy/AIFace/template/hairstyles_male_merge_ready.json)
- 女发完整 merge 版：
  [hairstyles_female_merge_ready.json](/home/lcy/AIFace/template/hairstyles_female_merge_ready.json)

## 对应替换目标

- 用男发 merge 版替换：
  `Faceprompt/src/faceprompt/data/hairstyles_male.json`
- 用女发 merge 版替换：
  `Faceprompt/src/faceprompt/data/hairstyles_female.json`

## 数量确认

- 男发：25 条
- 女发：33 条

## 合并口径

- 保留原始正式库全部条目
- 插入新增发型草案
- 按新的分类顺序重排，方便后续前端筛选和模板管理

## 当前保留策略

- 原有条目内容未改写
- 新增条目使用草案字段结构补齐
- 新增条目的 `controlProfile` 暂时保留为 `null`
- 新增条目的封面字段仍为占位状态，待后续补图

## 如果另一个 agent 继续处理

建议顺序：

1. 先直接用 merge ready 文件替换正式 JSON
2. 跑数据校验或测试
3. 再补 `controlProfile`
4. 最后补封面图和更新时间
