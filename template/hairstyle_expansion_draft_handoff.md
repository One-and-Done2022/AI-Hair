# 新增发型草案交付说明

更新时间：2026-03-27

## 交付内容

- 新增男生发型草案：5 条
- 新增女生发型草案：13 条
- 合计：18 条

对应 JSON 草案文件：

- [hairstyle_expansion_draft.json](/home/lcy/AIFace/template/hairstyle_expansion_draft.json)

## 覆盖范围

### 男生新增 5 类

- 微分碎盖
- 渐变寸头
- 气垫烫
- 定位烫
- 法式慵懒卷

### 女生新增 13 类

- 内扣波波头
- 齐脸短发
- 赫本短发
- 锁骨发
- 高层次锁骨发
- 微卷锁骨发
- 齐肩发
- 狼剪
- 原版公主切 / 姬发式
- 黑长直
- 人鱼卷
- 蛋蛋卷 / 蛋卷头
- 港风大波浪

## 字段说明

草案字段对齐现有发型 JSON：

- `id`
- `gender`
- `title`
- `styleLine`
- `summary`
- `promptCore`
- `detailTags`
- `constraints`
- `pairingAdvice`
- `shotAdvice`
- `expressionAction`
- `controlProfile`
- `referenceNotes`
- `referenceSourceIds`
- `categoryKey`
- `categoryLabel`
- `coverImagePath`
- `coverImageUpdatedAt`
- `coverImageSource`

## 当前草案约定

- `promptCore`、`constraints`、`detailTags`、`pairingAdvice`、`shotAdvice`、`expressionAction` 已写到可直接落库的程度
- `controlProfile` 统一先设为 `null`
  原因：现有正式库里也只有少数发型带结构化控制，新增项先走基础提示词模式更稳
- `coverImagePath` 已给占位路径
- `coverImageUpdatedAt` 暂时为空字符串
- `coverImageSource` 统一写为 `draft_pending_render`

## 接手建议

另一个 agent 接手时，建议按这个顺序继续：

1. 先把 `hairstyle_expansion_draft.json` 合并进正式发型库
2. 再根据是否需要做推荐系统，补部分高优先级发型的 `controlProfile`
3. 最后再批量生成对应封面图并回填 `coverImageUpdatedAt`

## 优先建议补 `controlProfile` 的发型

- 男生：微分碎盖、气垫烫、定位烫
- 女生：锁骨发、高层次锁骨发、黑长直、原版公主切、人鱼卷
