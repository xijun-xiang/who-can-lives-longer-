"""
奖励公式引擎

将平台互动指标（浏览/点赞/收藏/评论/分享）映射为Token奖励。
只奖励增量——每次检查只计算自上次以来的新增互动。
"""

import logging
from .platforms.base_platform import PlatformMetrics

logger = logging.getLogger(__name__)


class RewardEngine:
    """指标 → Token 奖励计算"""

    def __init__(self, formula_config: dict):
        self.formula = formula_config

    def calculate_reward(
        self, metrics: PlatformMetrics, previous: PlatformMetrics
    ) -> int:
        """
        计算从上次检查到现在的增量Token奖励

        formula: min(metric_value * tokens_per_unit, max_reward)
        仅奖励增量部分（当前值 - 上次值）
        """
        delta = metrics.delta(previous)

        total = 0
        for metric_name, rule in self.formula.items():
            value = getattr(delta, metric_name, 0)
            if value <= 0:
                continue

            tokens_per_unit = rule.get("tokens_per_unit", 0)
            max_reward = rule.get("max_reward", 0)

            reward = min(int(value * tokens_per_unit), max_reward)
            if reward > 0:
                logger.debug(
                    f"  指标 {metric_name}: {value} × {tokens_per_unit} "
                    f"= {reward} (上限 {max_reward})"
                )
            total += reward

        return total

    def calculate_total(
        self, metrics: PlatformMetrics
    ) -> int:
        """计算总Token奖励（从零开始，不基于增量）"""
        total = 0
        for metric_name, rule in self.formula.items():
            value = getattr(metrics, metric_name, 0)
            tokens_per_unit = rule.get("tokens_per_unit", 0)
            max_reward = rule.get("max_reward", 0)
            reward = min(int(value * tokens_per_unit), max_reward)
            total += reward
        return total
