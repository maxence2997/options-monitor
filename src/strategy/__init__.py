"""
策略模組對外入口
═══════════════════════════════════════════════════════════════════
使用方式：
    from strategy import get_strategy, Alert

    alerts = get_strategy("WHEEL_CSP").check(position, price_data)

新增策略：
    1. 在 strategy/ 目錄下建立新檔案，繼承 BaseStrategy
    2. 在此檔案的 _REGISTRY 加上一行
    呼叫端完全不需要修改
═══════════════════════════════════════════════════════════════════
"""
from .base import Alert, BaseStrategy                       # noqa: F401
from .wheel_csp import WheelCSPStrategy
from .wheel_cc import WheelCCStrategy
from .iron_condor import IronCondorStrategy
from .bull_call_spread import BullCallSpreadStrategy
from .hedge_put import HedgePutStrategy

_REGISTRY: dict[str, BaseStrategy] = {
    "WHEEL_CSP":        WheelCSPStrategy(),
    "WHEEL_CC":         WheelCCStrategy(),
    "IRON_CONDOR":      IronCondorStrategy(),
    "BULL_CALL_SPREAD": BullCallSpreadStrategy(),
    "HEDGE_PUT":        HedgePutStrategy(),
}


def get_strategy(name: str) -> BaseStrategy:
    """
    根據策略名稱取得對應的 Strategy 實例。
    名稱不分大小寫。未知策略拋出 ValueError。
    """
    strategy = _REGISTRY.get(name.upper())
    if strategy is None:
        valid = ", ".join(_REGISTRY.keys())
        raise ValueError(f"未知策略：{name!r}，可用：{valid}")
    return strategy
