from scripts.bwg_traffic import choose_primary_node, parse_usage


def test_parse_usage_calculates_ratio_and_remaining_bytes():
    # Bandwagon/KiwiVM 的 getServiceInfo 返回字节级用量。
    # 这里用最小字段集验证我们只依赖流量判断需要的字段，避免把 VPS 其他信息耦合进发布流程。
    usage = parse_usage(
        {
            "data_counter": 95,
            "plan_monthly_data": 100,
            "data_next_reset": 1234567890,
        }
    )

    assert usage.used_bytes == 95
    assert usage.total_bytes == 100
    assert usage.remaining_bytes == 5
    assert usage.used_ratio == 0.95
    assert usage.next_reset == 1234567890


def test_choose_primary_node_switches_to_dmit_at_threshold_and_recovers_after_reset():
    # 发布订阅时只需要调整 fallback 顺序，不需要改客户端策略组。
    # 当 BWG 用量超过阈值时 DMIT 排第一；下月重置后比例下降，下一次生成自然恢复 BWG 第一。
    assert choose_primary_node(used_ratio=0.95, threshold=0.95) == "DMIT"
    assert choose_primary_node(used_ratio=0.10, threshold=0.95) == "BWG"
