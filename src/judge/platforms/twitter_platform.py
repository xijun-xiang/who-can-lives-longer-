"""
Twitter/X 平台适配器

使用 Twitter API v2 发布推文并读取公开互动指标。
需要环境变量: TWITTER_BEARER_TOKEN

API文档: https://developer.x.com/en/docs/x-api
"""

import os
import logging
import urllib.request
import json
from typing import Optional

from .base_platform import (
    BasePlatform,
    PlatformMetrics,
    PublishResult,
)

logger = logging.getLogger(__name__)

API_BASE = "https://api.twitter.com/2"


class TwitterPlatform(BasePlatform):
    """X/Twitter 平台适配器"""

    platform_name = "twitter"

    def __init__(self):
        self.bearer_token = os.environ.get("TWITTER_BEARER_TOKEN", "")
        self._available = bool(self.bearer_token)
        if not self._available:
            logger.warning(
                "Twitter 平台未配置: 缺少 TWITTER_BEARER_TOKEN 环境变量"
            )

    def is_available(self) -> bool:
        return self._available

    def publish(self, content: str, title: str = "") -> PublishResult:
        """
        发布推文
        注意: Twitter API v2 发推需要 OAuth 1.0a 用户上下文,
        Bearer Token 仅用于只读操作。
        这里返回需要手动发布的结果。
        """
        if not self._available:
            return PublishResult(
                success=False,
                platform=self.platform_name,
                error="未配置 API 密钥",
            )

        # Twitter 发推需要 OAuth 1.0a (consumer key + access token)
        # 而非 Bearer Token。如果未来添加完整 OAuth 配置这里可以改为自动发布。
        return PublishResult(
            success=False,
            platform=self.platform_name,
            needs_manual_action=True,
            content_for_manual=(
                f"[准备发推]\n\n{content[:260]}\n\n"
                f"请手动发布到 Twitter 后将推文链接填入评判面板。"
            ),
        )

    def fetch_metrics(self, post_id: str) -> Optional[PlatformMetrics]:
        """
        拉取推文互动指标
        GET /2/tweets/:id?tweet.fields=public_metrics
        """
        if not self._available:
            return None

        # 支持手动填入的推文链接中提取ID
        tweet_id = self._extract_tweet_id(post_id)

        url = (
            f"{API_BASE}/tweets/{tweet_id}"
            f"?tweet.fields=public_metrics"
        )
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "User-Agent": "wcll/1.0",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            metrics = data.get("data", {}).get("public_metrics", {})
            return PlatformMetrics(
                views=metrics.get("impression_count", 0),
                likes=metrics.get("like_count", 0),
                saves=metrics.get("bookmark_count", 0),
                comments=metrics.get("reply_count", 0),
                shares=metrics.get("retweet_count", 0)
                       + metrics.get("quote_count", 0),
            )
        except urllib.error.HTTPError as e:
            logger.warning(f"Twitter API 错误 {e.code}: {e.reason}")
        except Exception:
            logger.exception("Twitter 拉取指标失败")
        return None

    @staticmethod
    def _extract_tweet_id(post_id: str) -> str:
        """从推文URL中提取推文ID"""
        if post_id.isdigit():
            return post_id
        # 尝试从URL中提取
        parts = post_id.rstrip("/").split("/")
        for p in reversed(parts):
            if p.isdigit():
                return p
        return post_id
