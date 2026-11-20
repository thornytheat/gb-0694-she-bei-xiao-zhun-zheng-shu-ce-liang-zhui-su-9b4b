# 深度登记 设备校准证书与测量追溯

- 规模：中型
- 使用者与工作流：检验机构质量员，合并仪器使用与校准证书，裁决测量是否在有效可追溯链内。
- 核心规则：证书有效期与量程双约束；参考标准也须在校准时有效，证书撤销向下游传播并检测环。复检超差且调整合格的证书给出半开停用区间[上次校准生效日,恢复日)，区间内已出测量生成复测项目。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 证书接收 | 运行证书接收并复核证据 | `POST /api/m1`；`/work/1` | `app/modules/m1_receiving/rules.py` | `tests/test_m1.py` |
| M2 设备别名 | 运行设备别名并复核证据 | `POST /api/m2`；`/work/2` | `app/modules/m2_identity/rules.py` | `tests/test_m2.py` |
| M3 有效区间 | 运行有效区间并复核证据 | `POST /api/m3`；`/work/3` | `app/modules/m3_validity/rules.py` | `tests/test_m3.py` |
| M4 量程匹配 | 运行量程匹配并复核证据 | `POST /api/m4`；`/work/4` | `app/modules/m4_ranges/rules.py` | `tests/test_m4.py` |
| M5 溯源链路 | 运行溯源链路并复核证据 | `POST /api/m5`；`/work/5` | `app/modules/m5_trace/rules.py` | `tests/test_m5.py` |
| M6 测量裁决 | 运行测量裁决并复核证据 | `POST /api/m6`；`/work/6` | `app/modules/m6_verdict/rules.py` | `tests/test_m6.py` |
| M7 撤销复核 | 运行撤销复核并复核证据 | `POST /api/m7`；`/work/7` | `app/modules/m7_revocation/rules.py` | `tests/test_m7.py` |
| M8 超差处置 | 运行超差处置并复核证据 | `POST /api/m8`；`/work/8` | `app/modules/m8_disposition/rules.py` | `tests/test_m8.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现会怎样 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | 旧编码证书 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m1_receiving/rules.py` | `tests/test_m1.py::test_legacy_chinese` |
| TRAP-07 | 空值测量 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m2_identity/rules.py` | `tests/test_m2.py::test_missing_isolated` |
| TRAP-08 | 设备编码保形 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m2_identity/rules.py` | `tests/test_m2.py::test_device_code_preserved` |
| TRAP-14 | 定义冲突 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m2_identity/rules.py` | `tests/test_m2.py::test_conflict_certificate_flag` |
| TRAP-20 | 溯源依赖环 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m5_trace/rules.py` | `tests/test_m5.py::test_reference_cycle` |
| TRAP-22 | 设备别名 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m2_identity/rules.py` | `tests/test_m2.py::test_alias_order_independent` |
| TRAP-23 | 失效日边界 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m3_validity/rules.py` | `tests/test_m3.py::test_expiry_endpoint` |
| TRAP-25 | 多证书重叠 | 静默覆盖或误计 | 显式裁决并保留证据 | `app/modules/m3_validity/rules.py` | `tests/test_m3.py::test_overlapping_certificates` |
| TRAP-26 | 复检当天截断 | 漏掉调整前流出的测量 | 停用起点回退到上次校准生效日 | `app/modules/m8_disposition/rules.py` | `tests/test_m8.py::test_sample_retests_before_check_day` |
| TRAP-27 | 回退上次校准 | 调整后合格结果被一起作废 | 影响区间半开，恢复时点起不作废 | `app/modules/m8_disposition/rules.py` | `tests/test_m8.py::test_sample_post_recovery_kept` |
| TRAP-28 | 事件区间重叠 | 同一测量重复生成复测 | 按测量行号去重，事件证书并列 | `app/modules/m8_disposition/rules.py` | `tests/test_m8.py::test_overlapping_events_dedup` |
| TRAP-29 | 复检证书晚到 | 旧结论残留或复测重复 | 内容摘要定批次，重算换新幂等复用 | `app/store.py` | `tests/test_m8.py::test_late_certificate_invalidates_and_recomputes` |

## 对账规则

输入记录 = 采信记录 + 隔离记录 + 相同行重复。重复表头与空行单独记数。业务合计按阶段中的守恒或差值列复核。运行清单有原文SHA256、规则版本与耗时；相同规则版本下同文重复提交复用批次。

## 已知不覆盖

部署为本地单用户工具，不连接外部上游系统。CSV单文件5MB及一万条业务记录上限；不推断未提供的未知数据。
