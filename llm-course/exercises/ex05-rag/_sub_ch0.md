# 第 0 章 核心业务规则（权威定版 · 代码交叉验证）

> 本章规则源自系统开发中用户明确确认的业务决策，且后端代码实现与之一致（子代理从
> WasteMainServiceImpl / WasteDetailServiceImpl / OutboundMainServiceImpl 等类交叉验证）。
> **这些内容大模型不可能凭公开知识答对，是 RAG 验证效果最好的问题。**

## 0.1 单号（编号）规则

系统所有单据编号由 `NumberGenerator.generateNumber(prefix)` 统一生成，直接返回完整编号：

```
{前缀}-{yyyyMM}-{4位流水}
示例：DH-202608-0001、CK-202608-0250
```

### 规则细节（NumberGenerator.java）

- Redis Key：`material:number:{prefix}:{yyyyMM}`
- 通过 Redis INCR 原子递增，多实例不重复、严格升序
- 按前缀独立计数，自然月内递增；跨自然月从 0001 重新计数
- Key 过期时间 40 天，防止堆积
- 调用方不得再手动拼接前缀（历史上 20 处调用点统一改造过）
- 雪花 ID 用于物资数字身份：19 位雪花 ID 作 identityId / rfidCode

### 前缀用途速查表

| 前缀 | 单据/对象 | 来源类（方法） |
|---|---|---|
| DH | 到货单 | PurchaseMainServiceImpl.importPurchaseExcel / MelcPurchaseOrderServiceImpl |
| YS | 验收单主表 | AcceptMainServiceImpl.createAcceptMain |
| RK | 入库单（验收合格转/盘盈入库/退库转入库） | ConfirmMainServiceImpl / StockMainServiceImpl / ReturnMainServiceImpl |
| CK | 出库单/领用单（正常领用） | OutboundMainServiceImpl.createOutboundMain |
| CK | 盘亏出库单 | StockMainServiceImpl.updateApprovalStatusOut |
| CK | 报废处置出库单 | WasteDetailServiceImpl.createOutboundMain |
| PD | 盘点单 | StockMainServiceImpl.createStockMain |
| BF | 报废（废旧）单 | WasteMainServiceImpl.createWasteMain |
| HX | 直供核销申请单 | DirectSupplyServiceImpl.saveWriteoff |
| RT | 退库单 | ReturnMainServiceImpl.createReturnMain |
| YK | 移库单 | MoveboundMainServiceImpl.createMoveboundMain |
| GX | 共享编号 | MaterialSharedServiceImpl.createMaterialShared |
| WX | 维修（检修）单 | MaterialRepairServiceImpl.createMaterialRepair |
| AZ | 安装登记 | MaterialInstallServiceImpl |
| LSZCK | 临时资产库的仓库编码 | InboundMainServiceImpl.ensureTemporaryWarehouse |
| MRHJ | 默认货架的货架编码 | InboundMainServiceImpl.ensureDefaultShelf |
| Code | Excel 导入到货时自动补的物资编码 | PurchaseMainServiceImpl.importPurchaseExcel |

> ⚠️ 注意：报废出库、盘亏出库与正常领用**共用 CK 前缀**（不区分），只能靠出库主表 `types` 区分。
> 历史旧格式单号不迁移，仅新单据按此规范。

## 0.2 废旧出库（material_waste）—— 审批 ≠ 出库【关键规则】

- **审批通过只更新单据状态**（status=3、warehousedStatus=2），**不会**自动生成出库记录/出库清单
- 报废出库单（types=5）+ 出库明细 + 库存流水，在废旧台账执行**"处置"**时统一生成
- 处置生成出库的关键实现：`WasteDetailServiceImpl.updateWasteDetail → createOutboundMain`
- **关键状态值**：出库单须设 `status=2`（已出库）；库存流水 `outStatus=2`。
  若状态不对，前端"出库记录页"（只展示 status===2）与"出库清单页"（SQL 排除 outStatus=1）都查不到
- 反面教训：曾有"审批通过自动生成出库"的实现，后被推翻并还原——勿再实现审批时出库

## 0.3 在库物资报废数量锁定模型

核心表 `t_bound_main` 数量口径（多占用列模型）：

| 字段 | 含义 |
|---|---|
| inventoryQuantity | 账面库存数量 |
| availableQuantity | 可用数量（可领用） |
| wasteQuantity | 报废锁定量（专项用于报废流程） |
| shardQuantity | 共享占用 |
| moveQuantity | 移库占用 |

数量变动铁律：**移库、共享、报废都以 availableQuantity 划入对应占用列，回退时归还**。

报废流程规则：
- `waste-main/create` 创建报废单时：从 availableQuantity **划入** wasteQuantity（锁定）；可用不足时报错码 **1192**
- **处置时**：扣减 wasteQuantity **同时**扣减 inventoryQuantity（用户确认），**不动** availableQuantity
- **审批驳回 / 删除报废单**时：退回未处置明细的锁定量（只动 available/waste，不动 inventory）

## 0.4 领用出库两步扣减模型【关键规则】

- **建单（占用）**：创建出库单时扣 availableQuantity（占用可用量）
- **审批驳回**：归还占用的 availableQuantity
- **确认出库（confirmOutbound）**：才扣 inventoryQuantity 与金额，并置库存流水 outStatus=2

## 0.5 报废单前端提交约束

- 报废单前端（WasteMainForm.vue）**只提交 `sources`**（值形如"仓库名-货架名"的下拉 value），**从不提交 `lables`**
- 后端定位在库记录必须与处置路径 `createOutboundMain` 一致：**materialCode + 仓库名 + 货架名** 三要素；`lables` 仅作兜底
- 历史教训：曾按 lables 解析导致创建报废单报错 **1190**

## 0.6 硬件能力（hasHardware）链路

- 租户是否启用 RFID 等硬件能力，来自登录时 `get-permission-info` 返回的 `tenant.hasHardware`
- 后端 `TenantServiceImpl.getTenant` 直查库、无缓存；前端存 Pinia 会话内、不刷新
- 改库后需重新登录 / 硬刷新才生效
- 系统租户（id=1）受保护禁止页面修改，可手动改库绕过；
  但手动改 package_id 不会触发套餐菜单到 role_menu 同步，菜单权限需在角色管理手动分配

## 0.7 流程实例关联（t_instance_code.types）

| types | 业务 |
|---|---|
| 1 | 出库/领用审批（含临时领用） |
| 2 | 退库审批 |
| 3 | 报废审批 |
| 4 | 盘点差异入库（盘盈）审批 |
| 5 | 盘点差异出库（盘亏）审批 |
| 6 | 移库审批 |

> 例外：直供核销审批不写 t_instance_code，流程实例 ID 直接存 t_writeoff_main.process_instance_id。
