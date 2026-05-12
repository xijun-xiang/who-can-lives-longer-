"""
平台抽象基类

定义所有平台的统一接口:
- publish: 发布内容到平台
- fetch_metrics: 拉取互动指标
- platform_name: 平台标识
"""

import uuid
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PlatformMetrics:
    """平台互动指标"""
    views: int = 0
    likes: int = 0
    saves: int = 0
    comments: int = 0
    shares: int = 0

    def to_dict(self) -> dict:
        return {
            "views": self.views,
            "likes": self.likes,
            "saves": self.saves,
            "comments": self.comments,
            "shares": self.shares,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PlatformMetrics":
        return cls(
            views=d.get("views", 0),
            likes=d.get("likes", 0),
            saves=d.get("saves", 0),
            comments=d.get("comments", 0),
            shares=d.get("shares", 0),
        )

    def delta(self, previous: "PlatformMetrics") -> "PlatformMetrics":
        """计算与上次检查的增量"""
        return PlatformMetrics(
            views=max(0, self.views - previous.views),
            likes=max(0, self.likes - previous.likes),
            saves=max(0, self.saves - previous.saves),
            comments=max(0, self.comments - previous.comments),
            shares=max(0, self.shares - previous.shares),
        )


@dataclass
class PlatformSubmission:
    """一次平台发布记录"""
    submission_id: str
    agent_id: str
    platform: str
    platform_post_id: str = ""
    content_preview: str = ""
    published_at: str = ""
    last_checked_at: str = ""
    metrics: PlatformMetrics = field(default_factory=PlatformMetrics)
    previous_metrics: PlatformMetrics = field(default_factory=PlatformMetrics)
    rewards_granted: int = 0
    status: str = "pending"  # pending | published | checked | closed

    def to_dict(self) -> dict:
        return {
            "submission_id": self.submission_id,
            "agent_id": self.agent_id,
            "platform": self.platform,
            "platform_post_id": self.platform_post_id,
            "content_preview": self.content_preview,
            "published_at": self.published_at,
            "last_checked_at": self.last_checked_at,
            "metrics": self.metrics.to_dict(),
            "previous_metrics": self.previous_metrics.to_dict(),
            "rewards_granted": self.rewards_granted,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PlatformSubmission":
        return cls(
            submission_id=d["submission_id"],
            agent_id=d["agent_id"],
            platform=d.get("platform", ""),
            platform_post_id=d.get("platform_post_id", ""),
            content_preview=d.get("content_preview", ""),
            published_at=d.get("published_at", ""),
            last_checked_at=d.get("last_checked_at", ""),
            metrics=PlatformMetrics.from_dict(d.get("metrics", {})),
            previous_metrics=PlatformMetrics.from_dict(
                d.get("previous_metrics", {})
            ),
            rewards_granted=d.get("rewards_granted", 0),
            status=d.get("status", "pending"),
        )


@dataclass
class PublishResult:
    """发布结果"""
    success: bool
    platform_post_id: str = ""
    platform: str = ""
    error: str = ""
    needs_manual_action: bool = False
    content_for_manual: str = ""


class BasePlatform(ABC):
    """平台适配器抽象基类"""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        ...

    @abstractmethod
    def publish(self, content: str, title: str = "") -> PublishResult:
        """发布内容到平台，返回发布结果"""
        ...

    @abstractmethod
    def fetch_metrics(self, post_id: str) -> Optional[PlatformMetrics]:
        """拉取指定帖子的互动指标，失败返回None"""
        ...

    def is_available(self) -> bool:
        """检查平台是否可用（API密钥等是否就绪）"""
        return True
