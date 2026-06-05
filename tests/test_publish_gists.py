from scripts.publish_gists import decide_primary_node


def test_decide_primary_node_defaults_to_bwg_when_api_credentials_are_missing(monkeypatch):
    # BWG 流量 API 是增强能力，不应该成为订阅发布的硬依赖。
    # 没有配置 VEID/API_KEY 时，发布流程继续使用 BWG 第一，保证订阅仍可生成。
    monkeypatch.delenv("BWG_VEID", raising=False)
    monkeypatch.delenv("BWG_API_KEY", raising=False)

    assert decide_primary_node(0.95) == "BWG"


def test_decide_primary_node_defaults_to_bwg_when_api_request_fails(monkeypatch):
    # API 临时 403、超时或服务端异常时，发布流程应该降级，而不是中断 Gist 更新。
    monkeypatch.setenv("BWG_VEID", "dummy-veid")
    monkeypatch.setenv("BWG_API_KEY", "dummy-key")

    def raise_api_error(*_args, **_kwargs):
        raise RuntimeError("api unavailable")

    monkeypatch.setattr("scripts.publish_gists.fetch_service_info", raise_api_error)

    assert decide_primary_node(0.95) == "BWG"
