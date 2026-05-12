"""
手动代理平台

为没有公开API的平台（知乎、抖音等）提供人工桥接:
1. Agent产出 → 系统记录为"待人工发布"
2. 人类复制内容到平台
3. 人类回填链接和互动数据到Web UI
4. 系统计算Token奖励

这是目前唯一默认启用的平台模式。
"""

import logging
from datetime import datetime
from typing import Optional

from .base_platform import (
    BasePlatform,
    PlatformMetrics,
    PublishResult,
)

logger = logging.getLogger(__name__)


class ManualProxyPlatform(BasePlatform):
    """手动代理平台适配器 — 通用人工桥接"""

    platform_name = "manual"

    def __init__(self, platform_label: str = "manual"):
        """
        platform_label: 显示用的平台名，如 "zhihu" | "douyin" | "manual"
        """
        self.platform_name = platform_label
        self._pending_content: dict[str, str] = {}  # sub_id → content

    def publish(self, content: str, title: str = "") -> PublishResult:
        """
        "发布"到手动代理——实际是生成待人类处理的记录
        """
        return PublishResult(
            success=False,
            platform=self.platform_name,
            needs_manual_action=True,
            content_for_manual=content,
        )

    def fetch_metrics(self, post_id: str) -> Optional[PlatformMetrics]:
        """
        手动代理不主动拉取指标。
        指标由人类通过 Web UI POST /manual-metrics 填入。
        """
        return None
