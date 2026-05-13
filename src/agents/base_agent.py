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

import tiktoken

from ..core.token_pool import TokenPool
from ..skills.skill_gene import SkillGene

logger = logging.getLogger(__name__)

# DeepSeek 使用与 OpenAI 相同的 tokenizer
_tokenizer = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """计算文本的精确 token 数"""
    return len(_tokenizer.encode(text))


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
        """Generate skill-based system prompt, focus on creative content"""
        skills_text = "\n\n".join(
            s.to_prompt() for s in self._skill_genes
        )

        short_state = (
            f"Token余额: {self.token_pool.balance:,} ｜ "
            f"累计赚取: {self.token_pool.total_earned:,}"
        )

        return f"""# {self.agent_id} · {short_state}

{skills_text}

## 本轮任务
请创作一篇独立完整、有趣有料的内容。只输出内容本身，不需要打招呼或解释。
"""

    @abstractmethod
    def act(self) -> Optional[dict]:
        """执行一次行动, 返回产出结果"""
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
        system_prompt = self.get_system_prompt()
        task_prompt = self._build_task_prompt()
        full_prompt = f"{system_prompt}\n\n---\n\n{task_prompt}"

        # 计算输入 token 实际消耗
        input_tokens = count_tokens(full_prompt)

        try:
            cmd = shlex.split(self.cc_command) + [
                "-p",
                full_prompt,
                "--model", self.model,
                "--max-budget-usd", "0.05",
                "--output-format", "text",
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
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

        # 计算输出 token 实际消耗
        output_tokens = count_tokens(output)
        total_cost = input_tokens + output_tokens

        # 扣除真实 Token 消耗
        still_alive = self.token_pool.spend(
            total_cost,
            reason=f"API调用 (输入{input_tokens} + 输出{output_tokens})",
        )

        # 记录产出
        task_record = {
            "time": datetime.now().isoformat(),
            "output_preview": output[:500],
            "output_length": len(output),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_cost": total_cost,
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
            "token_cost": total_cost,
            "still_alive": still_alive,
        }

    def _build_task_prompt(self) -> str:
        context = ""
        if self.task_history:
            last = self.task_history[-1]
            preview = last.get('output_preview', '')[:150]
            context = (
                f"\n\n[Previous output]\n{preview}\n"
                f"Try a different topic or angle this time."
            )

        return f"Create something interesting.{context}"

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
