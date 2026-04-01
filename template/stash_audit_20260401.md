# Git Stash 审计报告

更新时间：2026-04-01

## 1. 目标

这份报告用于确认 `/home/lcy/AIFace` 最近是否发生过 `stash`，以及该 `stash` 具体收纳了哪些文件。

## 2. 结果概览

已确认当前仓库存在 1 条最近的 `stash`：

- `stash@{Tue Mar 31 20:39:29 2026}`
- 描述：`On feature/creation-flow-redesign: temp-before-switch-to-main-20260331`

这是一次在 `feature/creation-flow-redesign` 分支上执行的临时暂存。

## 3. 与分支切换相关的关键时间线

按时间顺序，最近的关键记录如下：

1. `2026-03-31 20:18:46 +0800`
   `feature/creation-flow-redesign` 提交：
   `6e3e7c5 Route all scene generation to Seedream 4.5`
2. `2026-03-31 20:32:46 +0800`
   `main` 合并 feature：
   `953a402 Merge branch 'feature/creation-flow-redesign'`
3. `2026-03-31 20:39:29 +0800`
   创建 `stash`
4. `2026-03-31 20:39:44 +0800`
   从 `feature/creation-flow-redesign` 切到 `main`
5. `2026-03-31 20:39:54 +0800`
   执行 `reset: moving to origin/main`

## 4. 这笔 stash 的规模

`stash@{0}` 共包含大量改动和未跟踪文件。

按顶层目录统计：

- `template`：112 个文件
- `front-sugestion`：82 个文件
- `assets`：6 个文件
- `Faceprompt`：6 个文件
- `miniapp`：2 个文件
- `backend`：2 个文件
- `scripts`：1 个文件
- `docs`：1 个文件

结论：

- 你感觉“文件少了很多”是合理的
- 最明显被收进去的是 `template/` 和 `front-sugestion/`
- 这两个目录正好属于“视觉素材、文档、展示稿、前端原型”最容易让人产生“怎么突然没了”的区域

## 5. 二级目录重点分布

按二级目录统计，文件最多的是：

- `front-sugestion/src`：67
- `template/hairstyles`：40
- `template/scenes`：20
- `template/extras`：14
- `template/social_refs`：12
- `front-sugestion/stitch_ui_ux`：8
- `miniapp/pages`：2
- `backend/app`：2
- `Faceprompt/src`：2

## 6. 最可能让你觉得“少了”的内容

### 6.1 `template/` 整批内容

这笔 `stash` 里包含整批 `template/` 文件，例如：

- `template/backend_current_hairstyle_catalog.md`
- `template/domestic_hairstyle_grouped_catalog.md`
- `template/domestic_hairstyle_taxonomy_checklist.md`
- `template/hairstyle_expansion_draft.json`
- `template/hairstyle_expansion_draft_handoff.md`
- `template/hairstyle_system_refactor_draft.md`
- `template/hairstyles_male_merge_ready.json`
- `template/hairstyles_female_merge_ready.json`
- `template/hairstyles_merge_ready_handoff.md`
- `template/merged_hairstyle_catalog_with_legacy.md`
- `template/scene_styling_refactor_plan.md`
- `template/source.txt`
- `template/www.douyin.com.har`
- `template/www.douyin2.com.har`
- `template/www.douyin2_salvaged.har`

还包含大量图片目录：

- `template/hairstyles/...`
- `template/scenes/...`
- `template/extras/...`
- `template/social_refs/...`

如果你现在看到 `template/` 目录明显空了，这就是直接原因。

### 6.2 `front-sugestion/` 整个原型前端

这笔 `stash` 里新增了完整的 `front-sugestion/` 目录，包括：

- `front-sugestion/index.html`
- `front-sugestion/package.json`
- `front-sugestion/src/app/...`
- `front-sugestion/src/assets/...`
- `front-sugestion/src/styles/...`
- `front-sugestion/stitch_ui_ux/...`

如果你之前记得项目里有一整套前端建议稿、原型代码、Stitch UI 参考，而现在不见了，这也是因为它们被 `stash` 了。

### 6.3 其它被收起来的关键内容

- `docs/faceprompt_frontend_image_guide.md`
- `assets/female1.jpg`
- `assets/female2.jpg`
- `assets/female3.jpg`
- `assets/male1.jpg`
- `assets/male2.jpg`
- `assets/male3.jpg`
- `scripts/review_scene_pipeline.py`

以及部分代码修改：

- `backend/app/data/faceprompt/scenes.json`
- `backend/app/routers/scene_understanding.py`
- `miniapp/pages/scene-tool/index.js`
- `miniapp/pages/scene-tool/index.wxml`
- `Faceprompt/src/faceprompt/cli.py`

## 7. 对“文件为什么变少”的判断

目前最合理的解释不是“主分支丢历史了”，而是：

1. 你在 `feature/creation-flow-redesign` 上有一批未提交或未跟踪内容
2. 这些内容在 `2026-03-31 20:39:29` 被 `stash`
3. 之后切回 `main`
4. 然后把 `main` 重置到了 `origin/main`

因此：

- 已提交到 `main` 或 `feature` 的 commit 仍在
- 但那批未提交文件和未跟踪文件被临时藏进了 `stash`
- 视觉上就会像“目录突然少了很多”

## 8. 当前最重要的判断

就这次审计结果看：

- 不是分支记录消失
- 不是远端 main 被回滚
- 也不是 feature 分支丢了

更像是：

- 一大批本地工作成果被 `stash` 了，尤其是 `template/` 和 `front-sugestion/`

## 9. 后续建议

当前工作区本身还有未提交修改，因此不建议直接在 `main` 上执行 `git stash pop`。

更稳妥的做法是：

1. 新建一个临时恢复分支
2. 在那个分支上应用这笔 `stash`
3. 先检查目录是否就是你要找回的那批文件
4. 确认后再决定如何拣回到 `main`

如果需要，下一步可以继续做：

- 生成 `stash@{0}` 的完整文件清单文本版
- 或者安全创建一个恢复分支来查看这批文件
