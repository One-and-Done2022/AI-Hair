面向中文图像模型的人像提示词库项目。当前仓库的核心目标是：

- 以参考人物照片为原型，生成“换发型 + 换场景”的高质量中文提示词
- 严格保留同一人物身份特征，不做换脸或多人生成
- 通过结构化数据管理场景、发型、约束和最终成品提示词

这个 README 主要写给下一个接手的 Agent 或工程师，用于快速建立上下文并继续开发。

## 当前状态

项目已经具备可用的本地能力：

- 20 类场景数据
- 20 类男士发型数据
- 20 类女士发型数据
- 结构化数据加载、校验、交互式选择、成品提示词渲染
- 面向中文模型的统一身份保持规则和负面约束
- 与线上后端对齐的单张稳定版提示词骨架与动作冲突规避逻辑

当前不是 Web 服务，也不是 GUI 应用。它是一个本地 Python 工具项目，主要通过 CLI 和数据文件工作。

## 快速开始

本机默认使用 `python3`。

```bash
make summary
make lint
make test
make interactive
```

也可以直接调用 CLI：

```bash
PYTHONPATH=src python3 -m faceprompt.cli summary
PYTHONPATH=src python3 -m faceprompt.cli list --category scene
PYTHONPATH=src python3 -m faceprompt.cli list --category hairstyle --gender female
PYTHONPATH=src python3 -m faceprompt.cli render --scene indoor-film-lifestyle --hairstyle female-french-lazy-waves
PYTHONPATH=src python3 -m faceprompt.cli interactive
```

## 仓库结构

```text
.
├── src/faceprompt/
│   ├── cli.py
│   ├── catalog.py
│   └── data/
│       ├── scenes.json
│       ├── hairstyles_male.json
│       ├── hairstyles_female.json
│       └── reference_sources.json
├── tests/
│   └── test_catalog.py
├── docs/
│   ├── prompt-library.md
│   └── reference-sources.md
├── assets/reference-thumbnails/
│   └── README.md
├── Makefile
├── pyproject.toml
├── AGENTS.md
└── README.md
```

关键文件说明：

- `src/faceprompt/catalog.py`
  这是核心逻辑文件。统一定义基础身份提示词、负面约束、数据加载、记录过滤、提示词渲染和数据校验。

- `src/faceprompt/cli.py`
  CLI 入口。支持 `summary`、`validate`、`list`、`render`、`interactive`。

- `src/faceprompt/data/scenes.json`
  20 条场景数据。

- `src/faceprompt/data/hairstyles_male.json`
  20 条男士发型数据，顺序与交互菜单顺序一致。

- `src/faceprompt/data/hairstyles_female.json`
  20 条女士发型数据，顺序与交互菜单顺序一致。

- `tests/test_catalog.py`
  当前核心回归测试。改数据、改渲染规则、改交互逻辑时都应同步检查这里。

- `docs/prompt-library.md`
  给人看的中文说明文档，列出分类、命令入口和使用方式。

## 当前生成规则

### 1. 身份保持是最高优先级

统一身份约束定义在 `src/faceprompt/catalog.py` 的 `BASE_IDENTITY_PROMPT`。

当前默认规则包括：

- 严格保留参考人物真实身份特征
- 保证一眼看出是同一个人
- 不改变脸型、五官比例、眼距、鼻梁、嘴型、肤色、年龄感、整体气质
- 不改变性别表达
- 不换脸
- 不生成第二个人
- 忽略原背景、原服饰、原发型和原有动作
- 主体始终是同一位单人肖像

如果后续要继续加强“身份锁定”能力，优先改这里，不要分散写在单个发型或单个场景记录里。

### 2. 负面约束是统一注入的

统一负面约束定义在 `src/faceprompt/catalog.py` 的 `BASE_NEGATIVE_PROMPT`。

当前默认包含：

- 不要换脸
- 不要改变性别表达
- 不要生成第二个人
- 不要多人同框
- 不要双脸
- 不要身份漂移
- 不要背景杂乱
- 不要过强滤镜
- 不要文字水印
- 以及 AI 脸、过度磨皮、假发感、光影冲突、肢体物理逻辑错误等常见错误

如果后续用户继续加“全局禁忌项”，也应该优先改这里。

### 3. 交互菜单顺序依赖数据文件顺序

`list_records()` 当前保留 JSON 文件原始顺序，不再按 `id` 排序。

这意味着：

- `interactive` 菜单展示顺序 == 数据文件中的书写顺序
- 如果你调整 `hairstyles_male.json` 或 `hairstyles_female.json` 的顺序，交互菜单顺序会跟着变

这个行为是有意设计的，因为当前发型列表已经按国内理发店常见分类顺序整理。

## 数据模型

运行时统一暴露 `CatalogRecord`。关键字段：

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

场景和发型的组合由 `render_prompt(scene_id, hairstyle_id)` 生成最终中文提示词。

当前 `render_prompt()` 默认输出的是单张稳定版运行时 prompt，而不是旧版“一次生成 5 张”的草稿式提示词。
如果你只是想看线上后端现在实际接近什么样的完整提示词，优先用：

```bash
cd Faceprompt
PYTHONPATH=src python3 -m faceprompt.cli render --scene morning-window-softlight --hairstyle male-forward-spikes
```

## 扩展方式

### 新增或调整发型

1. 修改 `src/faceprompt/data/hairstyles_male.json` 或 `src/faceprompt/data/hairstyles_female.json`
2. 保持字段完整
3. 如果顺序变动，确认这是你想要的交互菜单顺序
4. 运行 `make lint` 和 `make test`
5. 如果分类文档发生变化，同步更新 `docs/prompt-library.md`

### 新增或调整场景

1. 修改 `src/faceprompt/data/scenes.json`
2. 保持场景里的环境、光线、风格、动作、表情、约束字段完整
3. 运行 `make lint` 和 `make test`
4. 如有必要，同步更新 `docs/prompt-library.md`

### 修改统一生成规则

如果是这些类型的改动，优先改 `src/faceprompt/catalog.py`：

- 身份保持骨架
- 负面约束
- 渲染顺序
- 单张稳定版 prompt 结构
- 主体动作与发型动作的冲突规避逻辑
- CLI 输出格式
- 记录过滤逻辑

## 已知约束和容易踩坑的地方

### 1. 校验数量是写死的

`validate_catalog()` 当前默认要求：

- 20 个场景
- 40 个发型
- 其中男发型 20、女发型 20

如果你要扩库，不仅要改 JSON，还要改 `validate_catalog()` 和对应测试。

### 2. 测试里对提示词骨架有断言

`tests/test_catalog.py` 会检查：

- 数量是否符合预期
- 渲染出的提示词里是否包含身份保持规则
- 是否使用单张稳定版结构
- 是否包含动作冲突约束和物理逻辑约束
- 负面约束里是否包含关键禁忌项
- 交互式命令是否能输出完整结果

所以只改数据不改测试，或者只改测试不改代码，都会很容易不一致。

### 3. 参考图片没有自动入库

项目当前只保存来源索引和文档，不自动下载外部参考图。

相关文件：

- `docs/reference-sources.md`
- `src/faceprompt/data/reference_sources.json`
- `assets/reference-thumbnails/README.md`

如果未来要补“内部缩略图参考”，请按 `assets/reference-thumbnails/README.md` 的规则来，避免直接塞原始高清外部素材。

## 推荐接手流程

下个 Agent 建议按这个顺序理解项目：

1. 先看 `README.md`
2. 再看 `AGENTS.md`
3. 看 `src/faceprompt/catalog.py`
4. 看 `src/faceprompt/cli.py`
5. 看 `docs/prompt-library.md`
6. 最后跑一遍：

```bash
make summary
make lint
make test
make interactive
```

如果这四步都正常，说明你的本地环境和项目状态基本一致。

## 当前适合继续做的方向

一些合理的后续工作方向：

- 为不同模型输出不同风格的提示词模板
- 增加服饰模板库
- 增加可配置的输出张数、画幅比例和镜头风格
- 增加按场景风格线筛选发型的交互入口
- 增加导出 JSON 或 Markdown 的批量生成命令
- 如果未来要做服务化，可以在当前 `catalog.py` 之上包一层 API

## 验证标准

提交前最低限度运行：

```bash
make lint
make test
```

如果改了交互或成品提示词逻辑，建议额外跑：

```bash
make interactive
make render-example
```
<<<<<<< HEAD

>>>>>>> 12b5489 (docs: add project handoff readme)
=======
>>>>>>> 4f01c3c (save local work before submodule migration)
