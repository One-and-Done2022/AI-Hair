# Faceprompt 前端出图参考

这份文档给前端占位图、模板图、示意图使用。目标不是复刻用户上传参考图，而是快速选出合适的场景和发型，生成风格统一的展示图。

## 原始资料位置

- 总说明文档：`Faceprompt/docs/prompt-library.md`
- 场景库：`Faceprompt/src/faceprompt/data/scenes.json`
- 男发库：`Faceprompt/src/faceprompt/data/hairstyles_male.json`
- 女发库：`Faceprompt/src/faceprompt/data/hairstyles_female.json`
- 运行时拼装逻辑：`Faceprompt/src/faceprompt/catalog.py`

如果你需要精确字段，优先看 JSON；如果你需要直接出成品 prompt，优先用 CLI `render`。

## 两种使用方式

### 1. 有参考人脸

直接走 Faceprompt 的标准命令：

```bash
PYTHONPATH=Faceprompt/src python3 -m faceprompt.cli render --scene morning-window-softlight --hairstyle female-french-lazy-waves
```

这个模式会自动带上“身份保持”“单人”“负面约束”等全局规则，适合后端真实生成链路。

### 2. 无参考图，只做前端占位图

这种情况不要直接照搬“保留同一人物身份”的那一段。建议使用下面这套简化模板：

```text
生成 1 张写实风格单人头像写真，3:4 竖构图，胸口以上近景。
场景：<场景环境>
光线：<场景光线>
风格氛围：<场景氛围>
服饰：<场景服饰建议>
人物发型：<发型 promptCore>
要求：真实皮肤质感，脸部清晰对焦，发丝细节清楚，光影过渡自然，画面高级、自然、和谐。
负面约束：不要第二个人，不要多人同框，不要双脸，不要 AI 脸，不要过度磨皮，不要塑料皮肤，不要错位眼睛，不要手指异常，不要耳朵变形，不要发际线异常，不要假发感，不要背景杂乱，不要文字水印，不要不符合物理逻辑的肢体。
```

如果只是填前端图，不建议在同一批图里混用太多风格线。首页和模板列表优先用 `realistic_editorial`，风格专题页再补 `fashion_editorial`。

## 全局规则

- 只出 1 个主体，不要多人，不要拼图，不要多宫格。
- 单张图只保留 1 个主要动作，不要把多个手部动作叠在一起。
- 发型必须是主角，背景只能辅助，不要抢脸和头发。
- 服装只做氛围补充，不要高饱和大图案。
- 前端示意图优先 3:4 竖图、胸口以上近景，兼容小程序卡片。

## 场景目录

### 真实高级写真

- `indoor-film-lifestyle` | 室内生活感胶片写真 | 浅色墙面、木质陈设、自然窗光、生活感近景。
- `morning-window-softlight` | 清晨窗边软光人像 | 清晨窗边、干净留白、软光、松弛感强。
- `walnut-study-portrait` | 胡桃木书房静物人像 | 木质书柜、纸张、暖中性侧光、安静知识感。
- `cafe-candid-seat` | 咖啡馆抓拍座位人像 | 靠窗座位、杯具桌面、轻都市感、自然抓拍。
- `bathroom-mirror-morning` | 浴室镜前晨间人像 | 镜面、瓷砖、晨间洗漱语境、亲密生活化。
- `hotel-room-loose` | 酒店房间松弛感人像 | 浅米色酒店空间、床品软包、旅行感和慵懒感。
- `sunset-home-backlight` | 傍晚家居逆光人像 | 傍晚逆光、暖色边缘光、家庭空间情绪感。
- `hallway-quiet-frame` | 楼道玄关安静框景人像 | 门框构图、低饱和、克制、安静定格。
- `bedside-half-recline` | 床边半卧近景人像 | 半卧姿态、柔光、私密温和、适合中长发。
- `rainy-window-mood` | 雨天窗边情绪人像 | 冷调散射光、玻璃雨痕、极简忧郁氛围。

### 时尚大片

- `studio-solid-backdrop` | 极简纯色棚拍 | 纯色背景、干净布光、最适合展示发型轮廓。
- `cold-metal-space` | 冷调金属空间人像 | 金属墙面、冷白反光、未来感、结构锐利。
- `retro-cinema-box` | 复古电影包厢人像 | 酒红暗木、暖色重点光、复古戏剧感。
- `city-neon-night` | 都市夜色霓虹人像 | 霓虹散景、城市夜景、轮廓感强。
- `gallery-white-cube` | 画廊白盒子空间人像 | 白墙几何空间、极简高定感、清冷。
- `dramatic-side-light` | 戏剧化强侧光人像 | 深色背景、单侧强光、骨相和发型纹理突出。
- `luxury-hotel-lobby` | 高级酒店大堂人像 | 大理石、灯带、明星感、成熟从容。
- `rooftop-wind` | 天台风场人像 | 城市天台、风感发丝、都市大片张力。
- `moody-bar-counter` | 暗调酒吧吧台人像 | 低照度暖光、玻璃反射、成熟夜色氛围。
- `backstage-vanity-mirror` | 后台化妆镜前人像 | 镜灯、化妆台、后台准备时刻、时尚感强。

## 男发目录

- `male-forward-spikes` | 前刺头 | 两侧铲青，顶区短而向前抓刺，利落清爽。
- `male-chestnut-head` | 栗子头 | 极短平直刘海，轮廓圆润，乖巧少年感。
- `male-american-buzz` | 美式圆寸 | 精致渐变，头顶极短，骨相清楚。
- `male-french-short-texture` | 法式短碎发 | 短碎刘海，顶区细碎纹理，高频生活化短发。
- `male-flat-short-cut` | 短平头 | 传统短发，整洁耐看，低维护。
- `male-morgan-fringe` | 摩根碎盖 | 发根支撑，前区轻碎，韩系松弛感。
- `male-tin-foil-perm` | 锡纸烫 | 细密条状卷束，发量感强，街头感明显。
- `male-clip-perm` | 钢夹烫 | 更自然的纹理烫，松散蓬松，适合日常图。
- `male-firework-perm` | 烟花烫 | 极小卷、极蓬松、个性强，适合态度型画面。
- `male-texture-perm` | 纹理烫 | 柔和弯曲纹理，兼容日常写真。
- `male-wool-perm` | 男士羊毛卷 | 细密卷度，复古文艺感强。
- `male-korean-37-part` | 韩系三七分 | 侧分加爱心弧度，柔和精致。
- `male-comma-bangs` | 逗号刘海 | 单侧 C 弯刘海，修饰额头和眉眼距离。
- `male-middle-micro-part` | 中分微分 | 自然中分，两侧垂落，学长感和温润感强。
- `male-vintage-slick-back` | 港风复古背头 | 露额后梳，成熟稳重，复古电影感。
- `male-side-part-pomade` | 侧分油头 | 正式偏分，发面整齐压实，商务感强。
- `male-mullet` | 鲻鱼头 | 前短后长，后区延伸到脖颈，辨识度很高。
- `male-wolf-tail` | 狼尾发型 | 高层次、轻尾感、比鲻鱼头更野更轻。
- `male-japanese-wavy-long` | 日系微卷长发 | 耳下到肩部的松散微卷，带艺术气质。
- `male-samurai-half-bun` | 武士半扎发 | 两侧更短，顶区长发后扎，结构感强。

## 女发目录

- `female-blunt-bob` | 一刀切波波头 | 平齐发尾、清冷利落、高级感强。
- `female-ear-tucked-first-love` | 挂耳初恋短发 | 两侧轻薄挂耳，后脑饱满，青春感强。
- `female-french-undercut-short` | 法式推边短发 | 耳后推短、顶区保留长度，中性帅气。
- `female-boyish-super-short` | 少年感超短发 | 露耳露颈，最大化突出五官骨相。
- `female-japanese-apple-head` | 日系苹果头 | 圆润低层次、轻内扣、甜感减龄。
- `female-collarbone-xinzhilei` | 辛芷蕾锁骨发 | 锁骨长度、脸侧高层次，修脸效果强。
- `female-edge-layer-cut` | 边缘层次剪 | 脸侧和发尾羽毛状打薄，直发更轻。
- `female-high-layer-midlong` | 高层次中长发 | 上蓬下轻，动势强，适合风感大片。
- `female-japanese-feather-cut` | 日系羽毛剪 | 发尾轻薄外扩，柔和耐看。
- `female-fishtail-perm` | 鱼尾烫中长发 | 发尾外翻，俏皮轻法式。
- `female-french-lazy-waves` | 法式慵懒卷 | 大而松散的卷度，浪漫、松弛。
- `female-korean-air-cushion-perm` | 韩式气垫烫 | 发根支撑明显，头包脸，高颅顶。
- `female-wooden-horse-curls` | 木马卷 | 卷度整齐立体，精致丰盈。
- `female-water-wave-mid` | 水波纹 | 连续平缓波浪，知性温柔。
- `female-wool-curls` | 羊毛卷 | 从发根开始的细密卷，复古港风。
- `female-cloud-perm` | 云朵烫 | 轻软微卷，发尾更明显，减龄百搭。
- `female-wheat-curls` | 麦穗卷 | 规则细卷，森系文艺感更强。
- `female-new-chinese-long-straight` | 新中式黑长直 | 乌黑顺滑、垂坠感强、东方清冷。
- `female-modern-hime-cut` | 改良公主切 | 耳前短切和后方长发形成明显断层。
- `female-waterfall-straight` | 瀑布直发 | 超长直发、发量丰沛、视觉冲击力强。

## 前端占位图推荐组合

下面这些组合稳定、容易出片，也适合放进模板卡片和首页瀑布流：

- 清爽男生日常：`morning-window-softlight` + `male-comma-bangs`
- 生活化男生短发：`indoor-film-lifestyle` + `male-french-short-texture`
- 韩系松弛男生：`hotel-room-loose` + `male-korean-37-part`
- 硬朗时装男生：`studio-solid-backdrop` + `male-american-buzz`
- 复古成熟男生：`retro-cinema-box` + `male-vintage-slick-back`
- 个性都市男生：`city-neon-night` + `male-wolf-tail`
- 清爽女生短发：`morning-window-softlight` + `female-ear-tucked-first-love`
- 通用女生爆款：`cafe-candid-seat` + `female-collarbone-xinzhilei`
- 松弛氛围女生：`hotel-room-loose` + `female-french-lazy-waves`
- 温柔卷发女生：`bedside-half-recline` + `female-water-wave-mid`
- 高级冷感女生：`gallery-white-cube` + `female-blunt-bob`
- 新中式女生：`rainy-window-mood` + `female-new-chinese-long-straight`

## 直接出图命令

### 查看全部场景

```bash
PYTHONPATH=Faceprompt/src python3 -m faceprompt.cli list --category scene
```

### 查看全部男发

```bash
PYTHONPATH=Faceprompt/src python3 -m faceprompt.cli list --category hairstyle --gender male
```

### 查看全部女发

```bash
PYTHONPATH=Faceprompt/src python3 -m faceprompt.cli list --category hairstyle --gender female
```

### 渲染完整成品 prompt

```bash
PYTHONPATH=Faceprompt/src python3 -m faceprompt.cli render --scene indoor-film-lifestyle --hairstyle female-collarbone-xinzhilei
PYTHONPATH=Faceprompt/src python3 -m faceprompt.cli render --scene studio-solid-backdrop --hairstyle male-american-buzz
```

## 你现在最该怎么用

- 如果你只是给前端补展示图，先从“前端占位图推荐组合”里选 8 到 12 组。
- 如果你要更精确控制发型细节，再去对应 JSON 里复制 `promptCore`。
- 如果你要走真实产品链路，就直接用 `render` 输出完整 prompt。
