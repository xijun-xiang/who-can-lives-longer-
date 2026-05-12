"""
人类评判 Web UI —— 系统的"上帝视角"

提供一个简洁的 Web 界面：
- 查看所有待评判的 Agent 产出
- 打分（奖励 Token）
- 查看 Agent 存活状态
- 查看系统运行状态
"""

import json
import logging
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, redirect, url_for

from ..core.heartbeat import Heartbeat
from ..agents.agent_manager import AgentManager
from .judge_queue import JudgeQueue

logger = logging.getLogger(__name__)

# ── HTML 模板 ──

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Who Can Lives Longer - 评判面板</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #c9d1d9; max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { color: #58a6ff; font-size: 1.5em; margin-bottom: 4px; }
        .subtitle { color: #8b949e; font-size: 0.85em; margin-bottom: 24px; }
        .status-bar { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
        .status-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; min-width: 120px; }
        .status-card .label { font-size: 0.75em; color: #8b949e; text-transform: uppercase; }
        .status-card .value { font-size: 1.3em; font-weight: bold; color: #58a6ff; }
        .status-card .value.danger { color: #f85149; }
        .status-card .value.success { color: #3fb950; }
        .section-title { font-size: 1.1em; color: #f0f6fc; margin: 24px 0 12px; padding-bottom: 8px; border-bottom: 1px solid #30363d; }
        .submission { background: #161b22; border: 1px solid #30363d; border-radius: 8px; margin-bottom: 12px; overflow: hidden; }
        .submission-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; background: #1c2333; }
        .submission-header .agent { font-weight: bold; color: #58a6ff; }
        .submission-header .time { font-size: 0.8em; color: #8b949e; }
        .submission-body { padding: 16px; }
        .submission-body pre { background: #0d1117; padding: 12px; border-radius: 4px; overflow-x: auto; max-height: 400px; font-size: 0.85em; line-height: 1.5; white-space: pre-wrap; }
        .actions { display: flex; gap: 8px; padding: 10px 16px; background: #1c2333; }
        .btn { padding: 6px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 0.85em; font-weight: 600; }
        .btn-reward { background: #238636; color: #fff; }
        .btn-reward:hover { background: #2ea043; }
        .btn-skip { background: #30363d; color: #c9d1d9; }
        .btn-skip:hover { background: #484f58; }
        .reward-input { background: #0d1117; border: 1px solid #30363d; color: #c9d1d9; padding: 6px 10px; border-radius: 6px; width: 80px; }
        .agent-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
        .agent-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px; }
        .agent-card.dead { opacity: 0.5; border-color: #f85149; }
        .agent-card .name { font-weight: bold; color: #58a6ff; margin-bottom: 6px; }
        .agent-card .stat { font-size: 0.8em; color: #8b949e; }
        .agent-card .stat strong { color: #c9d1d9; }
        .empty-message { color: #8b949e; text-align: center; padding: 40px; font-style: italic; }
        .refresh-hint { font-size: 0.8em; color: #484f58; margin-top: 20px; text-align: center; }
    </style>
</head>
<body>
    <h1>🧬 Who Can Lives Longer</h1>
    <p class="subtitle">LLM Agent 生存演化生态系统 · 评判面板</p>

    <div class="status-bar">
        <div class="status-card">
            <div class="label">运行状态</div>
            <div class="value {{ 'success' if status.running else 'danger' }}">{{ '运行中' if status.running else '已停止' }}</div>
        </div>
        <div class="status-card">
            <div class="label">心跳周期</div>
            <div class="value">{{ status.cycles_completed }}</div>
        </div>
        <div class="status-card">
            <div class="label">存活 Agent</div>
            <div class="value">{{ status.alive_agents }}</div>
        </div>
        <div class="status-card">
            <div class="label">待评判</div>
            <div class="value">{{ pending|length }}</div>
        </div>
        <div class="status-card">
            <div class="label">运行时长</div>
            <div class="value">{{ (status.uptime_seconds / 3600)|round(1) }}h</div>
        </div>
    </div>

    <h2 class="section-title">📋 待评判产出 ({{ pending|length }})</h2>
    {% if pending %}
        {% for sub in pending %}
        <div class="submission">
            <div class="submission-header">
                <span class="agent">🤖 {{ sub.agent_id }}</span>
                <span class="time">{{ sub.timestamp }} · 余额: {{ sub.token_balance }} Token</span>
            </div>
            <div class="submission-body">
                <pre>{{ sub.output[:2000] }}{% if sub.output|length > 2000 %}...(截断，共 {{ sub.output|length }} 字符){% endif %}</pre>
            </div>
            <div class="actions">
                <form method="POST" action="/judge/{{ sub.submission_id }}" style="display:flex;gap:8px;align-items:center;">
                    <input type="number" name="reward" class="reward-input" value="500" min="0" max="10000" step="100" title="奖励 Token 数">
                    <input type="text" name="feedback" placeholder="评语 (可选)" style="background:#0d1117;border:1px solid #30363d;color:#c9d1d9;padding:6px 10px;border-radius:6px;width:200px;">
                    <button type="submit" class="btn btn-reward">奖励 Token</button>
                </form>
                <form method="POST" action="/skip/{{ sub.submission_id }}">
                    <button type="submit" class="btn btn-skip">跳过</button>
                </form>
            </div>
        </div>
        {% endfor %}
    {% else %}
        <p class="empty-message">暂无待评判产出。Agent 正在工作中，等待下一个心跳周期...</p>
    {% endif %}

    <h2 class="section-title">🧬 Agent 种群</h2>
    <div class="agent-list">
        {% for agent in agents %}
        <div class="agent-card {{ 'dead' if not agent.alive }}">
            <div class="name">{{ '💀' if not agent.alive else '🤖' }} {{ agent.agent_id }}</div>
            <div class="stat">Token 余额: <strong>{{ agent.token_pool.balance }}</strong></div>
            <div class="stat">累计赚取: <strong>{{ agent.token_pool.total_earned }}</strong></div>
            <div class="stat">累计消耗: <strong>{{ agent.token_pool.total_spent }}</strong></div>
            <div class="stat">技能基因: <strong>{{ agent.skill_genes|length }} 个</strong></div>
            <div class="stat">产出次数: <strong>{{ agent.task_history|length }}</strong></div>
            {% if agent.parent_id %}
            <div class="stat">父代: <strong>{{ agent.parent_id }}</strong></div>
            {% endif %}
        </div>
        {% endfor %}
    </div>

    <p class="refresh-hint">页面每 30 秒自动刷新 · 手动刷新: F5</p>
    <script>setTimeout(() => location.reload(), 30000);</script>
</body>
</html>"""


def create_app(
    agent_manager: AgentManager,
    judge_queue: JudgeQueue,
    heartbeat: Heartbeat,
    config: dict,
) -> Flask:
    """创建 Flask Web 应用"""
    app = Flask(__name__)

    @app.route("/")
    def index():
        status = heartbeat.get_status()
        pending = sorted(
            judge_queue.get_pending(),
            key=lambda s: s.submission_id,
            reverse=True,
        )
        agents = sorted(
            agent_manager.list_all(),
            key=lambda a: a.token_pool.balance,
            reverse=True,
        )
        return render_template_string(
            HTML_TEMPLATE,
            status=status,
            pending=pending,
            agents=[a.to_dict() for a in agents],
        )

    @app.route("/judge/<submission_id>", methods=["POST"])
    def judge_submission(submission_id):
        reward = int(request.form.get("reward", 500))
        feedback = request.form.get("feedback", "")

        sub = judge_queue.judge(submission_id, reward, feedback)
        if not sub:
            return jsonify({"error": "提交不存在"}), 404

        # 注入 Token 到 Agent
        agent = agent_manager.get_agent(sub.agent_id)
        if agent:
            agent.token_pool.reward(reward, reason=f"人类评判: {feedback}")
            agent_manager._save_agent(agent)

        return redirect(url_for("index"))

    @app.route("/skip/<submission_id>", methods=["POST"])
    def skip_submission(submission_id):
        judge_queue.skip(submission_id)
        return redirect(url_for("index"))

    @app.route("/api/status")
    def api_status():
        return jsonify(heartbeat.get_status())

    @app.route("/api/agents")
    def api_agents():
        return jsonify([
            a.to_dict() for a in agent_manager.list_all()
        ])

    return app
