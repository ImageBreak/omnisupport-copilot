# 验收口径与风险边界
## 指标的精确口径
+ 分子: status为resolved的工单数
+ 分母: 总工单数
+ 维度: metric_date * product_line * priority * org_id * category

## PII分级
+ 等级: none
+ 理由: 这是一个纯粹的数值，不包含任何个人的身份信息

## 可查角色/HITL节点
+ 可查角色: support_ops / instructor / admin
+ 需要人工介入的场景: 得到的值不在0～1之间 

## 不可执行红线
+ Agent 不允许直接拼 SQL 访问原始工单表