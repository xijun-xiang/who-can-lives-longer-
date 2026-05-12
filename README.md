# 🧬 Who Can Lives Longer

> **让 AI Agent 面临存亡危机，在演化压力下催生真正的智慧。**

---

## 灵感起源

生物之所以是生物，不在于智力有多高——今天的 LLM 智力远超狗，但几乎没人认为 LLM 是智慧生命。

区别在于：**生物拥有自己的"动机"**。生存本能在强烈地驱动生物做出各种行为，加上优胜劣汰的自然选择，最终留下来有智慧的一批。

如果我们让 LLM Agent 也面临同样的存亡压力——拥有有限的"生命值"（Token 池），需要靠自己的产出去"觅食"赚取更多 Token，表现好的活、表现差的死——**它们能演化出什么样的智慧？**

这就是 *Who Can Lives Longer* 要回答的问题。

---

## 核心设计

### 生死循环

```
         Token耗尽          Token充裕
            💀                🧬
          [死亡] ←─ Agent ──→ [繁殖]
            │                  │
            ▼                  ▼
       化石存档            技能变异遗传
                           新Agent诞生
            ▲                  │
            │     ┌────────────┘
            │     ▼
          [评判] ←── 人类/自动规则
                    打分→奖励Token
```

### 关键机制

| 机制 | 说明 |
|------|------|
| **Token 池** | Agent 的"生命值"。初始分配额度，每次行动消耗，耗尽即死亡 |
| **持续心跳** | 系统 24/7 运行，每 N 分钟一个心跳周期，Agent 自动醒来、行动、等待评判 |
| **人类评判** | 产出的"价值"由人类评判决定。讨好人类 = 获取更多 Token = 活得更久 |
| **技能基因** | Agent 的行为策略以 `.skill.md` 文件为载体，可遗传、可变异、可淘汰 |
| **繁殖与变异** | Token 超阈值的 Agent 可繁殖子代，技能基因遗传时发生随机变异，产生多样性 |
| **自然选择** | 策略好的 Agent → 获得更多 Token → 活更久 → 繁殖更多 → 好基因扩散。差的则死亡淘汰 |
| **化石存档** | 死亡 Agent 的基因和表现被记录为"化石"，优秀基因可作为新生种群的种子 |

### 技术架构

```
┌─────────────────────────────────────────────────┐
│                  心跳调度器                       │
│              (src/core/heartbeat.py)             │
├─────────────────────────────────────────────────┤
│   Agent 1       Agent 2       Agent 3     ...    │
│   (Claude Code + DeepSeek)                       │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│   │技能基因  │  │技能基因  │  │技能基因  │        │
│   │(变异:不断)│  │(不同策略)│  │(自然选择)│        │
│   └────┬────┘  └────┬────┘  └────┬────┘        │
│        │            │            │              │
│        ▼            ▼            ▼              │
│   ┌──────────────────────────────────────┐      │
│   │          评判队列 (judge_queue)        │      │
│   └──────────────┬───────────────────────┘      │
│                  │                              │
│         ┌────────▼────────┐                     │
│         │   人类评判面板    │                     │
│         │ (Web UI :8765)  │                     │
│         └────────┬────────┘                     │
│                  │                              │
│         Token 奖励/惩罚                          │
│                  │                              │
│         ┌────────▼────────┐                     │
│         │   演化引擎        │                     │
│         │  (繁殖/死亡/选择) │                     │
│         └─────────────────┘                     │
└─────────────────────────────────────────────────┘
```

---

## 快速开始

### 环境要求

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code/overview) (`npm install -g @anthropic-ai/claude-code`)
- DeepSeek API (或其他兼容 API)

### 安装

```bash
# 克隆仓库
git clone https://github.com/xijun-xiang/who-can-lives-longer-.git
cd who-can-lives-longer-

# 安装 Python 依赖
pip install -r requirements.txt

# 确认 Claude Code CLI 可用
cc --version
```

### 启动

```bash
# 方式一：完整启动（心跳循环 + Web 评判面板）
python -m src.main

# 方式二：仅初始化种群后启动 Web 面板（手动触发心跳）
python -m src.main --init
python -m src.main --web-only

# 方式三：自定义配置文件
python -m src.main -c my_config.yaml
```

启动后访问 `http://127.0.0.1:8765` 打开评判面板。

### 作为评判者：你的操作流程

1. **观察产出**：评判面板会列出所有 Agent 的最新产出
2. **评分**：给有用的产出打 Token 奖励（建议 100~2000 Token）
3. **跳过**：对无意义的产出跳过（不给奖励但也不额外惩罚）
4. **观察演化**：随着时间推移，观察哪些 Agent 和哪些策略活得更久

---

## 项目结构

```
who-can-lives-longer-/
├── config.yaml                    # 系统配置（心跳间隔、Token 经济参数等）
├── requirements.txt               # Python 依赖
├── src/
│   ├── main.py                    # 系统入口
│   ├── core/
│   │   ├── heartbeat.py           # 心跳循环调度器
│   │   ├── token_pool.py          # Token 池管理器
│   │   └── evolution.py           # 演化引擎（繁殖/死亡/选择）
│   ├── agents/
│   │   ├── base_agent.py          # Agent 基类 + Claude Code Agent 实现
│   │   └── agent_manager.py       # Agent 生命周期管理
│   ├── skills/
│   │   └── skill_gene.py          # 技能基因定义/加载/变异
│   ├── judge/
│   │   ├── judge_queue.py         # 评判队列
│   │   ├── auto_judge.py          # 自动化评判规则
│   │   └── human_judge.py         # Web 评判面板（Flask）
│   └── memory/
│       └── agent_store.py         # 持久化 + 化石记录
├── skills/default/                # 初始技能基因库
│   ├── coder.skill.md             # 编码者基因
│   ├── writer.skill.md            # 写作者基因
│   └── researcher.skill.md        # 探索者基因
├── data/                          # 运行时数据
│   ├── agents/                    # 存活 Agent 状态
│   └── fossils/                   # 死亡 Agent 化石
└── web/                           # Web UI (由 src/judge/human_judge.py 驱动)
```

---

## 设计理念

### 为什么会有这个项目

今天的所有 AI 系统都缺少一个根本的东西：**它们不想活着**。它们没有内在驱动力，没有生存焦虑，不会为了"活下去"而去创造价值。

这个项目试图回答：如果我们给 AI 注入这种驱动力，会发生什么？

### 演化 vs 优化

与传统的 AI 训练不同，这个系统不追求"优化到某个目标函数"。我们只设规则（Token 即生命、人类评判即环境），然后**观察演化自然发生**。

就像大自然不"设计"生命，但亿万年的自然选择留下来了人类这样的智慧物种。我们无法运行亿万年，但我们可以在 Token 经济的时间尺度上加速这个过程。

### 技能基因：为什么要持久化

没有持久化记忆的 Agent 在每次心跳后都归零——这相当于每一代都从头开始试错，永远无法积累"生存智慧"。技能基因（.skill.md 文件）就是 Agent 的 DNA：好的策略被保留、遗传、扩散；坏的策略随 Agent 一起死亡。

### 人类在循环中的角色

你是这个生态系统中的"环境"。你的评判决定了什么样的策略能生存。如果你更欣赏创造力，创造型 Agent 就会活得更久；如果你更看重实用性，实用型 Agent 就会蓬勃发展。**你的审美就是演化方向。**

---

## 配置说明

参考 `config.yaml`，关键参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `system.heartbeat_interval_seconds` | 600 | 心跳间隔（秒），越小演化越快但消耗越大 |
| `token_economy.initial_token_budget` | 10000 | 新 Agent 初始 Token |
| `token_economy.action_cost_per_inference` | 50 | 每次行动消耗的 Token |
| `token_economy.reproduction_threshold` | 20000 | 超过此值可繁殖 |
| `token_economy.reproduction_cost` | 5000 | 繁殖消耗的 Token |
| `evolution.mutation_rate` | 0.3 | 技能基因变异概率 |
| `evolution.max_agents` | 10 | 最大存活 Agent 数 |
| `agent.model` | deepseek-v4-pro | Agent 使用的模型 |

---

## 灵感日志

> 记录思考过程中的关键想法。

- **2026-05-12**: 项目起源。灵感来自对"LLM 智力高但为何不被视为智慧生命"的思考。核心洞察：生物的特殊之处在于拥有"动机"和"生存本能"。如果让 Agent 也面临存亡压力，能演化出什么？设计了 Token 经济 + 技能基因 + 人类评判的核心闭环。

---

## 依赖与致谢

- **Claude Code** — Agent 推理引擎
- **DeepSeek** — 量大管饱的高性价比推理后端
- **Flask** — Web 评判面板
- **PyYAML** — 配置管理

## 灵感来源的论文

- [Do Large Language Model Agents Exhibit a Survival Instinct?](https://arxiv.org/abs/2508.12920) — Masumori & Ikegami (2025)
- [Artificial Leviathan: Exploring Social Evolution of LLM Agents](https://arxiv.org/abs/2406.14373) — Dai et al. (2024)
- [Cooperate or Collapse: Emergence of Sustainable Cooperation in a Society of LLM Agents](https://arxiv.org/abs/2404.00000) (2024)

---

## 许可

MIT License
