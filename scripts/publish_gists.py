from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess

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
    parser.add_argument("--dry-run", action="store_true", help="只生成本地文件，不更新 Gist")
    parser.add_argument("--trojan-password", default=os.environ.get("TROJAN_PASSWORD"), help="Trojan 密码，也可用 TROJAN_PASSWORD 环境变量")
    args = parser.parse_args()

    if not args.trojan_password:
        raise SystemExit("缺少 Trojan 密码，请设置 TROJAN_PASSWORD 或传入 --trojan-password")

    # BWG 和 DMIT 都采用超流量暂停的服务形态，节点不可用时由 fallback 健康检查自然切换。
    # 因此发布订阅不再依赖服务商流量 API，固定保持 BWG 优先、DMIT 备用。
    primary = "BWG"
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
