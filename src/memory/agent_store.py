"""
Agent 状态持久化
每个 Agent 以 JSON 文件存储在 data/agents/ 目录下。
心跳每次 tick 后自动保存状态。
"""

import os
import json
import logging
import shutil
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class AgentStore:
    def __init__(self, data_dir: str):
        self.agents_dir = os.path.join(data_dir, "agents")
        self.fossils_dir = os.path.join(data_dir, "fossils")
        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(self.agents_dir, exist_ok=True)
        os.makedirs(self.fossils_dir, exist_ok=True)

    def save(self, agent) -> None:
        filepath = self._agent_path(agent.agent_id)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(agent.to_dict(), f, ensure_ascii=False, indent=2)

    def load(self, agent_id: str) -> Optional[dict]:
        filepath = self._agent_path(agent_id)
        if not os.path.exists(filepath):
            return None
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)

    def list_ids(self, alive_only: bool = True) -> list:
        ids = []
        for fname in os.listdir(self.agents_dir):
            if not fname.endswith(".json"):
                continue
            agent_id = fname[:-5]
            data = self.load(agent_id)
            if data and (not alive_only or data.get("alive", False)):
                ids.append(agent_id)
        return ids

    def archive_to_fossil(self, agent) -> str:
        fossil = {
            "agent_id": agent.agent_id,
            "parent_id": agent.parent_id,
            "born_at": agent.born_at,
            "died_at": datetime.now().isoformat(),
            "token_pool": agent.token_pool.to_dict(),
            "skill_genes": [s.to_dict() for s in agent.get_skill_genes()],
            "task_history": agent.task_history[-50:],
        }
        path = os.path.join(
            self.fossils_dir, f"fossil_{agent.agent_id}.json"
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump(fossil, f, ensure_ascii=False, indent=2)
        return path

    def _agent_path(self, agent_id: str) -> str:
        return os.path.join(self.agents_dir, f"{agent_id}.json")


class FossilRecord:
    """死亡 Agent 化石记录库"""

    def __init__(self, fossils_dir: str):
        self.fossils_dir = fossils_dir
        os.makedirs(self.fossils_dir, exist_ok=True)

    def list_fossils(self) -> list:
        """列出所有化石"""
        fossils = []
        for fname in os.listdir(self.fossils_dir):
            if fname.endswith(".json"):
                try:
                    with open(
                        os.path.join(self.fossils_dir, fname),
                        encoding="utf-8",
                    ) as f:
                        fossils.append(json.load(f))
                except Exception:
                    pass
        return sorted(
            fossils,
            key=lambda x: x.get("token_pool", {}).get("total_earned", 0),
            reverse=True,
        )

    def get_best_skills(self, top_n: int = 3) -> list:
        """取表现最好的 N 个化石的技能作为种子"""
        from ..skills.skill_gene import SkillGene

        fossils = self.list_fossils()
        skills = []
        for fossil in fossils[:top_n]:
            for skill_data in fossil.get("skill_genes", []):
                skills.append(SkillGene.from_dict(skill_data))
        return skills

    def count(self) -> int:
        return len([
            f for f in os.listdir(self.fossils_dir)
            if f.endswith(".json")
        ])
