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
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class Heartbeat:
    """心跳调度器：驱动整个生态系统持续运转"""

    def __init__(self, config: dict, agent_manager, judge_queue, evolution_engine):
        self.config = config
        self.agent_manager = agent_manager
        self.judge_queue = judge_queue
        self.evolution = evolution_engine
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

        # 3. 每个 Agent 行动
        submissions_this_tick = 0
        for agent in alive_agents:
            try:
                # 扣除行动消耗
                cost = self.config["token_economy"]["action_cost_per_inference"]
                still_alive = agent.token_pool.spend(cost, reason="心跳行动消耗")

                if not still_alive:
                    # Agent 刚刚归零
                    self._handle_death(agent)
                    continue

                # Agent 决策并产出
                result = agent.act()

                if result and result.get("submitted"):
                    submissions_this_tick += 1
                    self.judge_queue.submit(agent.agent_id, result)

            except Exception:
                logger.exception(f"Agent {agent.agent_id} 行动异常")

        # 4. 检查繁殖条件
        for agent in alive_agents:
            try:
                self.evolution.try_reproduce(agent)
            except Exception:
                logger.exception(f"Agent {agent.agent_id} 繁殖检查异常")

        # 5. 日志
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
