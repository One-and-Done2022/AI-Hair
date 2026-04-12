# 男生前端展示名映射表草案

## 说明

- 这份表是给前端展示层使用的预设映射，不等于底层结构主库本体。
- 用户看到的是 `display_name`。
- 后端实际执行的是 `structure_id + modifier_ids + technique_ids`。
- 前端一级分类使用更贴近用户认知的 5 类：`清爽短发 / 韩系分线 / 轻熟背头 / 个性长发 / 烫卷造型`。
- `structure_id` 优先复用扩展草案里的新结构 ID；少量仍沿用当前后端已存在的旧 ID。
- 卷烫造型属于“工艺驱动预设”，前端可展示，但生成时必须绑定一个默认结构骨架。

## 清爽短发

| display_name | category_key | structure_id | modifier_ids | technique_ids | 备注 |
| --- | --- | --- | --- | --- | --- |
| 美式前刺 | clean_short | male-american_forward_spike | [] | [] | 前刺体系标准款，适合做默认推荐 |
| 立体前刺 | clean_short | male-dimensional_forward_spike | [] | [] | 强调颅顶和立体支撑 |
| 纹理前刺 | clean_short | male-textured_forward_spike | [] | ["male-texture-perm"] | 纹理比基础前刺更强 |
| 凌乱抓刺 | clean_short | male-messy_forward_spike | ["modifier_messy_texture"] | [] | 少年感和街头感更强 |
| 微分前刺 | clean_short | male-micro_part_forward_spike | [] | [] | 前刺里偏修脸路线 |
| 前刺老虎头 | clean_short | male-tiger_head_spike | [] | [] | 顶部更高更圆 |
| 立体碎盖 | korean_soft | male-textured_cover | [] | [] | 碎盖里更强调顶部立体 |
| 微分碎盖 | korean_soft | male-micro_part_cover | [] | [] | 当前最稳的少年感款 |
| 短碎栗子头 | korean_soft | male-chestnut_crop | [] | [] | 低门槛、圆润、减龄 |
| 基础短发 | clean_short | male-textured_short_foundation | [] | [] | 兜底短发预设 |
| 韩式小平头 | clean_short | male-korean_flat_crop | [] | [] | 更韩系的小平头版本 |
| 美式圆寸 | clean_short | male-american-buzz | [] | [] | 继续沿用当前后端 ID |
| 渐变寸头 | clean_short | male-fade-buzz | [] | [] | 继续沿用当前后端 ID |
| 短平头 | clean_short | male-flat-short-cut | [] | [] | 继续沿用当前后端 ID |

## 韩系分线

| display_name | category_key | structure_id | modifier_ids | technique_ids | 备注 |
| --- | --- | --- | --- | --- | --- |
| 韩式三七分 | korean_soft | male-korean_37_part | [] | [] | 分线体系主干款 |
| 括号三七 | korean_soft | male-korean_37_part | ["modifier_bracket_fringe"] | [] | 用三七主结构叠括号前区 |
| 逗号侧分 | korean_soft | male-clean_side_part | ["modifier_comma_fringe"] | [] | 日常好理解的展示词 |
| 偏分三七 | korean_soft | male-clean_37_part | [] | [] | 比韩式三七更干净 |
| 纹理三七分 | korean_soft | male-textured_37_part | [] | [] | 更强调束感和层次 |
| 三七侧分 | korean_soft | male-soft_37_part | [] | [] | 前区更柔和修脸 |
| 基础侧分 | korean_soft | male-clean_side_part | [] | [] | 通勤基础款 |
| 二八侧分 | korean_soft | male-two_eight_part | ["modifier_commute_clean"] | [] | 更成熟、更正式 |
| 长纹理侧分 | korean_soft | male-textured_side_part | ["modifier_side_fringe"] | [] | 轻熟氛围感路线 |
| 微分纹理 | korean_soft | male-micro_middle_part | [] | [] | 中分/微分主干款 |

## 轻熟背头

| display_name | category_key | structure_id | modifier_ids | technique_ids | 备注 |
| --- | --- | --- | --- | --- | --- |
| 纹理背头 | statement_style | male-textured_slick_back | [] | [] | 轻熟硬朗，不做强油头 |
| 三七侧背 | statement_style | male-three_seven_side_back | [] | [] | 修脸和成熟感兼顾 |
| 侧背短发 | statement_style | male-short_side_back | [] | [] | 造型感入门款 |
| 长纹理侧背 | statement_style | male-long_textured_side_back | [] | [] | 顶区和前区更长 |
| 蓬松侧背 | statement_style | male-fluffy_side_back | [] | [] | 空气感更强 |
| 四六分侧背 | statement_style | male-six_four_side_back | [] | [] | 偏成熟偏正式 |
| 复古油头 | statement_style | male-vintage_pomade | [] | [] | 已经是成型结构预设 |
| 湿发侧背 | statement_style | male-wet_side_back | [] | [] | 直接用独立结构预设 |
| 龙须背头 | statement_style | male-dragon_whisker_back | [] | [] | 前区保留龙须落发 |
| 长刘海侧背 | statement_style | male-long_fringe_side_back | ["modifier_long_fringe"] | [] | 长前区修饰更明显 |

## 个性长发

| display_name | category_key | structure_id | modifier_ids | technique_ids | 备注 |
| --- | --- | --- | --- | --- | --- |
| 港风分线 | statement_style | male-hongkong_parted_style | ["modifier_hk_vibe"] | [] | 港风建议走风格修饰 |
| 港风纹理 | statement_style | male-hongkong_texture | ["modifier_hk_vibe", "modifier_messy_texture"] | [] | 更松弛、更复古 |
| 港风中长发 | statement_style | male-hongkong_medium_long | ["modifier_hk_vibe"] | [] | 中长发港风主展示词 |
| 鲻鱼头 | statement_style | male-mullet | [] | [] | 继续沿用当前后端 ID |
| 狼尾发型 | statement_style | male-wolf-tail | [] | [] | 继续沿用当前后端 ID |
| 日系微卷长发 | statement_style | male-japanese-wavy-long | [] | [] | 继续沿用当前后端 ID |
| 武士半扎发 | statement_style | male-samurai-half-bun | [] | [] | 继续沿用当前后端 ID |

## 烫卷造型

| display_name | category_key | structure_id | modifier_ids | technique_ids | 备注 |
| --- | --- | --- | --- | --- | --- |
| 自然纹理烫 | textured_perm | male-textured_side_part | [] | ["male-texture-perm"] | 工艺驱动预设，默认挂长纹理侧分骨架 |
| 气垫纹理烫 | textured_perm | male-micro_middle_part | [] | ["male-air-cushion-perm"] | 默认挂微分纹理骨架 |
| 定位蓬松烫 | textured_perm | male-textured_short_foundation | [] | ["male-root-lift-perm"] | 适合作为短发蓬松工艺入口 |
| 钢夹前刺烫 | textured_perm | male-textured_forward_spike | [] | ["male-clip-perm"] | 明确绑定前刺骨架 |
| 韩式羊毛卷 | textured_perm | male-middle-micro-part | [] | ["male-wool-perm"] | 当前先沿用旧结构骨架 |
| 法式慵懒卷 | textured_perm | male-textured_side_part | [] | ["male-french-lazy-perm"] | 默认走轻熟长纹理侧分 |
| 锡纸束感卷 | textured_perm | male-textured_short_foundation | [] | ["male-tin-foil-perm"] | 默认挂基础短发骨架 |

## 建议

- 第一版前端主界面不要一次性全放出，优先上线 24 到 30 个高频展示名。
- 卷烫造型建议单独做一个二级入口，不要和结构发型完全混排。
- 如果后续正式拆库，建议把这张映射表落为 `hairstyle_presets_male.json`。
