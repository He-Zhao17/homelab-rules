from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

from scripts.bwg_traffic import choose_primary_node, fetch_service_info, parse_usage
from scripts.generate_clash import build_config, read_domain_list, write_config, REPO_ROOT


TARGET_GISTS = [
    {
        "gist_id": "0c6bb76d69400f2ea96b5adb0b620679",
        "file_name": "JP_Tokyo.yaml",
    },
    {
        "gist_id": "8c5d980296fc6cf8ae8d9281138e4b31",
        "file_name": "Bobby.yaml",
    },
]


def decide_primary_node(threshold: float) -> str:
    """根据 BWG API 决定生成订阅时的 fallback 第一节点。

    如果本机没有配置 BWG API 凭据，则保守使用 BWG 第一，避免发布流程因为缺少可选监控能力而失败。
    """

    veid = os.environ.get("BWG_VEID")
    api_key = os.environ.get("BWG_API_KEY")
    if not veid or not api_key:
        return "BWG"

    try:
        usage = parse_usage(fetch_service_info(veid, api_key))
    except Exception as exc:
        # BWG API 只影响 fallback 第一节点排序，不应该影响订阅发布本身。
        # 这里不打印 API key，只输出异常类型和消息，方便排查 403、超时等问题。
        print(f"BWG API 不可用，默认使用 BWG 第一: {type(exc).__name__}: {exc}", file=sys.stderr)
        return "BWG"
    return choose_primary_node(usage.used_ratio, threshold)


def publish_file(gist_id: str, file_name: str, path: Path) -> None:
    """用 `gh gist edit` 替换已有 Gist 文件内容。

    这里不删除、不重建 Gist，只编辑已有文件，保证已经分发出去的订阅地址继续可用。
    """

    subprocess.run(
        ["gh", "gist", "edit", gist_id, "--filename", file_name, str(path)],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="生成订阅并更新现有 Gist 文件")
    parser.add_argument("--threshold", type=float, default=0.95, help="BWG 用量达到该比例后优先 DMIT")
    parser.add_argument("--dry-run", action="store_true", help="只生成本地文件，不更新 Gist")
    parser.add_argument("--trojan-password", default=os.environ.get("TROJAN_PASSWORD"), help="Trojan 密码，也可用 TROJAN_PASSWORD 环境变量")
    args = parser.parse_args()

    if not args.trojan_password:
        raise SystemExit("缺少 Trojan 密码，请设置 TROJAN_PASSWORD 或传入 --trojan-password")

    primary = decide_primary_node(args.threshold)
    nodes = [
        {"name": "BWG", "server": "bwg.irispeko.com", "sni": "bwg.irispeko.com"},
        {"name": "DMIT", "server": "dmit.irispeko.com", "sni": "dmit.irispeko.com"},
    ]
    config = build_config(
        trojan_password=args.trojan_password,
        nodes=nodes,
        primary=primary,
        my_proxy_domains=read_domain_list(REPO_ROOT / "lists/proxy-domain.list"),
        my_direct_domains=read_domain_list(REPO_ROOT / "lists/direct-domain.list"),
    )

    for target in TARGET_GISTS:
        output = REPO_ROOT / "build" / target["file_name"]
        write_config(config, output)
        if not args.dry_run:
            publish_file(target["gist_id"], target["file_name"], output)

    print(f"primary={primary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
