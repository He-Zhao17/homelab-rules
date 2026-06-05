from __future__ import annotations

import argparse
from pathlib import Path
import os
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]

# 这里使用 Loyalsoldier/clash-rules 的 release 分支作为公共规则集来源。
# 这些文件已经是 Clash rule-provider 可消费的 `payload:` YAML 格式。
CLASH_RULES_BASE = "https://raw.githubusercontent.com/Loyalsoldier/clash-rules/release"


def read_domain_list(path: Path) -> list[str]:
    """读取一行一个域名的自维护列表。

    列表文件面向人工维护，因此允许空行和 `#` 注释；生成订阅时会过滤掉这些辅助内容。
    """

    entries: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def normalize_domain_entry(entry: str) -> str:
    """把常见通配域名写法归一化为 Clash DOMAIN-SUFFIX 可用的后缀。

    `*.example.com` 和 `+.example.com` 都表达“该域名及子域名”，在 Clash 里用
    `DOMAIN-SUFFIX,example.com,...` 更直接，也能被 Stash/Clash/Mihomo 共同识别。
    """

    domain = entry.strip()
    if domain.startswith("*.") or domain.startswith("+."):
        domain = domain[2:]
    return domain.strip(".")


def domain_rules_from_entries(entries: Iterable[str], target: str) -> list[str]:
    """把自维护域名转换成内联规则。

    自维护列表体量很小，直接内联进主 YAML 可以确保它们优先于公共规则集生效。
    """

    rules: list[str] = []
    for entry in entries:
        entry = entry.strip()
        if not entry or entry.startswith("#"):
            continue
        rules.append(f"DOMAIN-SUFFIX,{normalize_domain_entry(entry)},{target}")
    return rules


def trojan_proxy(name: str, server: str, sni: str, password: str) -> dict[str, Any]:
    """生成 Trojan 节点配置。

    两个节点参数保持一致，仅 server/SNI 不同；密码只在运行时传入，公开仓库不保存真实值。
    """

    return {
        "name": name,
        "type": "trojan",
        "server": server,
        "port": 443,
        "password": password,
        "sni": sni,
        "skip-cert-verify": False,
        "udp": True,
    }


def provider(name: str, behavior: str, filename: str) -> dict[str, Any]:
    """生成公共 rule-provider 配置。

    `path` 使用每个 provider 独立文件，便于客户端缓存和定期刷新；`interval` 设为一天。
    """

    return {
        "type": "http",
        "behavior": behavior,
        "url": f"{CLASH_RULES_BASE}/{filename}",
        "path": f"./ruleset/{name}.yaml",
        "interval": 86400,
    }


def ordered_nodes(nodes: list[dict[str, str]], primary: str) -> list[dict[str, str]]:
    """按流量策略调整 fallback 顺序。

    只调整自动选择组的节点顺序，不改变节点定义本身。手动选择组仍然保留所有节点。
    """

    by_name = {node["name"]: node for node in nodes}
    if primary not in by_name:
        raise ValueError(f"未知主节点: {primary}")
    return [by_name[primary], *[node for node in nodes if node["name"] != primary]]


def build_config(
    *,
    trojan_password: str,
    nodes: list[dict[str, str]],
    my_proxy_domains: list[str],
    my_direct_domains: list[str],
    primary: str = "BWG",
) -> dict[str, Any]:
    """构建极简 Clash/Stash/Mihomo 订阅。

    设计目标是让客户端只暴露一个“代理”选择组和一个“自动选择”fallback 组。
    Apple、Google、媒体、Final 等服务分类只存在于规则数据里，不再变成用户要手动选择的策略组。
    """

    fallback_nodes = ordered_nodes(nodes, primary)
    proxy_names = [node["name"] for node in nodes]

    config: dict[str, Any] = {
        "port": 7890,
        "socks-port": 7891,
        "allow-lan": True,
        "mode": "Rule",
        "log-level": "info",
        "proxies": [
            trojan_proxy(node["name"], node["server"], node["sni"], trojan_password)
            for node in nodes
        ],
        "proxy-groups": [
            {
                "name": "代理",
                "type": "select",
                "proxies": ["自动选择", *proxy_names, "DIRECT"],
            },
            {
                "name": "自动选择",
                "type": "fallback",
                "proxies": [node["name"] for node in fallback_nodes],
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300,
                "lazy": True,
            },
        ],
        "rule-providers": {
            "public-private": provider("public-private", "domain", "private.txt"),
            "public-direct": provider("public-direct", "domain", "direct.txt"),
            "public-proxy": provider("public-proxy", "domain", "proxy.txt"),
            "public-lancidr": provider("public-lancidr", "ipcidr", "lancidr.txt"),
            "public-cncidr": provider("public-cncidr", "ipcidr", "cncidr.txt"),
            "public-telegramcidr": provider("public-telegramcidr", "ipcidr", "telegramcidr.txt"),
        },
    }

    rules: list[str] = []
    # 自维护直连/代理规则放在最前面，保证你的覆盖列表优先级最高。
    rules.extend(domain_rules_from_entries(my_direct_domains, "DIRECT"))
    rules.extend(domain_rules_from_entries(my_proxy_domains, "代理"))
    # 局域网和保留域名/IP 必须直连，避免家庭内网和私有地址误走代理。
    rules.extend(
        [
            "RULE-SET,public-private,DIRECT",
            "RULE-SET,public-lancidr,DIRECT",
            # Telegram 有大量 IP-only 连接，单靠域名规则覆盖不完整。
            "RULE-SET,public-telegramcidr,代理",
            # 公共代理域名在公共直连之前，避免需要代理的域名被后面的直连大表吞掉。
            "RULE-SET,public-proxy,代理",
            "RULE-SET,public-direct,DIRECT",
            "RULE-SET,public-cncidr,DIRECT",
            "GEOIP,CN,DIRECT",
            "MATCH,代理",
        ]
    )
    config["rules"] = rules
    return config


def write_config(config: dict[str, Any], output: Path) -> None:
    """写出 YAML 文件。

    生成产物可能包含真实节点密码，因此默认写到被 `.gitignore` 忽略的 `build/` 目录。
    """

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="生成极简 Clash/Stash/Mihomo 订阅 YAML")
    parser.add_argument("--output", required=True, type=Path, help="输出 YAML 文件路径，建议放在 build/ 下")
    parser.add_argument("--primary", choices=["BWG", "DMIT"], default=os.environ.get("PRIMARY_NODE", "BWG"))
    parser.add_argument("--trojan-password", default=os.environ.get("TROJAN_PASSWORD"), help="Trojan 密码，也可用 TROJAN_PASSWORD 环境变量")
    args = parser.parse_args()

    if not args.trojan_password:
        raise SystemExit("缺少 Trojan 密码，请设置 TROJAN_PASSWORD 或传入 --trojan-password")

    nodes = [
        {"name": "BWG", "server": "bwg.irispeko.com", "sni": "bwg.irispeko.com"},
        {"name": "DMIT", "server": "dmit.irispeko.com", "sni": "dmit.irispeko.com"},
    ]
    config = build_config(
        trojan_password=args.trojan_password,
        nodes=nodes,
        primary=args.primary,
        my_proxy_domains=read_domain_list(REPO_ROOT / "lists/proxy-domain.list"),
        my_direct_domains=read_domain_list(REPO_ROOT / "lists/direct-domain.list"),
    )
    write_config(config, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
