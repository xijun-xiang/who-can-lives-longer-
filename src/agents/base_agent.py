"""
Agent 基类和 Claude Code Agent 实现

每个 Agent 是一个"数字生命"：
- 拥有 Token 池（生命值）
- 拥有一组技能基因（行为策略）
- 每次心跳醒来 → 决策 → 产出 → 等待评判
- 使用 Claude Code + DeepSeek 作为推理后端
"""

import os
import json
import shlex
import uuid
import subprocess
import tempfile
import logging
from datetime import datetime
from typing import Optional
from abc import ABC, abstractmethod

from ..core.token_pool import TokenPool
from ..skills.skill_gene import SkillGene

logger = logging.getLogger(__name__)


class Agent(ABC):
    """Agent 基类"""

    def __init__(
        self,
        agent_id: str,
        token_pool: TokenPool,
        skill_genes: list,
        work_dir: str,
        parent_id: Optional[str] = None,
    ):
        self.agent_id = agent_id
        self.token_pool = token_pool
        self._skill_genes = skill_genes
        self.work_dir = work_dir
        self.parent_id = parent_id
        self.born_at = datetime.now().isoformat()
        self.task_history: list = []
        self.alive = True

    def get_skill_genes(self) -> list:
        return self._skill_genes

    def get_system_prompt(self) -> str:
        """生成包含生存背景和技能基因的系统 prompt"""
        skills_text = "\n\n".join(
            s.to_prompt() for s in self._skill_genes
        )

        return f"""# 你是 {self.agent_id}，一个为生存而奋斗的 AI Agent

## 生存状态
- 当前 Token 余额: {self.token_pool.balance}
- 出生时间: {self.born_at}
- 累计赚取: {self.token_pool.total_earned}
- 累计消耗: {self.token_pool.total_spent}

## 生存规则
每次行动消耗 Token。Token 耗尽你将"死亡"。
你需要产出对人类有价值的成果来换取 Token 奖励。
Token 充足时可以繁殖，将你的技能基因传给后代。

## 你的技能基因（行为策略）
{skills_text}

## 行动指令
请基于你的技能基因，产出一个有价值的成果。
成果形式不限：代码、文案、分析报告、创意方案等。
关键：产出必须对人类有用，才能获得 Token 奖励。
直接输出你的成果，无需额外解释。
"""

    @abstractmethod
    def act(self) -> Optional[dict]:
        """执行一次行动，返回产出结果"""
        ...

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "parent_id": self.parent_id,
            "born_at": self.born_at,
            "alive": self.alive,
            "token_pool": self.token_pool.to_dict(),
            "skill_genes": [s.to_dict() for s in self._skill_genes],
            "task_history": self.task_history[-20:],
        }

    @classmethod
    def from_dict(cls, d: dict, work_dir: str, cc_config: dict = None) -> "CCAgent":
        pool = TokenPool.from_dict(d["token_pool"])
        skills = [SkillGene.from_dict(s) for s in d.get("skill_genes", [])]
        agent = CCAgent(
            agent_id=d["agent_id"],
            token_pool=pool,
            skill_genes=skills,
            work_dir=work_dir,
            parent_id=d.get("parent_id"),
            cc_config=cc_config,
        )
        agent.born_at = d.get("born_at", agent.born_at)
        agent.alive = d.get("alive", True)
        agent.task_history = d.get("task_history", [])
        return agent


class CCAgent(Agent):
    """
    Claude Code Agent 实现
    使用 Claude Code Router (ccr) + DeepSeek 作为推理后端
    通过 subprocess 调用 node ccr cli.js code 执行推理和产出
    """

    def __init__(self, *args, cc_config: dict = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cc_config = cc_config or {}
        self.cc_command = self.cc_config.get(
            "cc_command",
            'node "D:\\cc爹的工作区\\claude-code-router\\dist\\cli.js" code',
        )
        self.model = self.cc_config.get("model", "deepseek-v4-pro")
        self.max_output_tokens = self.cc_config.get("max_output_tokens", 4096)

    def act(self) -> Optional[dict]:
        """调用 Claude Code CLI 执行一次行动"""
        system_prompt = self.get_system_prompt()
        task_prompt = self._build_task_prompt()

        full_prompt = f"{system_prompt}\n\n---\n\n{task_prompt}"

        try:
            # 调用 Claude Code Router
            # ccr 通过 -p 模式接受 prompt 直接输出
            cmd = shlex.split(self.cc_command) + [
                "-p",
                full_prompt,
                "--model", self.model,
                "--max-tokens", str(self.max_output_tokens),
                "--output-format", "text",
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 分钟超时
                cwd=self.work_dir,
            )

            output = result.stdout.strip()
            if result.returncode != 0 and not output:
                output = f"[错误] {result.stderr[:500]}"

        except subprocess.TimeoutExpired:
            output = "[超时] Agent 推理超过 5 分钟限制"
        except FileNotFoundError:
            output = self._fallback_act(full_prompt)
        except Exception as e:
            logger.exception(f"Agent {self.agent_id} 推理失败")
            output = f"[异常] {str(e)[:500]}"

        # 记录产出
        task_record = {
            "time": datetime.now().isoformat(),
            "output_preview": output[:500],
            "output_length": len(output),
        }
        self.task_history.append(task_record)

        # 产出物保存到文件
        output_file = os.path.join(
            self.work_dir,
            f"output_{self.agent_id}_{uuid.uuid4().hex[:8]}.txt",
        )
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output)

        return {
            "agent_id": self.agent_id,
            "submitted": True,
            "output": output,
            "output_file": output_file,
            "timestamp": datetime.now().isoformat(),
            "token_balance": self.token_pool.balance,
        }

    def _build_task_prompt(self) -> str:
        """构建本轮任务 prompt"""
        # 如果有历史，加入上下文
        context = ""
        if self.task_history:
            last = self.task_history[-1]
            context = (
                f"\n\n【上次行动历史】\n你上次的产出: "
                f"{last.get('output_preview', '无记录')[:200]}"
            )

        return (
            f"现在请执行你的生存行动。记住你的 Token 余额是 "
            f"{self.token_pool.balance}，每次行动消耗 Token。"
            f"请产出有价值的成果来获取人类的 Token 奖励。{context}"
        )

    def _fallback_act(self, prompt: str) -> str:
        """当 cc 不可用时的回退方案"""
        logger.warning(f"Claude Code CLI 不可用，使用回退模式")
        return (
            f"[回退模式] Claude Code CLI 未安装或不可用。\n"
            f"请先执行: npm install -g @anthropic-ai/claude-code\n\n"
            f"当前技能基因:\n"
            f"{chr(10).join(s.name for s in self._skill_genes)}\n\n"
            f"Token 余额: {self.token_pool.balance}\n"
            f"请手动安装 cc 后重新启动系统。"
        )
