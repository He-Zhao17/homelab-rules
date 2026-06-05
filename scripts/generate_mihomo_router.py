from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import yaml


def trojan_proxy(name: str, server: str, sni: str, password: str) -> dict[str, Any]:
    """生成旁路由使用的 Trojan 节点。

    旁路由只负责出站代理，不暴露给手机端选择，因此节点名保持短且稳定。
    """

    return {
        "name": name,
        "type": "trojan",
        "server": server,
        "port": 443,
        "password": password,
        "sni": sni,
        "udp": True,
        "skip-cert-verify": False,
    }


def build_router_config(trojan_password: str) -> dict[str, Any]:
    """构建旁路由专用 mihomo 配置。

    iKuai 已经完成域名/IP 分流，送到旁路由的流量都应该走代理。
    所以这里不引入任何 rule-provider，只保留 `MATCH,代理` 和 BWG -> DMIT 的 fallback。
    """

    return {
        "mode": "rule",
        "interface-name": "eth0",
        "allow-lan": True,
        "bind-address": "*",
        "log-level": "info",
        # 继续保留内网管理 API，AdGuardHome 健康检查脚本会用它判断代理是否可用。
        "external-controller": "192.168.50.3:9090",
        "secret": "f6a7dd453c038d4fdb0f608c2d27a6900291a73cc05c7ac5",
        "tun": {
            "enable": True,
            "stack": "system",
            "auto-route": True,
            "auto-detect-interface": False,
            "dns-hijack": [
                "any:53",
                "tcp://any:53",
            ],
        },
        "sniffer": {
            "enable": True,
            "force-dns-mapping": True,
            "parse-pure-ip": True,
            "override-destination": True,
            "sniff": {
                "tls": {"ports": [443, 8443]},
                "http": {"ports": [80, "8080-8880"]},
                "quic": {"ports": [443, 8443]},
            },
        },
        "dns": {
            "enable": True,
            "listen": "0.0.0.0:1053",
            "ipv6": False,
            "enhanced-mode": "fake-ip",
            "fake-ip-range": "198.18.0.1/16",
            "fake-ip-filter": [
                "*.lan",
                "*.local",
                "localhost.ptlogin2.qq.com",
                "+.irispeko.com",
            ],
            # 节点域名必须用真实 DNS 直连解析，避免代理未建立前出现 DNS/代理循环依赖。
            "default-nameserver": [
                "https://1.1.1.1/dns-query#DIRECT",
                "https://223.5.5.5/dns-query#DIRECT",
            ],
            "proxy-server-nameserver": [
                "https://1.1.1.1/dns-query#DIRECT",
                "https://223.5.5.5/dns-query#DIRECT",
            ],
            # 普通域名 DNS 查询也走 fallback 组；若 BWG 暂停，健康检查会切到 DMIT。
            "nameserver": [
                "https://1.1.1.1/dns-query#代理",
                "https://1.0.0.1/dns-query#代理",
            ],
        },
        "proxies": [
            trojan_proxy("BWG", "bwg.irispeko.com", "bwg.irispeko.com", trojan_password),
            trojan_proxy("DMIT", "dmit.irispeko.com", "dmit.irispeko.com", trojan_password),
        ],
        "proxy-groups": [
            {
                "name": "代理",
                "type": "fallback",
                "proxies": ["BWG", "DMIT"],
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300,
                "timeout": 5000,
                "lazy": True,
            }
        ],
        "rules": [
            "MATCH,代理",
        ],
    }


def write_config(config: dict[str, Any], output: Path) -> None:
    """写出旁路由 mihomo YAML。

    文件包含真实 Trojan 密码，默认应写到被 `.gitignore` 忽略的 `build/` 目录。
    """

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="生成旁路由专用 mihomo 配置")
    parser.add_argument("--output", required=True, type=Path, help="输出 YAML 路径，建议放在 build/ 下")
    parser.add_argument("--trojan-password", default=os.environ.get("TROJAN_PASSWORD"), help="Trojan 密码，也可用 TROJAN_PASSWORD 环境变量")
    args = parser.parse_args()

    if not args.trojan_password:
        raise SystemExit("缺少 Trojan 密码，请设置 TROJAN_PASSWORD 或传入 --trojan-password")

    write_config(build_router_config(args.trojan_password), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
