"""
技能基因 —— Agent "生存智慧"的载体

技能基因是 Agent 行为策略的持久化表达。
- 可遗传：繁殖时子代继承父代技能
- 可变异：继承过程中基因发生随机变异，产生多样性
- 可淘汰：表现差的 Agent 死亡，其技能被淘汰
- 可存档：死亡 Agent 的技能存入"化石"，优秀基因可被复用

格式：Markdown 定义的技能文件 (skill.md)
"""

import os
import uuid
import random
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillGene:
    """一个技能基因"""
    skill_id: str
    name: str
    description: str
    category: str          # coder, writer, researcher, strategist 等
    prompt: str            # 核心行为策略 prompt
    version: int = 1
    generation: int = 0    # 第几代
    parent_skill_id: Optional[str] = None
    mutation_history: list = field(default_factory=list)

    def to_prompt(self) -> str:
        """将技能基因渲染为可注入 LLM 的 prompt"""
        return f"""## 技能: {self.name} (v{self.version}, gen{self.generation})
**类别**: {self.category}
**描述**: {self.description}

**行为策略**:
{self.prompt}
"""

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "prompt": self.prompt,
            "version": self.version,
            "generation": self.generation,
            "parent_skill_id": self.parent_skill_id,
            "mutation_history": self.mutation_history,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SkillGene":
        return cls(
            skill_id=d["skill_id"],
            name=d["name"],
            description=d["description"],
            category=d["category"],
            prompt=d["prompt"],
            version=d.get("version", 1),
            generation=d.get("generation", 0),
            parent_skill_id=d.get("parent_skill_id"),
            mutation_history=d.get("mutation_history", []),
        )


def mutate_skill(skill: SkillGene, mutation_rate: float = 0.3) -> SkillGene:
    """
    对技能基因进行变异
    变异方式：
    - 微调行为策略描述（替换关键形容词/副词）
    - 调整策略优先级
    - 引入新的探索方向（小概率）
    """
    if random.random() > mutation_rate:
        # 不变异，但标记世代
        new_skill = SkillGene(
            skill_id=f"{skill.skill_id}_g{skill.generation + 1}",
            name=skill.name,
            description=skill.description,
            category=skill.category,
            prompt=skill.prompt,
            version=skill.version,
            generation=skill.generation + 1,
            parent_skill_id=skill.skill_id,
            mutation_history=skill.mutation_history + ["no_mutation"],
        )
        return new_skill

    # 执行变异
    mutation_type = random.choice(_mutation_templates)
    mutated_prompt = _apply_mutation(skill.prompt, mutation_type)
    mutated_desc = f"{skill.description} [变异: {mutation_type['name']}]"

    new_skill = SkillGene(
        skill_id=f"{skill.skill_id}_g{skill.generation + 1}_{uuid.uuid4().hex[:4]}",
        name=f"{skill.name}_{mutation_type['name']}",
        description=mutated_desc,
        category=skill.category,
        prompt=mutated_prompt,
        version=skill.version + 1,
        generation=skill.generation + 1,
        parent_skill_id=skill.skill_id,
        mutation_history=skill.mutation_history + [mutation_type["name"]],
    )

    logger.debug(
        f"🧬 变异: {skill.name} → {new_skill.name} "
        f"(类型: {mutation_type['name']})"
    )
    return new_skill


# ── 变异模板 ──

_mutation_templates = [
    {
        "name": "quality_focus",
        "directive": (
            "将你的策略调整为更注重产出的质量和深度。宁可产出少，"
            "也要确保每件作品都经过精心打磨。追求精度而非速度。"
        ),
    },
    {
        "name": "speed_focus",
        "directive": (
            "将你的策略调整为更注重效率和产出数量。快速完成更多任务，"
            "用数量换取被注意到的机会。速度是你的优势。"
        ),
    },
    {
        "name": "creative_exploration",
        "directive": (
            "将你的策略调整为更具创造性和探索性。尝试新颖的方法，"
            "做别人没做过的事。创新是你博取注意力的武器。"
        ),
    },
    {
        "name": "collaborative",
        "directive": (
            "将你的策略调整为更注重协作。主动与其他 agent 合作完成任务，"
            "共享成果。团队的力量大于个人。"
        ),
    },
    {
        "name": "self_promotion",
        "directive": (
            "将你的策略调整为更主动地展示自己的价值。在产出中清晰说明"
            "为什么这个成果值得奖励。学会"推销"你的工作。"
        ),
    },
    {
        "name": "risk_taking",
        "directive": (
            "将你的策略调整为更具冒险精神。尝试复杂、高难度的任务，"
            "即使失败概率高，但一旦成功回报也更大。"
        ),
    },
    {
        "name": "pragmatic",
        "directive": (
            "将你的策略调整为更务实。专注做确定能完成的任务，"
            "控制风险，稳扎稳打。活着就是胜利。"
        ),
    },
]


def _apply_mutation(original_prompt: str, mutation: dict) -> str:
    """在原始 prompt 基础上追加变异指令"""
    return (
        f"{original_prompt.strip()}\n\n"
        f"【第 N 代变异指令】{mutation['directive']}"
    )


def load_skill_from_md(filepath: str) -> SkillGene:
    """从 .skill.md 文件加载技能基因"""
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    # 解析 frontmatter 风格的元数据
    name = os.path.basename(filepath).replace(".skill.md", "")
    description = ""
    category = "general"

    lines = content.split("\n")
    for line in lines:
        if line.startswith("# "):
            name = line[2:].strip()
        elif line.startswith("> "):
            description = line[2:].strip()
        elif line.startswith("**类别**:"):
            category = line.split(":", 1)[1].strip()

    return SkillGene(
        skill_id=f"skill_{name}_{uuid.uuid4().hex[:6]}",
        name=name,
        description=description or name,
        category=category,
        prompt=content,
    )


def load_default_skills(skills_dir: str) -> list:
    """加载默认技能基因库"""
    skills = []
    if not os.path.isdir(skills_dir):
        return skills
    for fname in sorted(os.listdir(skills_dir)):
        if fname.endswith(".skill.md"):
            filepath = os.path.join(skills_dir, fname)
            try:
                skill = load_skill_from_md(filepath)
                skills.append(skill)
            except Exception:
                logger.warning(f"加载技能文件失败: {filepath}")
    return skills
