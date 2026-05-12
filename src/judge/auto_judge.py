"""
自动评判规则
初期主要依赖人类评判，自动评判作为辅助。
后期可逐步引入更多自动化指标来加速演化。
"""

import os
import logging
from typing import Optional

from .judge_queue import JudgeQueue

logger = logging.getLogger(__name__)


class AutoJudge:
    """自动评判器 —— 对产出进行自动化评估"""

    def __init__(self, rules: list, agent_manager):
        self.rules = rules
        self.agent_manager = agent_manager

    def evaluate(self, submission, rules_config: list) -> Optional[int]:
        """评估一个提交，返回应奖励的 Token 数，或 None（需人工评判）"""
        total_reward = 0
        any_matched = False

        for rule in rules_config:
            reward = self._apply_rule(submission, rule)
            if reward is not None:
                total_reward += reward
                any_matched = True

        return total_reward if any_matched else None

    def _apply_rule(self, submission, rule: dict) -> Optional[int]:
        rule_type = rule.get("type", "")
        reward = rule.get("reward", 0)

        if rule_type == "code_runnable":
            # 检查产出是否包含可运行代码
            return self._check_runnable_code(submission, reward)
        elif rule_type == "file_produced":
            # 只要产生了文件就奖励
            if os.path.exists(submission.output_file):
                return reward
        elif rule_type == "self_check_passed":
            # 产出中包含自我验证通过的标记
            if "自我验证: 通过" in submission.output:
                return reward

        return None

    def _check_runnable_code(self, submission, reward: int) -> Optional[int]:
        """检查产出中是否包含代码块"""
        has_code = "```" in submission.output and len(submission.output) > 200
        return reward if has_code else None
