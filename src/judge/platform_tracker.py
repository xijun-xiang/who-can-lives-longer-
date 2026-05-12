"""
平台发布追踪器 —— 持久化层

管理所有平台发布的完整生命周期:
- 记录新发布
- 更新互动指标
- 查询待检查的活跃提交
- 统计Agent的平台表现
"""

import os
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Union

from .platforms.base_platform import (
    PlatformSubmission,
    PlatformMetrics,
)

logger = logging.getLogger(__name__)


class PlatformTracker:
    """追踪所有平台发布及其互动指标"""

    def __init__(self, data_dir: str, freshness_hours: int = 72):
        self.storage_dir = os.path.join(data_dir, "platform_submissions")
        self.freshness_hours = freshness_hours
        os.makedirs(self.storage_dir, exist_ok=True)

    def track_publish(
        self,
        agent_id: str,
        platform: str,
        content_preview: str,
        platform_post_id: str = "",
    ) -> PlatformSubmission:
        """记录一次新的平台发布"""
        sub = PlatformSubmission(
            submission_id=f"plat_{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            platform=platform,
            platform_post_id=platform_post_id,
            content_preview=content_preview[:500],
            published_at=datetime.now().isoformat(),
            last_checked_at=datetime.now().isoformat(),
            status="published",
        )
        self._save(sub)
        logger.info(f"📤 记录发布: {sub.submission_id} → {platform}")
        return sub

    def update_metrics(
        self, submission: PlatformSubmission, new_metrics: PlatformMetrics
    ) -> None:
        """更新互动指标（保留旧指标作为previous）"""
        submission.previous_metrics = PlatformMetrics(
            views=submission.metrics.views,
            likes=submission.metrics.likes,
            saves=submission.metrics.saves,
            comments=submission.metrics.comments,
            shares=submission.metrics.shares,
        )
        submission.metrics = new_metrics
        submission.last_checked_at = datetime.now().isoformat()
        submission.status = "checked"
        self._save(submission)

    def mark_closed(self, submission: PlatformSubmission) -> None:
        """标记提交为已关闭（超过新鲜期，不再追踪）"""
        submission.status = "closed"
        self._save(submission)

    def get_fresh_submissions(self) -> list[PlatformSubmission]:
        """获取所有仍在新鲜期内的活跃提交"""
        cutoff = datetime.now() - timedelta(hours=self.freshness_hours)
        fresh = []
        for fname in os.listdir(self.storage_dir):
            if not fname.endswith(".json"):
                continue
            try:
                sub = self._load(fname)
                if sub.status == "closed":
                    continue
                published = datetime.fromisoformat(sub.published_at)
                if published > cutoff:
                    fresh.append(sub)
                else:
                    self.mark_closed(sub)
            except Exception:
                logger.warning(f"加载提交文件失败: {fname}")
        return fresh

    def get_agent_submissions(
        self, agent_id: str
    ) -> list[PlatformSubmission]:
        """获取某Agent的所有平台提交"""
        results = []
        for fname in os.listdir(self.storage_dir):
            if not fname.endswith(".json"):
                continue
            try:
                sub = self._load(fname)
                if sub.agent_id == agent_id:
                    results.append(sub)
            except Exception:
                pass
        return sorted(
            results,
            key=lambda s: s.published_at,
            reverse=True,
        )

    def get_all_recent(self, limit: int = 20) -> list[PlatformSubmission]:
        """获取最近的提交"""
        subs = []
        for fname in os.listdir(self.storage_dir):
            if not fname.endswith(".json"):
                continue
            try:
                subs.append(self._load(fname))
            except Exception:
                pass
        subs.sort(key=lambda s: s.published_at, reverse=True)
        return subs[:limit]

    def get_submission(self, submission_id: str) -> Optional[PlatformSubmission]:
        """按ID查询单个提交"""
        fname = f"{submission_id}.json"
        filepath = os.path.join(self.storage_dir, fname)
        if not os.path.exists(filepath):
            return None
        try:
            return self._load(fname)
        except Exception:
            return None

    def save_submission(self, submission: PlatformSubmission) -> None:
        """公开保存/更新提交"""
        self._save(submission)

    def _save(self, submission: PlatformSubmission) -> None:
        filepath = os.path.join(
            self.storage_dir, f"{submission.submission_id}.json"
        )
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(submission.to_dict(), f, ensure_ascii=False, indent=2)

    def _load(self, fname: str) -> PlatformSubmission:
        filepath = os.path.join(self.storage_dir, fname)
        with open(filepath, encoding="utf-8") as f:
            return PlatformSubmission.from_dict(json.load(f))
