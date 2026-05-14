"""
平台发布编排器

统一调度所有启用平台的发布和指标收集。
作为心跳循环与各平台之间的中间层。
"""

import logging
from datetime import datetime
from typing import Optional

from .reward_engine import RewardEngine
from .platform_tracker import PlatformTracker
from .platforms.base_platform import BasePlatform, PublishResult

logger = logging.getLogger(__name__)


class PlatformPublisher:
    """编排器：管理所有启用的平台"""

    def __init__(
        self,
        config: dict,
        platform_tracker: PlatformTracker,
        reward_engine: RewardEngine,
        agent_manager,
    ):
        self.config = config
        self.tracker = platform_tracker
        self.reward_engine = reward_engine
        self.agent_manager = agent_manager
        self._platforms: list[BasePlatform] = []
        self.check_interval = config["judge"]["platforms"][
            "check_interval_seconds"
        ]
        self.publish_cooldown = config["judge"]["platforms"][
            "publish_cooldown_minutes"
        ]
        self._last_check_time: Optional[datetime] = None

    def register_platform(self, platform: BasePlatform) -> None:
        """注册一个平台适配器"""
        self._platforms.append(platform)
        logger.info(f"📡 平台已注册: {platform.platform_name}")

    def publish_pending(self, agent, platform: str = None) -> None:
        """将Agent的最新产出发布到指定平台(或所有平台)"""
        if not agent.task_history:
            return

        latest = agent.task_history[-1]
        content = latest.get("output_preview", "")
        if not content or len(content) < 50:
            return

        # 确定目标平台列表
        targets = (
            [p for p in self._platforms if p.platform_name == platform]
            if platform
            else self._platforms
        )

        for plat in targets:
            if not plat.is_available():
                continue
            try:
                result = plat.publish(content)
                if result.success:
                    self.tracker.track_publish(
                        agent_id=agent.agent_id,
                        platform=plat.platform_name,
                        content_preview=content,
                        platform_post_id=result.platform_post_id,
                    )
                    logger.info(
                        f"📤 {agent.agent_id} → {plat.platform_name} 发布成功"
                    )
                elif result.needs_manual_action:
                    sub = self.tracker.track_publish(
                        agent_id=agent.agent_id,
                        platform=plat.platform_name,
                        content_preview=content,
                        platform_post_id="pending_manual",
                    )
                    sub.status = "pending"
                    sub.content_preview = result.content_for_manual
                    self.tracker._save(sub)
                    logger.info(
                        f"📋 {agent.agent_id} → {plat.platform_name} 待人工"
                    )
            except Exception:
                logger.exception(f"发布到 {plat.platform_name} 失败")

    def collect_and_reward(self) -> dict[str, int]:
        """拉取所有活跃提交的指标并发放Token奖励"""
        should_check = (
            self._last_check_time is None
            or (
                datetime.now() - self._last_check_time
            ).total_seconds() >= self.check_interval
        )
        if not should_check:
            return {}

        self._last_check_time = datetime.now()
        rewards: dict[str, int] = {}

        fresh_subs = self.tracker.get_fresh_submissions()
        if not fresh_subs:
            return rewards

        for sub in fresh_subs:
            if sub.status == "pending":
                continue  # 待人工发布，跳过

            platform = self._find_platform(sub.platform)
            if not platform or not platform.is_available():
                continue

            try:
                post_id = sub.platform_post_id
                if not post_id or post_id == "pending_manual":
                    continue

                new_metrics = platform.fetch_metrics(post_id)
                if new_metrics is None:
                    continue

                # 计算增量奖励
                reward = self.reward_engine.calculate_reward(
                    new_metrics, sub.previous_metrics
                )

                if reward > 0:
                    # 更新指标记录
                    self.tracker.update_metrics(sub, new_metrics)
                    sub.rewards_granted += reward

                    # 发放Token
                    agent = self.agent_manager.get_agent(sub.agent_id)
                    if agent:
                        agent.token_pool.reward(
                            reward,
                            reason=(
                                f"平台互动 {sub.platform}: "
                                f"浏览{new_metrics.views} "
                                f"赞{new_metrics.likes} "
                                f"藏{new_metrics.saves}"
                            ),
                        )
                        rewards[sub.agent_id] = (
                            rewards.get(sub.agent_id, 0) + reward
                        )

                    logger.info(
                        f"🏆 {sub.agent_id} 获得 +{reward} Token "
                        f"(来自 {sub.platform} 互动)"
                    )

            except Exception:
                logger.exception(
                    f"检查提交 {sub.submission_id} 指标失败"
                )

        if rewards:
            logger.info(
                f"📊 本轮平台奖励汇总: "
                + ", ".join(
                    f"{aid}: +{r}" for aid, r in rewards.items()
                )
            )
        return rewards

    def _find_platform(self, name: str) -> Optional[BasePlatform]:
        for p in self._platforms:
            if p.platform_name == name:
                return p
        return None

    @property
    def platform_names(self) -> list:
        return [p.platform_name for p in self._platforms]
