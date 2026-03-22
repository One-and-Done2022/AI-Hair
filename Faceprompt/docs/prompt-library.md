# Faceprompt 提示词库

## 概览
这个提示词库面向中文图像模型，默认用于“以上传人物照片为原型”的人像再创作场景。库内数据同时支持两种用法：

1. 结构化使用：按场景、发型、动作、约束字段做程序拼装。
2. 成品使用：通过 CLI 直接渲染与线上后端接近的单张稳定版提示词。

默认硬约束：
- 第一优先级是保留参考人物真实身份特征，必须一眼看出是同一个人。
- 不改变脸型、五官比例、眼距、鼻梁、嘴型、肤色、年龄感、整体气质和性别表达。
- 忽略原背景、原服饰、原发型和原有动作，只保留同一位单人主体做换发和换背景创作。
- 统一带入基础负面约束，避免换脸、第二个人、AI 脸、五官漂移、假发感和光影冲突。
- 严格限制单张图只保留 1 个主体动作；如果主体动作已经占手，不再额外叠加抓头发或握杯类发型动作。

## 命令入口
- `make summary` 查看提示词库数量和风格线覆盖情况。
- `make lint` 校验数据完整性、来源索引和计划中的数量约束。
- `make test` 运行自动化测试。
- `make render-example` 渲染一条场景 + 发型组合示例。
- `make interactive` 进入交互式选择模式，按编号选择性别、场景和发型后生成完整提示词。

也可以直接使用 CLI：

```bash
make interactive
PYTHONPATH=src python3 -m faceprompt.cli list --category scene
PYTHONPATH=src python3 -m faceprompt.cli list --category hairstyle --gender male
PYTHONPATH=src python3 -m faceprompt.cli render --scene indoor-film-lifestyle --hairstyle female-french-lazy-waves
PYTHONPATH=src python3 -m faceprompt.cli render --scene morning-window-softlight --hairstyle male-forward-spikes
PYTHONPATH=src python3 -m faceprompt.cli render --scene morning-window-softlight --hairstyle male-forward-spikes --subject-action "靠在窗台边"
PYTHONPATH=src python3 -m faceprompt.cli interactive
```

交互模式会按 3 步完成：

1. 选择性别
2. 选择场景
3. 选择对应性别的发型

完成后会直接输出完整提示词，并附带对应的 `render` 命令，方便你后续复制复用。

## 场景分类
共 20 类场景，分为两条主线：

真实高级写真：
1. 室内生活感胶片写真
2. 清晨窗边软光人像
3. 胡桃木书房静物人像
4. 咖啡馆抓拍座位人像
5. 浴室镜前晨间人像
6. 酒店房间松弛感人像
7. 傍晚家居逆光人像
8. 楼道玄关安静框景人像
9. 床边半卧近景人像
10. 雨天窗边情绪人像

时尚大片：
1. 极简纯色棚拍
2. 冷调金属空间人像
3. 复古电影包厢人像
4. 都市夜色霓虹人像
5. 画廊白盒子空间人像
6. 戏剧化强侧光人像
7. 高级酒店大堂人像
8. 天台风场人像
9. 暗调酒吧吧台人像
10. 后台化妆镜前人像

## 男性发型分类
共 20 类：

1. 前刺头
2. 栗子头
3. 美式圆寸
4. 法式短碎发
5. 短平头
6. 摩根碎盖
7. 锡纸烫
8. 钢夹烫
9. 烟花烫
10. 纹理烫
11. 男士羊毛卷
12. 韩系三七分
13. 逗号刘海
14. 中分微分
15. 港风复古背头
16. 侧分油头
17. 鲻鱼头
18. 狼尾发型
19. 日系微卷长发
20. 武士半扎发

## 女性发型分类
共 20 类：

1. 一刀切波波头
2. 挂耳初恋短发
3. 法式推边短发
4. 少年感超短发
5. 日系苹果头
6. 辛芷蕾锁骨发
7. 边缘层次剪
8. 高层次中长发
9. 日系羽毛剪
10. 鱼尾烫中长发
11. 法式慵懒卷
12. 韩式气垫烫
13. 木马卷
14. 水波纹
15. 羊毛卷
16. 云朵烫
17. 麦穗卷
18. 新中式黑长直
19. 改良公主切
20. 瀑布直发

## 结构化字段
运行时记录会统一暴露这些字段：

- `id`
- `title`
- `categoryType`
- `gender`
- `styleLine`
- `summary`
- `promptCore`
- `detailTags`
- `constraints`
- `negativePrompt`
- `pairingAdvice`
- `shotAdvice`
- `expressionAction`
- `referenceNotes`
- `referenceSources`
- `exampleFinalPrompt`

## 示例
当前 `render` 输出的是与线上后端同骨架的“单张稳定版”提示词，会按固定顺序拼装：

1. 身份保持骨架
2. 构图
3. 场景
4. 主表情
5. 主体动作
6. 发型细节动作参考
7. 服饰
8. 发型
9. 关键约束
10. 画质约束
11. 负面约束

注意：
- JSON 数据文件里保存的是结构化片段，不是最终成品 prompt。
- 完整提示词的拼装逻辑在 `src/faceprompt/catalog.py`。
- 线上后端也会做“手部冲突检查”，避免同时出现多于两只手这类不合物理逻辑的动作组合。

适合先用 `list` 找到 `scene` 和 `hairstyle` 的 `id`，再用 `render` 输出成品提示词。

当前男女发型分类已按国内理发店高频术语重整，和交互菜单顺序保持一致。
