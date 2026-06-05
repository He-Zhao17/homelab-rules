# homelab-rules

这个仓库是家庭网络分流规则的事实源。后续 iKuai、Mihomo/Clash 订阅、AdGuardHome 规则都应该从这里或这里记录的公共上游生成，避免多处手工维护后规则漂移。

## 目录说明

- `lists/proxy-domain.list`：自维护的强制代理/旁路域名列表，第一版由 iKuai 当前 `PassWall` 和 `IKUAI_BYPASS_private_bypass` 规则迁移而来。
- `lists/direct-domain.list`：自维护的强制直连域名列表，第一版由 iKuai 当前 `direct` 和 `IKUAI_BYPASS_private_direct` 规则迁移而来。
- `sources.yml`：公共上游规则和本仓库自维护列表的来源记录。后续生成脚本应该读取这个文件，而不是反向读取 iKuai 的历史表。

## 维护原则

1. 公共大规则不复制进仓库，只记录上游地址，例如 GFW 域名列表、国内 IP、Telegram IP、Google IP。
2. 自己要覆盖的域名放在 `lists/` 目录，后续 iKuai-bypass 和 Mihomo/Gist 生成器都消费同一份列表。
3. iKuai 里历史残留的 `PassWall`、`direct`、`CN` 等规则不再作为长期事实源；需要保留的内容应迁移进本仓库。
4. `.list` 文件保持纯域名/标记内容，避免注释影响 iKuai-bypass 或其他解析器。

## Raw URL

```text
https://raw.githubusercontent.com/He-Zhao17/homelab-rules/main/lists/proxy-domain.list
https://raw.githubusercontent.com/He-Zhao17/homelab-rules/main/lists/direct-domain.list
```
