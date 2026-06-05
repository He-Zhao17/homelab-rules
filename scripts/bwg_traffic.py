from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_ENDPOINT = "https://api.64clouds.com/v1/getServiceInfo"


@dataclass(frozen=True)
class BandwagonUsage:
    """Bandwagon/KiwiVM 月流量使用情况。

    字段都使用字节作为单位，避免在判断阈值时混入 GB/GiB 换算误差。
    """

    used_bytes: int
    total_bytes: int
    remaining_bytes: int
    used_ratio: float
    next_reset: int | None


def parse_usage(payload: dict[str, Any]) -> BandwagonUsage:
    """从 KiwiVM `getServiceInfo` 响应中提取月流量比例。

    只读取 `data_counter` 和 `plan_monthly_data` 两个核心字段。这样即使 API 返回了
    VPS 状态、内存、硬盘等额外信息，也不会影响订阅发布时的节点排序决策。
    """

    used = int(payload["data_counter"])
    total = int(payload["plan_monthly_data"])
    if total <= 0:
        raise ValueError("plan_monthly_data 必须大于 0，无法计算流量使用比例")

    remaining = max(total - used, 0)
    return BandwagonUsage(
        used_bytes=used,
        total_bytes=total,
        remaining_bytes=remaining,
        used_ratio=used / total,
        next_reset=int(payload["data_next_reset"]) if payload.get("data_next_reset") else None,
    )


def choose_primary_node(used_ratio: float, threshold: float) -> str:
    """根据 BWG 已用比例选择 fallback 第一节点。

    当 BWG 到达阈值时，将 DMIT 放到 fallback 第一位，避免继续消耗 BWG 流量。
    下月 KiwiVM 流量重置后，`used_ratio` 会自然下降，下一次生成订阅会自动恢复 BWG 第一。
    """

    return "DMIT" if used_ratio >= threshold else "BWG"


def fetch_service_info(veid: str, api_key: str, timeout: int = 20) -> dict[str, Any]:
    """调用 Bandwagon/KiwiVM API 获取服务信息。

    API key 只通过内存和 HTTPS 请求传递，不写入仓库文件，也不会在 CLI 输出中打印。
    """

    query = urlencode({"veid": veid, "api_key": api_key})
    # KiwiVM API 对 Python 默认 urllib User-Agent 会返回 403。
    # 显式设置一个普通自动化脚本 UA，可以避免把可用 API key 误判为无效。
    request = Request(
        f"{API_ENDPOINT}?{query}",
        headers={"User-Agent": "homelab-rules/1.0"},
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="读取 Bandwagon/KiwiVM 月流量并给出主节点建议")
    parser.add_argument("--threshold", type=float, default=0.95, help="BWG 已用比例达到该阈值后优先 DMIT")
    parser.add_argument("--veid", default=os.environ.get("BWG_VEID"), help="Bandwagon VEID，也可用 BWG_VEID 环境变量")
    parser.add_argument("--api-key", default=os.environ.get("BWG_API_KEY"), help="Bandwagon API key，也可用 BWG_API_KEY 环境变量")
    args = parser.parse_args()

    if not args.veid or not args.api_key:
        raise SystemExit("缺少 BWG_VEID 或 BWG_API_KEY")

    usage = parse_usage(fetch_service_info(args.veid, args.api_key))
    primary = choose_primary_node(usage.used_ratio, args.threshold)
    print(
        json.dumps(
            {
                "used_ratio": usage.used_ratio,
                "used_bytes": usage.used_bytes,
                "total_bytes": usage.total_bytes,
                "remaining_bytes": usage.remaining_bytes,
                "next_reset": usage.next_reset,
                "primary": primary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
