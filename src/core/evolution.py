"""
演化引擎
- 繁殖：Token 充裕的 Agent 可以产生子代，技能基因遗传+变异
- 死亡：Token 归零的 Agent 被归档为"化石"
- 自然选择：表现好→获更多 Token→活更久→繁殖更多→好策略扩散
"""

import os
import uuid
import random
import logging
from datetime import datetime
from typing import Optional

from .token_pool import TokenPool
from ..skills.skill_gene import SkillGene, mutate_skill

logger = logging.getLogger(__name__)


class EvolutionEngine:
    def __init__(self, config: dict, agent_manager: "AgentManager"):
        self.config = config
        self.agent_manager = agent_manager
        self.fossils_dir = os.path.join(
            config["system"]["data_dir"], "fossils"
        )

    def try_reproduce(self, agent) -> Optional["Agent"]:
        """如果 Agent Token 超过繁殖阈值，尝试繁殖"""
        evo_cfg = self.config["evolution"]
        econ_cfg = self.config["token_economy"]
        threshold = econ_cfg["reproduction_threshold"]
        max_agents = evo_cfg["max_agents"]

        if not agent.token_pool.can_reproduce(threshold):
            return None
        if len(self.agent_manager.list_alive()) >= max_agents:
            logger.info(f"Agent {agent.agent_id} 想繁殖但已到达上限 {max_agents}")
            return None

        # 消耗繁殖 Token
        cost = econ_cfg["reproduction_cost"]
        agent.token_pool.spend(cost, reason="繁殖")

        # 子代技能基因：遗传+变异
        parent_skills = agent.get_skill_genes()
        child_skills = []
        for skill in parent_skills:
            mutated = mutate_skill(
                skill,
                mutation_rate=self.config["evolution"]["mutation_rate"],
            )
            child_skills.append(mutated)

        # 创建子代
        child_id = f"{agent.agent_id}_offspring_{uuid.uuid4().hex[:6]}"
        child = self.agent_manager.create_agent(
            agent_id=child_id,
            initial_tokens=econ_cfg["offspring_initial_tokens"],
            skill_genes=child_skills,
            parent_id=agent.agent_id,
        )

        logger.info(
            f"🐣 繁殖！{agent.agent_id} → {child_id} "
            f"(消耗 {cost} Token，子代继承 {len(child_skills)} 个技能基因)"
        )
        return child

    def archive_dead_agent(self, agent) -> None:
        """归档死亡 Agent 为化石"""
        fossil = {
            "agent_id": agent.agent_id,
            "parent_id": agent.parent_id,
            "born_at": agent.born_at,
            "died_at": datetime.now().isoformat(),
            "lifespan_seconds": (
                datetime.now() - datetime.fromisoformat(agent.born_at)
            ).total_seconds(),
            "token_pool": agent.token_pool.to_dict(),
            "skill_genes": [s.to_dict() for s in agent.get_skill_genes()],
            "task_history": agent.task_history[-50:],
            "cause_of_death": "token_exhausted",
        }

        fossil_path = os.path.join(
            self.fossils_dir, f"fossil_{agent.agent_id}.json"
        )
        import json

        with open(fossil_path, "w", encoding="utf-8") as f:
            json.dump(fossil, f, ensure_ascii=False, indent=2)

        logger.info(
            f"💀 {agent.agent_id} 已死亡，生存了 "
            f"{fossil['lifespan_seconds']:.0f} 秒，化石已存档"
        )

    def check_population(self) -> bool:
        """检查种群数量，低于下限时自动创建新 Agent"""
        alive = self.agent_manager.list_alive()
        min_agents = self.config["evolution"]["min_agents"]
        if len(alive) < min_agents:
            # 从化石中选最优策略作为"种子"，或使用初始技能
            seed_skills = self._get_best_fossil_skills()
            for i in range(min_agents - len(alive)):
                new_id = f"agent_genesis_{uuid.uuid4().hex[:6]}"
                self.agent_manager.create_agent(
                    agent_id=new_id,
                    initial_tokens=self.config["token_economy"][
                        "initial_token_budget"
                    ],
                    skill_genes=seed_skills,
                )
                logger.info(f"🌱 种群补充: 创建新 Agent {new_id}")
            return True
        return False

    def _get_best_fossil_skills(self) -> list:
        """从化石记录中获取表现最好的技能基因作为种子"""
        import json
        import glob

        fossil_files = glob.glob(os.path.join(self.fossils_dir, "*.json"))
        if not fossil_files:
            from ..skills.skill_gene import load_default_skills

            return load_default_skills(
                os.path.join(
                    self.config["agent"]["skills_dir"], "default"
                )
            )

        # 按 total_earned 排序，取 top 3 的技能
        fossils = []
        for fp in fossil_files:
            try:
                with open(fp, encoding="utf-8") as f:
                    fossils.append(json.load(f))
            except Exception:
                pass

        fossils.sort(
            key=lambda x: x.get("token_pool", {}).get("total_earned", 0),
            reverse=True,
        )

        skills = []
        for fossil in fossils[:3]:
            for skill_data in fossil.get("skill_genes", []):
                skills.append(SkillGene.from_dict(skill_data))
        return skills[:5]  # 最多 5 个种子基因
