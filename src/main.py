"""
Who Can Lives Longer — 系统入口

用法:
    python -m src.main              # 启动完整系统
    python -m src.main --init       # 初始化初始 Agent 种群
    python -m src.main --web-only   # 仅启动 Web 评判面板
"""

import os
import sys
import yaml
import logging
import argparse
import signal
from pathlib import Path

from .core.heartbeat import Heartbeat
from .core.evolution import EvolutionEngine
from .agents.agent_manager import AgentManager
from .judge.judge_queue import JudgeQueue
from .judge.auto_judge import AutoJudge
from .judge.human_judge import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("wcll")


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def init_population(
    agent_manager: AgentManager,
    config: dict,
) -> None:
    """初始化初始 Agent 种群"""
    existing = agent_manager.load_all()
    if existing:
        logger.info(f"已从磁盘加载 {len(existing)} 个存活 Agent，跳过初始化")
        return

    # 创建初始 Agent
    for i in range(3):
        agent_id = f"agent_alpha_{i+1}"
        agent_manager.create_agent(
            agent_id=agent_id,
            initial_tokens=config["token_economy"]["initial_token_budget"],
        )
    logger.info("初始种群已创建: 3 个 Agent")


def start_system(config_path: str, web_only: bool = False):
    """启动系统"""
    config = load_config(config_path)
    web_cfg = config["judge"]

    # 初始化组件
    agent_manager = AgentManager(config)
    judge_queue = JudgeQueue(max_pending=50)
    auto_judge = AutoJudge(
        rules=web_cfg.get("auto_judge_rules", []),
        agent_manager=agent_manager,
    )

    # 初始化种群
    init_population(agent_manager, config)

    # 初始化演化引擎
    evolution = EvolutionEngine(config, agent_manager)

    # 心跳
    heartbeat = Heartbeat(config, agent_manager, judge_queue, evolution)

    if not web_only:
        heartbeat.start()
        logger.info("=" * 50)
        logger.info("🧬 Who Can Lives Longer 已启动")
        logger.info(f"   心跳间隔: {config['system']['heartbeat_interval_seconds']}s")
        logger.info(f"   初始 Agent: {len(agent_manager.list_alive())} 个")
        logger.info(f"   评判面板: http://{web_cfg['web_host']}:{web_cfg['web_port']}")
        logger.info("   按 Ctrl+C 停止")
        logger.info("=" * 50)

    # 启动 Web UI
    app = create_app(agent_manager, judge_queue, heartbeat, config)

    def shutdown(sig, frame):
        logger.info("正在关闭系统...")
        heartbeat.stop()
        agent_manager.save_all()
        logger.info("系统已安全关闭")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    app.run(
        host=web_cfg["web_host"],
        port=web_cfg["web_port"],
        debug=False,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Who Can Lives Longer - LLM Agent 生存演化生态系统"
    )
    parser.add_argument(
        "-c", "--config", default="config.yaml", help="配置文件路径"
    )
    parser.add_argument(
        "--init", action="store_true", help="仅初始化 Agent 种群"
    )
    parser.add_argument(
        "--web-only", action="store_true", help="仅启动 Web 评判面板"
    )
    args = parser.parse_args()

    # 确保在项目根目录
    os.chdir(Path(__file__).parent.parent)

    if args.init:
        config = load_config(args.config)
        agent_manager = AgentManager(config)
        init_population(agent_manager, config)
        logger.info("种群初始化完成")
        return

    start_system(args.config, web_only=args.web_only)


if __name__ == "__main__":
    main()
