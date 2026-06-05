import yaml

from scripts.generate_clash import build_config, domain_rules_from_entries


def test_domain_rules_from_entries_normalizes_wildcards_and_suffixes():
    # 这里验证自维护列表的最小解析规则：
    # 1. 普通域名按 DOMAIN-SUFFIX 生成，便于同时命中自身和子域名。
    # 2. `*.` 和 `+.` 这两种常见通配写法会被折叠成 Clash 可识别的后缀规则。
    # 3. 空行和注释不进入最终订阅，避免用户维护列表时的说明文字污染规则。
    rules = domain_rules_from_entries(
        [
            "example.com",
            "*.openai.com",
            "+.google.com",
            "",
            "# comment",
        ],
        "代理",
    )

    assert rules == [
        "DOMAIN-SUFFIX,example.com,代理",
        "DOMAIN-SUFFIX,openai.com,代理",
        "DOMAIN-SUFFIX,google.com,代理",
    ]


def test_build_config_keeps_minimal_proxy_groups_and_rule_targets():
    # 这里固定最终订阅的核心形态：客户端只需要看到“代理”和“自动选择”两个自定义策略组。
    # 具体服务分类全部落到 DIRECT 或“代理”，不要再暴露 Apple、Media、Final 等多余组。
    config = build_config(
        trojan_password="secret-password",
        nodes=[
            {"name": "BWG", "server": "bwg.irispeko.com", "sni": "bwg.irispeko.com"},
            {"name": "DMIT", "server": "dmit.irispeko.com", "sni": "dmit.irispeko.com"},
        ],
        my_proxy_domains=["chatgpt.com"],
        my_direct_domains=["kiwivm.64clouds.com"],
    )

    assert [group["name"] for group in config["proxy-groups"]] == ["代理", "自动选择"]
    assert config["proxy-groups"][0]["proxies"] == ["自动选择", "BWG", "DMIT", "DIRECT"]
    assert config["proxy-groups"][1]["type"] == "fallback"
    assert config["proxy-groups"][1]["proxies"] == ["BWG", "DMIT"]

    assert config["rules"][:2] == [
        "DOMAIN-SUFFIX,kiwivm.64clouds.com,DIRECT",
        "DOMAIN-SUFFIX,chatgpt.com,代理",
    ]
    assert config["rules"][-1] == "MATCH,代理"
    assert "Final" not in yaml.safe_dump(config, allow_unicode=True)
    assert "GlobalMedia" not in yaml.safe_dump(config, allow_unicode=True)


def test_build_config_uses_clash_rule_providers_for_public_domain_and_ip_sources():
    # 公共大规则通过 rule-providers 拉取，不把几千行域名或 IP 段塞进主 YAML。
    # 这样 Stash/Clash/Mihomo 可以定期刷新规则集，也方便我们只维护自己的覆盖列表。
    config = build_config(
        trojan_password="secret-password",
        nodes=[
            {"name": "BWG", "server": "bwg.irispeko.com", "sni": "bwg.irispeko.com"},
            {"name": "DMIT", "server": "dmit.irispeko.com", "sni": "dmit.irispeko.com"},
        ],
        my_proxy_domains=[],
        my_direct_domains=[],
    )

    providers = config["rule-providers"]
    assert providers["public-proxy"]["behavior"] == "domain"
    assert providers["public-direct"]["behavior"] == "domain"
    assert providers["public-private"]["behavior"] == "domain"
    assert providers["public-lancidr"]["behavior"] == "ipcidr"
    assert providers["public-cncidr"]["behavior"] == "ipcidr"
    assert providers["public-telegramcidr"]["behavior"] == "ipcidr"

    assert "RULE-SET,public-telegramcidr,代理" in config["rules"]
    assert "RULE-SET,public-cncidr,DIRECT" in config["rules"]
    assert "GEOIP,CN,DIRECT" in config["rules"]


def test_build_config_defaults_to_bwg_first_without_traffic_api():
    # BWG/DMIT 都是超流量后暂停的服务形态，客户端 fallback 自然切换即可。
    # 因此生成器不再读取服务商流量 API，也不按百分比提前调整节点顺序。
    config = build_config(
        trojan_password="secret-password",
        nodes=[
            {"name": "BWG", "server": "bwg.irispeko.com", "sni": "bwg.irispeko.com"},
            {"name": "DMIT", "server": "dmit.irispeko.com", "sni": "dmit.irispeko.com"},
        ],
        my_proxy_domains=[],
        my_direct_domains=[],
    )

    assert config["proxy-groups"][1]["proxies"] == ["BWG", "DMIT"]
