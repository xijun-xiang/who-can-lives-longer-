"""
Token 池管理器
每个 Agent 拥有一个 Token 池，Token 是 Agent 的"生命值"。
- 每次推理行动消耗 Token
- 人类评判奖励注入 Token
- Token 归零 → Agent 死亡
- Token 超阈值 → 可繁殖
"""

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TokenPool:
    agent_id: str
    balance: int
    initial_balance: int
    total_earned: int = 0
    total_spent: int = 0
    transactions: list = field(default_factory=list)

    def spend(self, amount: int, reason: str = "") -> bool:
        """消耗 Token，返回是否成功（不会透支到负数）"""
        actual = min(amount, self.balance)
        self.balance -= actual
        self.total_spent += actual
        self.transactions.append({
            "time": time.time(),
            "type": "spend",
            "amount": actual,
            "reason": reason,
            "balance_after": self.balance,
        })
        return self.balance > 0  # 返回是否还活着

    def reward(self, amount: int, reason: str = "") -> None:
        """获得 Token 奖励"""
        self.balance += amount
        self.total_earned += amount
        self.transactions.append({
            "time": time.time(),
            "type": "reward",
            "amount": amount,
            "reason": reason,
            "balance_after": self.balance,
        })

    def is_alive(self) -> bool:
        return self.balance > 0

    def can_reproduce(self, threshold: int) -> bool:
        return self.balance >= threshold

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "balance": self.balance,
            "initial_balance": self.initial_balance,
            "total_earned": self.total_earned,
            "total_spent": self.total_spent,
            "recent_transactions": self.transactions[-20:],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TokenPool":
        pool = cls(
            agent_id=d["agent_id"],
            balance=d["balance"],
            initial_balance=d.get("initial_balance", d["balance"]),
            total_earned=d.get("total_earned", 0),
            total_spent=d.get("total_spent", 0),
        )
        pool.transactions = d.get("recent_transactions", [])
        return pool
