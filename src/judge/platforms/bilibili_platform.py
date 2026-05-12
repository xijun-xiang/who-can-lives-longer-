"""
Bilibili 平台适配器

使用B站开放平台API发布专栏文章并读取互动数据。
需要环境变量: BILIBILI_CLIENT_ID, BILIBILI_CLIENT_SECRET

API文档: https://openhome.bilibili.com/doc
"""

import os
import logging
import urllib.request
import json
import time
from typing import Optional

from .base_platform import (
    BasePlatform,
    PlatformMetrics,
    PublishResult,
)

logger = logging.getLogger(__name__)


class BilibiliPlatform(BasePlatform):
    """B站平台适配器（专栏发布）"""

    platform_name = "bilibili"

    def __init__(self):
        self.client_id = os.environ.get("BILIBILI_CLIENT_ID", "")
        self.client_secret = os.environ.get("BILIBILI_CLIENT_SECRET", "")
        self._available = bool(self.client_id and self.client_secret)
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        if not self._available:
            logger.warning(
                "Bilibili 平台未配置: 缺少环境变量"
            )

    def is_available(self) -> bool:
        return self._available

    def publish(self, content: str, title: str = "") -> PublishResult:
        """
        发布专栏文章到B站
        需要先通过开放平台审核才能使用此接口。
        当前阶段返回手动发布模式。
        """
        if not self._available:
            return PublishResult(
                success=False,
                platform=self.platform_name,
                error="未配置 API 密钥",
            )

        # B站专栏发布需要企业认证 + 开放平台审核
        # 当前返回手动代理模式
        return PublishResult(
            success=False,
            platform=self.platform_name,
            needs_manual_action=True,
            content_for_manual=(
                f"[准备发布到B站专栏]\n\n"
                f"标题: {title or 'AI Agent 生存日记'}\n\n"
                f"{content[:1000]}\n\n"
                f"请手动发布后将专栏CV号或链接填入评判面板。"
            ),
        )

    def fetch_metrics(self, post_id: str) -> Optional[PlatformMetrics]:
        """
        拉取专栏互动指标
        使用B站开放平台数据API
        """
        if not self._available:
            return None

        cv_id = self._extract_cv_id(post_id)

        # B站专栏数据API (需要access_token)
        url = (
            "https://api.bilibili.com/x/web-interface/view"
            f"?id={cv_id}"
            "&type=article"
        )

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "wcll/1.0",
                "Referer": "https://www.bilibili.com",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            if data.get("code") != 0:
                logger.warning(f"B站API错误: {data.get('message')}")
                return None

            stats = data.get("data", {}).get("stats", {})
            return PlatformMetrics(
                views=stats.get("view", 0),
                likes=stats.get("like", 0),
                saves=stats.get("favorite", 0),
                comments=stats.get("reply", 0),
                shares=stats.get("share", 0),
            )
        except urllib.error.HTTPError as e:
            logger.warning(f"B站API HTTP错误 {e.code}")
        except Exception:
            logger.exception("B站拉取指标失败")
        return None

    @staticmethod
    def _extract_cv_id(post_id: str) -> str:
        """从B站专栏链接中提取CV号"""
        if post_id.lower().startswith("cv"):
            return post_id[2:]
        if post_id.isdigit():
            return post_id
        # cv数字格式
        parts = post_id.rstrip("/").split("/")
        for p in parts:
            clean = p.strip().lower()
            if clean.startswith("cv") and clean[2:].isdigit():
                return clean[2:]
        return post_id
