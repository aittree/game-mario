<h1 align="center">超级树里奥</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0.0-52c41a?style=flat-square" alt="Version"/>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/pygame-2.5%2B-2E7D32?style=flat-square" alt="pygame"/>
  <img src="https://img.shields.io/badge/PyInstaller-6.x-FFB300?style=flat-square" alt="PyInstaller"/>
  <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D4?style=flat-square&logo=windows&logoColor=white" alt="Windows"/><br/>
</p>

<p align="center">一个基于 <b>Python 3 + pygame</b> 的横版闯关桌面游戏：踩敌人、顶砖块、吃道具、跑到关底旗杆</p>

---

## 一、项目速览

| 项目 | 说明 |
| --- | --- |
| 中文名 | 超级树里奥 |
| 英文名 | Super Treeio |
| 运行形态 | Windows 桌面窗口程序（Python 脚本 ／ exe 可执行文件） |
| 技术栈 | Python 3.12（conda `game` 环境）/ pygame 2.5+ / PyInstaller 6.x |
| 画面 | 1280×720 逻辑画布，瓦片 40 px，视口 32×18 格 |
| 核心玩法 | 横版卷轴 4 关：加速跑 / 可变跳跃 / 踩敌 / 顶砖 / 三种能力状态 / 火球 / 检查点 / 限时 |
| 物理 | AABB + 瓦片逐格扫描，固定 120 Hz 子步（与刷新率无关） |
| 关卡 | 纯文本 JSON（18 行 × 160～200 列），4 关递进解锁 |
| 代码规模 | 规划约 2600 行（含注释与测试） |
| 当前状态 | **开发文档集已完成；源码、素材与 exe 待开发** |

## 二、文档索引

建议按序号阅读；只想快速了解玩法与操作，看第 1、7 两篇即可。

| 序号 | 文档 | 内容 | 主要读者 |
| --- | --- | --- | --- |
| 01 | [需求规格说明书](docs/01-需求规格说明书.md) | 18 项功能需求、非功能需求、界面需求、验收标准、需求边界 | 产品／讲师／开发 |
| 02 | [概要设计说明书](docs/02-概要设计说明书.md) | 四层架构、模块划分、运行时模型、数据流、关键决策、容错 | 开发 |
| 03 | [详细设计说明书](docs/03-详细设计说明书.md) | 常量、关卡 JSON、瓦片碰撞解算、玩家状态机、敌人/道具、相机、会话、渲染、主循环 | 开发 |
| 04 | [开发规范与环境搭建](docs/04-开发规范与环境搭建.md) | 环境准备、依赖、命名与依赖约束、调试快捷键、开发节奏、排错 | 开发 |
| 05 | [测试计划与用例](docs/05-测试计划与用例.md) | 单元用例 61 条、界面用例 42 条、性能、打包冒烟、关卡校验 | 开发／测试 |
| 06 | [打包发布指南](docs/06-打包发布指南.md) | PyInstaller 全流程、关卡/音频收集、体积与误报排查、发布清单 | 开发／发布 |
| 07 | [用户操作手册](docs/07-用户操作手册.md) | 安装、操作、状态与计分、敌人打法、通关技巧、常见问题 | 最终用户 |
| 08 | [素材清单与制作说明](docs/08-素材清单与制作说明.md) | 瓦片集/精灵表索引、背景与音频规格、关卡资产、生成脚本、换皮与合规 | 美术／开发／发布 |

## 三、工程目录结构（规划）

```
超级树里奥/
├── main.py                 # 入口：初始化、界面状态机、主循环
├── requirements.txt
├── pytest.ini
├── supertreeio.spec        # PyInstaller 打包配置
├── version_info.txt        # exe 版本信息
├── src/
│   ├── config.py           # 尺寸、物理与手感参数、配色、图块码、计分表
│   ├── resource.py         # 资源路径解析（兼容 exe）
│   ├── storage.py          # 存档：最高分/金币/解锁/最佳用时/设置
│   ├── audio.py            # 4 首 BGM + 14 个音效、音量、无声卡降级
│   ├── keymap.py           # 按键 → 输入意图（含按下沿）
│   ├── physics.py          # AABB 与瓦片碰撞解算
│   ├── tilemap.py          # 关卡解析、图块查询与修改
│   ├── camera.py           # 死区跟随、视差、坐标映射
│   ├── game.py             # 一关的会话：实体、计分、生死、通关
│   ├── entities/
│   │   ├── base.py         # Body / Entity / PowerState / AnimState
│   │   ├── player.py       # 移动、跳跃、踩踏、受伤、变形、火球
│   │   ├── enemies.py      # 巡逻菇、甲壳虫（壳）、飞行蝠、水管花
│   │   ├── items.py        # 变大菇、火花、火球
│   │   └── props.py        # 移动平台、检查点、终点旗杆
│   └── ui/
│       ├── theme.py        # 配色、字号、HUD 布局
│       ├── anim.py         # 动画定义与帧索引
│       ├── renderer.py     # 世界 / HUD / 菜单 / 选关 / 设置 / 结算
│       ├── effects.py      # 碎片、粒子、飘字、顶砖偏移
│       └── display.py      # 窗口/全屏与坐标映射
├── assets/
│   ├── icon.ico / icon.png
│   ├── fonts/msyh.ttc
│   ├── images/             # 4 套瓦片集、4 套背景 ×2 层、精灵表、Logo
│   ├── levels/             # w1-1 ～ w1-4.json
│   └── audio/              # 4 BGM + 14 SFX（WAV）
├── tools/                  # gen_tiles / gen_sprites / gen_backgrounds / gen_audio / gen_levels / format_level
├── tests/                  # test_physics / tilemap / player / game / storage
└── docs/                   # 本文档集
```

## 四、快速开始（开发时）

```bash
# 1. 安装依赖（conda game 环境，Python 3.12）
python -m pip install -r requirements.txt

# 2. 运行
python main.py

# 3. 跑单元测试（可选）
pytest -q

# 4. 重新生成素材（可选，需 pillow / numpy）
python tools/gen_tiles.py
python tools/gen_sprites.py
python tools/gen_backgrounds.py
python tools/gen_audio.py
python tools/gen_levels.py

# 5. 校验关卡 JSON
python tools/format_level.py

# 6. 打包成单文件 exe
pyinstaller supertreeio.spec --clean --noconfirm
# 产物：dist/超级树里奥.exe
```

## 五、操作方式

| 按键 | 作用 |
| --- | --- |
| ← → / A D | 左右移动（有加速度与摩擦，非瞬移） |
| ↑ / W / 空格 | 跳跃（按住跳约 4 格，轻按约 2 格；离地 110 ms 内仍可起跳） |
| Shift | 冲刺（上限 460 px/s） |
| ↓ / S | 下蹲（大体型可下穿单向平台） |
| X / F | 发射火球（仅 FIRE 状态，同屏最多 2 颗） |
| P / ESC | 暂停 / 继续 |
| F11 | 窗口 / 全屏 |
| Enter | 菜单与结算确认 |

## 六、关卡与内容

| 关卡 | 主题 | 特点 | 列数 |
| --- | --- | --- | --- |
| 1-1 | 草原 | 教学：砖块、问号块、巡逻菇、水管、检查点 | 200 |
| 1-2 | 地下 | 偏暗、尖刺与窄平台、甲壳虫密集 | 170 |
| 1-3 | 空中 | 单向平台、移动平台、飞行蝠 | 180 |
| 1-4 | 城堡 | 水管花、密集尖刺、长距离跳跃 | 190 |

## 七、素材一览

| 类型 | 内容 | 规格 |
| --- | --- | --- |
| 瓦片集 | `tiles_grass/cave/sky/castle.png` | 320×80（16 帧 × 40 px，索引固定） |
| 精灵表 | 角色（小/大）、敌人、道具 | 48×48 / 48×72 网格，见 08 §2 |
| 背景 | 每主题远/近两层 + 主菜单背景 | 1400×720（近景透明底） |
| 图标 | `icon.png`、`icon.ico` | 256×256 PNG + 七尺寸 ICO |
| 字体 | `msyh.ttc` | 随包中文，避免方块字 |
| 音乐 | `bgm_grass/cave/sky/castle.wav` | 24～30 s 原创芯片音乐，可循环 |
| 音效 | `sfx_*.wav` × 14 | 跳跃/金币/踩敌/顶砖/破砖/变大/变小/火球/死亡/通关/检查点/1UP/菜单/暂停 |
| 关卡 | `w1-1 ～ w1-4.json` | 18 行、160～200 列，纯文本可 diff |

素材全部由 `tools/` 下的脚本生成，规格、索引、触发时机与替换规则见 [08-素材清单与制作说明](docs/08-素材清单与制作说明.md)。

## 八、说明

- 本仓库当前只包含开发文档；源码、素材与 exe 按 04 文档的开发节奏推进。
- 玩法借鉴平台跳跃类型的通用规则，美术、音频、关卡与名称（中文名「超级树里奥」／英文名 `Super Treeio`）均为原创，不含第三方官方素材；商标与合规说明见 01 §8 与 08 §7。
