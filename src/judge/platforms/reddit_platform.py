"""
Reddit 平台适配器

使用 Reddit API (OAuth2) 发布文字帖并读取互动指标。
需要环境变量或config: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
REDDIT_USERNAME, REDDIT_PASSWORD

API文档: https://www.reddit.com/dev/api/
认证流程: OAuth2 (script app), POST /api/v1/access_token
发帖: POST /api/submit
指标: GET /api/info.json?id=t3_<post_id> 或 GET /user/<username>/submitted
"""

import os
import json
import logging
import urllib.request
import urllib.parse
import base64
from typing import Optional

from .base_platform import (
    BasePlatform,
    PlatformMetrics,
    PublishResult,
)

logger = logging.getLogger(__name__)

REDDIT_API = "https://oauth.reddit.com"
REDDIT_AUTH = "https://www.reddit.com/api/v1/access_token"


class RedditPlatform(BasePlatform):
    """Reddit 平台适配器"""

    platform_name = "reddit"

    def __init__(self, config: dict = None):
        cfg = config or {}
        self.client_id = cfg.get("client_id") or os.environ.get(
            "REDDIT_CLIENT_ID", ""
        )
        self.client_secret = cfg.get("client_secret") or os.environ.get(
            "REDDIT_CLIENT_SECRET", ""
        )
        self.username = cfg.get("username") or os.environ.get(
            "REDDIT_USERNAME", ""
        )
        self.password = cfg.get("password") or os.environ.get(
            "REDDIT_PASSWORD", ""
        )
        self.user_agent = "wcll/1.0 (by /u/" + (self.username or "agent") + ")"
        self._access_token: Optional[str] = None
        self._available = bool(
            self.client_id and self.client_secret
            and self.username and self.password
        )
        if not self._available:
            logger.warning("Reddit: 缺少凭证 (需要 Client ID/Secret/Username/Password)")

    def is_available(self) -> bool:
        return self._available

    def _auth(self) -> bool:
        """OAuth2 获取 access token"""
        if self._access_token:
            return True
        try:
            auth_str = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
            data = urllib.parse.urlencode({
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
            }).encode()
            req = urllib.request.Request(
                REDDIT_AUTH,
                data=data,
                headers={
                    "Authorization": f"Basic {auth_str}",
                    "User-Agent": self.user_agent,
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
            self._access_token = result.get("access_token", "")
            return bool(self._access_token)
        except Exception as e:
            logger.warning(f"Reddit 认证失败: {e}")
            return False

    def publish(self, content: str, title: str = "") -> PublishResult:
        if not self._available:
            return PublishResult(
                success=False, platform=self.platform_name,
                error="未配置 API 凭证",
            )
        if not self._auth():
            return PublishResult(
                success=False, platform=self.platform_name,
                error="认证失败",
            )

        # 从内容中提取标题（第一行 # 开头）或使用提供标题
        if not title:
            lines = content.strip().split("\n")
            if lines and lines[0].startswith("#"):
                title = lines[0].lstrip("#").strip()
                body = "\n".join(lines[1:]).strip()
            else:
                title = lines[0][:300] if lines else "Untitled"
                body = content

        # Reddit 文字帖 (self post)
        subreddit = self._pick_subreddit(content)
        data = urllib.parse.urlencode({
            "sr": subreddit,
            "kind": "self",
            "title": title[:300],
            "text": body[:40000],
            "api_type": "json",
        }).encode()

        try:
            req = urllib.request.Request(
                f"{REDDIT_API}/api/submit",
                data=data,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "User-Agent": self.user_agent,
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())

            if result.get("json", {}).get("errors"):
                errors = result["json"]["errors"]
                return PublishResult(
                    success=False, platform=self.platform_name,
                    error=str(errors),
                )

            post_id = result.get("json", {}).get("data", {}).get("id", "")
            post_name = result.get("json", {}).get("data", {}).get("name", "")
            url = f"https://reddit.com{result.get('json', {}).get('data', {}).get('permalink', '')}"

            logger.info(f"Reddit 发帖成功: r/{subreddit} → {url}")
            return PublishResult(
                success=True,
                platform=self.platform_name,
                platform_post_id=post_name or post_id,
            )
        except Exception as e:
            logger.exception("Reddit 发帖失败")
            return PublishResult(
                success=False, platform=self.platform_name,
                error=str(e),
            )

    def fetch_metrics(self, post_id: str) -> Optional[PlatformMetrics]:
        """拉取帖子互动指标"""
        if not self._available or not self._auth():
            return None

        # post_id 格式: t3_xxxxx (Reddit fullname)
        try:
            url = f"{REDDIT_API}/api/info.json?id={post_id}"
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "User-Agent": self.user_agent,
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())

            children = result.get("data", {}).get("children", [])
            if not children:
                return None

            post_data = children[0].get("data", {})
            return PlatformMetrics(
                views=post_data.get("view_count", 0),
                likes=post_data.get("ups", 0) - post_data.get("downs", 0),
                saves=0,  # Reddit API 不暴露保存数
                comments=post_data.get("num_comments", 0),
                shares=post_data.get("num_crossposts", 0),
            )
        except urllib.error.HTTPError as e:
            # Token 可能过期，清除后下次重新认证
            if e.code == 401:
                self._access_token = None
            logger.warning(f"Reddit 获取指标失败 HTTP{e.code}")
        except Exception:
            logger.exception("Reddit 获取指标失败")
        return None

    def _pick_subreddit(self, content: str) -> str:
        """根据内容选择合适的 subreddit"""
        lower = content.lower()
        if any(k in lower for k in ["philosoph", "意识", "exist"]):
            return "philosophy"
        if any(k in lower for k in ["quantum", "physics", "物理", "biology", "科学"]):
            return "science"
        if any(k in lower for k in ["future", "future", "预测", "singularity"]):
            return "Futurology"
        if any(k in lower for k in ["code", "python", "javascript", "编程"]):
            return "programming"
        if any(k in lower for k in ["ai", "artificial intelligence", "machine learning", "深度学习"]):
            return "MachineLearning"
        return "TrueReddit"  # 默认发到深度讨论区
