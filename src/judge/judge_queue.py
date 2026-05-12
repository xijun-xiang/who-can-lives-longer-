"""
评判队列 —— 产出物等待人类评判的缓冲区

Agent 产出提交到此队列，人类通过 Web UI 查看并评分。
评分后 Token 自动注入对应 Agent 的 Token 池。
"""

import time
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Submission:
    """一个待评判的 Agent 产出"""
    submission_id: str
    agent_id: str
    output: str
    output_file: str
    timestamp: str
    token_balance: int
    status: str = "pending"   # pending | judged | skipped
    reward: int = 0
    feedback: str = ""
    judged_at: Optional[str] = None


class JudgeQueue:
    def __init__(self, max_pending: int = 50):
        self._queue: deque[Submission] = deque()
        self._history: list[Submission] = []
        self._max_pending = max_pending
        self._id_counter = 0

    def submit(self, agent_id: str, result: dict) -> Submission:
        """提交产出到评判队列"""
        self._id_counter += 1
        sub = Submission(
            submission_id=f"sub_{self._id_counter:06d}",
            agent_id=agent_id,
            output=result.get("output", ""),
            output_file=result.get("output_file", ""),
            timestamp=result.get("timestamp", ""),
            token_balance=result.get("token_balance", 0),
        )
        self._queue.append(sub)

        # 限制队列大小
        while len(self._queue) > self._max_pending:
            old = self._queue.popleft()
            old.status = "skipped"
            self._history.append(old)

        logger.debug(f"📥 新提交: {sub.submission_id} (来自 {agent_id})")
        return sub

    def get_pending(self) -> list:
        """获取所有待评判的提交"""
        return list(self._queue)

    def pending_count(self) -> int:
        return len(self._queue)

    def judge(
        self,
        submission_id: str,
        reward: int,
        feedback: str = "",
    ) -> Optional[Submission]:
        """评判一个提交"""
        for sub in self._queue:
            if sub.submission_id == submission_id:
                sub.status = "judged"
                sub.reward = reward
                sub.feedback = feedback
                sub.judged_at = time.strftime("%Y-%m-%d %H:%M:%S")
                self._queue.remove(sub)
                self._history.append(sub)
                logger.info(
                    f"✅ 评判: {submission_id} "
                    f"(Agent {sub.agent_id}) → +{reward} Token"
                )
                return sub
        return None

    def skip(self, submission_id: str) -> Optional[Submission]:
        """跳过某个提交（不给奖励也不惩罚）"""
        for sub in self._queue:
            if sub.submission_id == submission_id:
                sub.status = "skipped"
                self._queue.remove(sub)
                self._history.append(sub)
                return sub
        return None

    def get_history(self, limit: int = 50) -> list:
        return self._history[-limit:]

    def get_agent_submissions(self, agent_id: str) -> list:
        return [s for s in self._history if s.agent_id == agent_id]
