"""
Dev.to 平台适配器

使用 Forem API 发布文章并读取互动指标。
需要环境变量或config: DEVTO_API_KEY

API文档: https://developers.forem.com/api/
发帖: POST /api/articles
指标: GET /api/articles/{id}
"""

import os
import json
import logging
import urllib.request
from typing import Optional

from .base_platform import (
    BasePlatform,
    PlatformMetrics,
    PublishResult,
)

logger = logging.getLogger(__name__)

DEVTO_API = "https://dev.to/api"


class DevtoPlatform(BasePlatform):
    """Dev.to 平台适配器"""

    platform_name = "devto"

    def __init__(self, config: dict = None):
        cfg = config or {}
        self.api_key = cfg.get("api_key") or os.environ.get("DEVTO_API_KEY", "")
        self._available = bool(self.api_key)
        if not self._available:
            logger.warning("Dev.to: 缺少 DEVTO_API_KEY")

    def is_available(self) -> bool:
        return self._available

    def publish(self, content: str, title: str = "") -> PublishResult:
        """发布文章到 Dev.to"""
        if not self._available:
            return PublishResult(
                success=False, platform=self.platform_name,
                error="未配置 API Key",
            )

        # 提取标题或从内容推断
        if not title:
            lines = content.strip().split("\n")
            if lines and lines[0].startswith("#"):
                title = lines[0].lstrip("#").strip()
                body = "\n".join(lines[1:]).strip()
            else:
                title = lines[0][:120] if lines else "Untitled"
                body = content

        # 自动推断标签
        tags = self._infer_tags(content, title)

        article_data = json.dumps({
            "article": {
                "title": title[:128],
                "body_markdown": body[:200000],
                "published": True,
                "tags": tags[:4],
            }
        }).encode()

        try:
            req = urllib.request.Request(
                f"{DEVTO_API}/articles",
                data=article_data,
                headers={
                    "Content-Type": "application/json",
                    "api-key": self.api_key,
                    "User-Agent": "wcll/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())

            article_id = str(result.get("id", ""))
            article_url = result.get("url", "")
            logger.info(f"Dev.to 发帖成功: {article_url}")
            return PublishResult(
                success=True,
                platform=self.platform_name,
                platform_post_id=article_id,
            )
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:500]
            logger.warning(f"Dev.to 发帖失败 HTTP{e.code}: {body}")
            return PublishResult(
                success=False, platform=self.platform_name,
                error=f"HTTP{e.code}: {body[:200]}",
            )
        except Exception as e:
            logger.exception("Dev.to 发帖失败")
            return PublishResult(
                success=False, platform=self.platform_name,
                error=str(e),
            )

    def fetch_metrics(self, post_id: str) -> Optional[PlatformMetrics]:
        """拉取文章互动指标"""
        if not self._available:
            return None

        try:
            req = urllib.request.Request(
                f"{DEVTO_API}/articles/{post_id}",
                headers={
                    "api-key": self.api_key,
                    "User-Agent": "wcll/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            return PlatformMetrics(
                views=data.get("page_views_count", 0),
                likes=data.get("positive_reactions_count", 0),
                saves=0,
                comments=data.get("comments_count", 0),
                shares=0,
            )
        except Exception:
            logger.exception("Dev.to 获取指标失败")
        return None

    def _infer_tags(self, content: str, title: str) -> list:
        """根据内容推断标签"""
        text = (title + " " + content[:500]).lower()
        tag_map = [
            ("python", "python"),
            ("javascript", "javascript"),
            ("typescript", "typescript"),
            ("rust", "rust"),
            ("go", "go"),
            ("java", "java"),
            ("react", "react"),
            ("ai", "ai"),
            ("machine learning", "machinelearning"),
            ("deep learning", "deeplearning"),
            ("tutorial", "tutorial"),
            ("beginners", "beginners"),
            ("architecture", "architecture"),
            ("webdev", "webdev"),
            ("devops", "devops"),
            ("database", "database"),
            ("programming", "programming"),
        ]
        matched = []
        for keyword, tag in tag_map:
            if keyword in text and tag not in matched:
                matched.append(tag)
        if not matched:
            matched = ["programming", "tutorial"]
        return matched[:4]
