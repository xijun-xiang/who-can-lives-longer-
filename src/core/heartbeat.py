"""
心跳循环调度器 —— 系统的"脉搏"

每个心跳周期：
1. 唤醒所有存活 Agent
2. Agent 根据技能基因决策并产出
3. 产出提交到评判队列
4. 处理死亡/繁殖
5. 等待下一个周期

这是整个系统"持续自主运行"的核心。
"""

import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class Heartbeat:
    """心跳调度器：驱动整个生态系统持续运转"""

    def __init__(self, config: dict, agent_manager, judge_queue, evolution_engine,
                 platform_publisher=None):
        self.config = config
        self.agent_manager = agent_manager
        self.judge_queue = judge_queue
        self.evolution = evolution_engine
        self.platform_publisher = platform_publisher
        self.interval = config["system"]["heartbeat_interval_seconds"]
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.cycle_count = 0
        self.start_time: Optional[datetime] = None

    def start(self):
        """启动心跳循环（后台线程）"""
        if self._running:
            return
        self._running = True
        self.start_time = datetime.now()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(
            f"💓 心跳已启动，间隔 {self.interval}s "
            f"(≈{self.interval/60:.1f}分钟)"
        )

    def stop(self):
        """停止心跳"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info(f"💓 心跳已停止，共运行 {self.cycle_count} 个周期")

    def _loop(self):
        """主循环"""
        while self._running:
            try:
                self._tick()
            except Exception:
                logger.exception("心跳周期异常，将在下个周期重试")
            time.sleep(self.interval)

    def _tick(self):
        """一个心跳周期"""
        self.cycle_count += 1
        tick_start = time.time()

        # 1. 检查种群数量（自动补充）
        self.evolution.check_population()

        # 2. 唤醒每个 Agent
        alive_agents = self.agent_manager.list_alive()
        if not alive_agents:
            logger.warning("⚠️ 无存活 Agent！等待种群补充...")
            return

        # 3. 每个 Agent 行动（并发执行）
        submissions_this_tick = 0

        def agent_action(agent):
            try:
                result = agent.act()
                if not result:
                    return (False, agent)

                # act() 内部已按实际 token 消耗扣费，检查是否还活着
                if not result.get("still_alive", True):
                    self._handle_death(agent)
                    return (False, agent)

                if result.get("submitted"):
                    self.judge_queue.submit(agent.agent_id, result)
                    return (True, agent)
                return (False, agent)
            except Exception:
                logger.exception(f"Agent {agent.agent_id} 行动异常")
                return (False, agent)

        with ThreadPoolExecutor(max_workers=min(len(alive_agents), 10)) as executor:
            futures = {
                executor.submit(agent_action, agent): agent
                for agent in alive_agents
            }
            for future in as_completed(futures, timeout=600):
                submitted, agent = future.result()
                if submitted:
                    submissions_this_tick += 1

        # 4. 检查繁殖条件
        for agent in alive_agents:
            try:
                self.evolution.try_reproduce(agent)
            except Exception:
                logger.exception(f"Agent {agent.agent_id} 繁殖检查异常")

        # 5. 发布到平台
        if self.platform_publisher and self.config.get("judge", {}).get(
            "platforms", {}
        ).get("enabled", False):
            for agent in alive_agents:
                try:
                    self.platform_publisher.publish_pending(agent)
                except Exception:
                    logger.exception(f"Agent {agent.agent_id} 平台发布异常")

        # 6. 收集平台指标并发放奖励
        if self.platform_publisher:
            try:
                self.platform_publisher.collect_and_reward()
            except Exception:
                logger.exception("平台指标收集异常")

        # 7. 日志
        elapsed = time.time() - tick_start
        logger.info(
            f"💓 周期 #{self.cycle_count} 完成 "
            f"({elapsed:.1f}s, "
            f"{len(alive_agents)} 个存活, "
            f"{submissions_this_tick} 个新提交)"
        )

    def _handle_death(self, agent):
        """处理 Agent 死亡"""
        logger.info(f"💀 Agent {agent.agent_id} Token 耗尽，即将归档...")
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
                if self.start_time
                else 0
            ),
            "alive_agents": len(alive),
            "pending_judgments": self.judge_queue.pending_count(),
            "interval_seconds": self.interval,
        }
