from scripts.generate_mihomo_router import build_router_config


def test_build_router_config_uses_only_fallback_and_match_rule():
    # 旁路由上的分流已经由 iKuai 完成，mihomo 只需要作为全局代理出口。
    # 因此配置中不应该出现公共 rule-providers，也不需要 Clash/Stash 客户端用的规则集。
    config = build_router_config(trojan_password="secret-password")

    assert [proxy["name"] for proxy in config["proxies"]] == ["BWG", "DMIT"]
    assert [group["name"] for group in config["proxy-groups"]] == ["代理"]
    assert config["proxy-groups"][0]["type"] == "fallback"
    assert config["proxy-groups"][0]["proxies"] == ["BWG", "DMIT"]
    assert config["rules"] == ["MATCH,代理"]
    assert "rule-providers" not in config


def test_build_router_config_keeps_dns_fake_ip_filter_for_irispeko_domain():
    # 节点域名和自有内网服务域名不能被 fake-ip 化，否则节点启动会陷入解析循环。
    config = build_router_config(trojan_password="secret-password")

    assert "+.irispeko.com" in config["dns"]["fake-ip-filter"]
    assert config["dns"]["proxy-server-nameserver"]
    assert all("#DIRECT" in item for item in config["dns"]["proxy-server-nameserver"])
