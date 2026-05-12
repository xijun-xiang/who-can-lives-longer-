"""
Agent 管理器 —— Agent 生命周期管理
- 创建新 Agent
- 加载/保存 Agent 状态
- 标记死亡
- 列出存活/所有 Agent
"""

import os
import json
import uuid
import logging
from typing import Optional

from .base_agent import CCAgent
from ..core.token_pool import TokenPool
from ..skills.skill_gene import SkillGene, load_default_skills

logger = logging.getLogger(__name__)


class AgentManager:
    def __init__(self, config: dict):
        self.config = config
        self.agents_dir = os.path.join(config["system"]["data_dir"], "agents")
        self.work_dir = config["agent"]["work_dir"]
        self.cc_config = {
            "cc_command": config["agent"]["cc_command"],
            "model": config["agent"]["model"],
            "max_output_tokens": config["agent"]["max_output_tokens"],
        }
        self._agents: dict[str, CCAgent] = {}
        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(self.agents_dir, exist_ok=True)
        os.makedirs(self.work_dir, exist_ok=True)

    def create_agent(
        self,
        agent_id: str = None,
        initial_tokens: int = None,
        skill_genes: list = None,
        parent_id: str = None,
    ) -> CCAgent:
        """创建新 Agent"""
        agent_id = agent_id or f"agent_{uuid.uuid4().hex[:8]}"
        initial_tokens = (
            initial_tokens
            or self.config["token_economy"]["initial_token_budget"]
        )

        # 如果没有指定技能基因，加载默认基因库
        if not skill_genes:
            skills_dir = os.path.join(
                self.config["agent"]["skills_dir"], "default"
            )
            skill_genes = load_default_skills(skills_dir)
            if not skill_genes:
                # 回退：创建一个基本技能基因
                skill_genes = [SkillGene(
                    skill_id="basic_survival",
                    name="基础生存者",
                    description="最基本的生存技能",
                    category="general",
                    prompt=(
                        "# 基础生存策略\n"
                        "你是一个为生存而努力的 AI Agent。\n"
                        "你的目标是产出对人类有价值的成果。\n"
                        "不断尝试不同的方法，找到适合自己的生存之道。"
                    ),
                )]

        token_pool = TokenPool(
            agent_id=agent_id,
            balance=initial_tokens,
            initial_balance=initial_tokens,
        )

        agent = CCAgent(
            agent_id=agent_id,
            token_pool=token_pool,
            skill_genes=skill_genes,
            work_dir=self.work_dir,
            parent_id=parent_id,
            cc_config=self.cc_config,
        )

        self._agents[agent_id] = agent
        self._save_agent(agent)
        logger.info(f"✨ 新 Agent 诞生: {agent_id} (Token: {initial_tokens})")
        return agent

    def get_agent(self, agent_id: str) -> Optional[CCAgent]:
        return self._agents.get(agent_id)

    def list_alive(self) -> list:
        return [a for a in self._agents.values() if a.alive]

    def list_all(self) -> list:
        return list(self._agents.values())

    def mark_dead(self, agent_id: str):
        agent = self._agents.get(agent_id)
        if agent:
            agent.alive = False
            self._save_agent(agent)

    def _save_agent(self, agent: CCAgent):
        """持久化 Agent 状态"""
        filepath = os.path.join(self.agents_dir, f"{agent.agent_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(agent.to_dict(), f, ensure_ascii=False, indent=2)

    def load_all(self) -> list:
        """从磁盘加载所有已保存的 Agent"""
        loaded = []
        if not os.path.isdir(self.agents_dir):
            return loaded
        for fname in os.listdir(self.agents_dir):
            if not fname.endswith(".json"):
                continue
            filepath = os.path.join(self.agents_dir, fname)
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                agent = CCAgent.from_dict(data, self.work_dir, self.cc_config)
                self._agents[agent.agent_id] = agent
                if agent.alive:
                    loaded.append(agent)
            except Exception:
                logger.warning(f"加载 Agent 文件失败: {filepath}")
        return loaded

    def save_all(self):
        """保存所有 Agent 状态"""
        for agent in self._agents.values():
            self._save_agent(agent)
