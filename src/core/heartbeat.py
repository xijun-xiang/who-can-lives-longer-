"""
心跳循环调度器 —— 系统的"脉搏"

串行模式：每个周期只让 1 个 Agent 行动（轮转制）。
Agent 全力产出深度内容 → 发布到对应平台 → 收集平台互动 → 触发进化。
"""

import time
import logging
import threading
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class Heartbeat:
    """心跳调度器：串行轮转，驱动生态系统运转"""

    def __init__(self, config: dict, agent_manager, judge_queue, evolution_engine,
                 platform_publisher=None, agent_platform_map: dict = None):
        self.config = config
        self.agent_manager = agent_manager
        self.judge_queue = judge_queue
        self.evolution = evolution_engine
        self.platform_publisher = platform_publisher
        self.agent_platform_map = agent_platform_map or {}
        self.interval = config["system"]["heartbeat_interval_seconds"]
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.cycle_count = 0
        self._agent_index = 0
        self.start_time: Optional[datetime] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self.start_time = datetime.now()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(
            f"💓 心跳已启动 (串行模式), 间隔 {self.interval}s "
            f"(≈{self.interval/3600:.1f}小时)"
        )

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info(f"💓 心跳已停止, 共运行 {self.cycle_count} 个周期")

    def _loop(self):
        while self._running:
            try:
                self._tick()
            except Exception:
                logger.exception("心跳周期异常")
            time.sleep(self.interval)

    def _tick(self):
        self.cycle_count += 1
        tick_start = time.time()

        # 1. 检查种群
        self.evolution.check_population()

        # 2. 获取存活 Agent 并选一个（轮转）
        alive = self.agent_manager.list_alive()
        if not alive:
            logger.warning("无存活 Agent")
            return

        agent = self._select_next(alive)
        platform = self.agent_platform_map.get(agent.agent_id, "unknown")

        logger.info(
            f"🎯 周期 #{self.cycle_count}: {agent.agent_id} → {platform}"
        )

        # 3. Agent 行动（串行，单个）
        try:
            result = agent.act()
        except Exception:
            logger.exception(f"{agent.agent_id} 行动异常")
            result = None

        if not result:
            self._post_tick(alive, tick_start, 0)
            return

        if not result.get("still_alive", True):
            self._handle_death(agent)
            self._post_tick(alive, tick_start, 0)
            return

        submitted = 0
        if result.get("submitted"):
            self.judge_queue.submit(agent.agent_id, result)
            submitted = 1

        # 4. 发布到该 Agent 绑定的平台
        if self.platform_publisher and self._platforms_enabled():
            try:
                self.platform_publisher.publish_pending(agent, platform=platform)
            except Exception:
                logger.exception(f"{agent.agent_id} 平台发布异常")

        # 5. 收集所有平台指标 + 触发进化
        if self.platform_publisher:
            try:
                self.platform_publisher.collect_and_reward()
            except Exception:
                logger.exception("指标收集异常")

        # 6. 繁殖检查（所有 Agent）
        self._post_tick(alive, tick_start, submitted)

    def _post_tick(self, alive, tick_start, submitted):
        for a in alive:
            try:
                self.evolution.try_reproduce(a)
            except Exception:
                logger.exception(f"{a.agent_id} 繁殖检查异常")

        elapsed = time.time() - tick_start
        logger.info(
            f"💓 周期 #{self.cycle_count} ({elapsed:.0f}s, "
            f"{len(alive)} 存活, {submitted} 提交)"
        )

    def _select_next(self, alive):
        idx = self._agent_index % len(alive)
        self._agent_index += 1
        return alive[idx]

    def _platforms_enabled(self) -> bool:
        return self.config.get("judge", {}).get("platforms", {}).get("enabled", False)

    def _handle_death(self, agent):
        logger.info(f"💀 {agent.agent_id} Token 耗尽")
        self.agent_manager.mark_dead(agent.agent_id)
        self.evolution.archive_dead_agent(agent)

    def get_status(self) -> dict:
        alive = self.agent_manager.list_alive()
        return {
            "running": self._running,
            "cycles_completed": self.cycle_count,
            "started_at": self.start_time.isoformat() if self.start_time else None,
            "uptime_seconds": (
                (datetime.now() - self.start_time).total_seconds()
                if self.start_time else 0
            ),
            "alive_agents": len(alive),
            "pending_judgments": self.judge_queue.pending_count(),
            "interval_seconds": self.interval,
        }
