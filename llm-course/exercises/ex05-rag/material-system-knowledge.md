# 物资仓储管理系统 · 系统知识总结（完整版）

> **用途**：本文件是物资系统的业务知识总览，用作 **RAG 知识问答数据源**（文档切块→向量化→检索问答），也可作为新同学上手文档。
> **来源**：后端代码（echo-cloud material 模块精读）+ 前端代码（materials_web 精读）+ 数据库 DO/表结构（73 张表）+ 历史业务决策。
> **文档结构**：第 0 章为权威业务规则；第 1~5 章为后端业务知识；第 6 章为数据库结构；第 7 章为前端功能结构。

---
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


---

## 第一部分：后端业务知识（第 1~5 章）

> 本文档由代码抽样精读归纳生成，每个结论均标注来源类名（括号内），未确认的信息一律不写。
>
> 代码根目录：
> `echo-module-material/echo-module-material-server/src/main/java/cn/echo/cloud/module/material`

---

## 1. 系统定位与技术栈

### 1.1 系统定位

这是一套面向电网/发电等企业的物资仓储管理系统（多租户 SaaS）。

业务范围覆盖采购到货、验收确认、入库、在库台账、领用出库、退库、移库、报废（废旧）处置、盘点、维修（检修）、共享与调拨、直接供货与核销等全链路。

系统集成 BPM 审批流（Flowable/yudao-bpm）、RFID 数字身份、无人值守仓库（IoT、MQTT、人脸识别预约）与区块链存证。

### 1.2 技术栈与模块划分

项目代号 echo-cloud，基于 yudao（芋道）框架二次开发，后端技术栈：

- Spring Boot / Spring Cloud Alibaba 微服务。
- MyBatis-Plus（DO + Mapper，BaseDO/TenantBaseDO 审计与租户字段）。
- Redis（单号流水、RFID 盘点标签缓存、盘点导入缓存）。
- 多租户：业务表继承 TenantBaseDO，按租户表级隔离（TenantContextHolder）。
- BPM 审批通过 RPC 调用 `cn.echo.cloud.module.bpm.api.task.BpmProcessInstanceApi`。
- 异步执行常用 @Async + CompletableFuture（出库上链等）。

仓库顶层模块（从代码仓库根目录观察）：

| 模块 | 职责 |
|---|---|
| echo-gateway | 网关 |
| echo-module-system | 用户、部门、租户等基础能力 |
| echo-module-bpm | 审批流程（被 material 调用） |
| echo-module-infra | 基础设施 |
| echo-module-material | 本业务模块，内部拆 -api（常量/DTO）与 -server（实现） |
| echo-framework / echo-dependencies | 框架公共代码与依赖管理 |

material-server 内的包划分即业务域划分：

- controller/admin、controller/app：管理端与 App 端接口。
- service/xxx：各业务 ServiceImpl。
- domain/xxx：DO、VO、PageReqVO 等。
- mapper、convert（MapStruct）、config（NumberGenerator 等）。
- util/mqtt、util（BlockchainUtil、RedisService）。

业务单据表命名规律：主表 t_xxx_main、明细 t_xxx_detail。

库存按「物资编码 + 仓库 + 货架」三元组定位一条在库主表记录。

---

## 2. 单据类型与编号规则

### 2.1 单号格式

单号统一由 NumberGenerator.generateNumber(prefix) 生成（NumberGenerator.java）。

格式：前缀-yyyyMM-4位流水号，例如：DH-202608-0001、CK-202608-0250。

流水规则：

- Redis Key：material:number:{前缀}:{yyyyMM}。
- 通过 INCR 原子递增，多实例不重复、严格升序。
- 按前缀各自独立计数，自然月内递增。
- 跨自然月从 0001 重新计数。
- Key 过期时间 40 天，防止堆积。

### 2.2 前缀用途表

以下前缀全部来自代码中 generateNumber("XX") 的调用点：

| 前缀 | 单据/对象 | 来源类（方法） |
|---|---|---|
| DH | 到货单 | PurchaseMainServiceImpl.importPurchaseExcel |
| DH | 采购订单提取生成的到货单 | MelcPurchaseOrderServiceImpl |
| YS | 验收单主表 | AcceptMainServiceImpl.createAcceptMain |
| RK | 入库单（验收合格转） | ConfirmMainServiceImpl.updateConfirmMainInfo |
| RK | 入库单（盘盈入库） | StockMainServiceImpl.updateApprovalStatus |
| RK | 入库单（退库转入库） | ReturnMainServiceImpl.createInbound |
| CK | 出库单/领用单 | OutboundMainServiceImpl.createOutboundMain |
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

注意：报废出库、盘亏出库与正常领用共用 CK 前缀（不区分），只能靠出库主表 types 区分。

补充：雪花 ID 用于物资数字身份：

- generateIdentityId()：19 位雪花 ID，作 identityId。
- getStingCode()：雪花 ID 字符串，作 rfidCode。
- 来源：NumberGenerator.java、InboundMainServiceImpl。

### 2.3 流程实例关联表 t_instance_code 的 types

t_instance_code 保存 BPM 流程实例 ID 与业务单据编号的关系。

| types | 业务 | 发起审批的类 |
|---|---|---|
| 1 | 出库/领用审批（含临时领用） | OutboundMainServiceImpl.initiateApproval / initiateTemporaryApproval |
| 2 | 退库审批 | ReturnMainServiceImpl.initiateApproval |
| 3 | 报废审批 | WasteMainServiceImpl.initiateApproval |
| 4 | 盘点差异入库（盘盈）审批 | StockMainServiceImpl.initiateApproval |
| 5 | 盘点差异出库（盘亏）审批 | StockMainServiceImpl.initiateApprovalOut |
| 6 | 移库审批 | MoveboundMainServiceImpl.initiateApproval |

例外：直供核销审批不写 t_instance_code。

核销审批的流程实例 ID 直接保存在 t_writeoff_main.process_instance_id。

（来源：DirectSupplyServiceImpl.startApproval）

---

## 3. 核心业务流程

### 3.1 主链路总览

主链路为：采购到货(DH) → 验收(YS) → 验收确认 → 入库(RK) → 在库(t_bound_main) → 领用出库(CK)。

全程通过 trackingId 串联同一采购链路上的多张单据，驱动外部进度系统回写。

### 3.2 到货（PurchaseMainServiceImpl）

#### 3.2.1 建单方式

- Excel 模板导入批量建单（importPurchaseExcel），从第二行读取计划名称、合同名称、合同编号等合并单元格。
- 从采购订单提取生成到货单（MelcPurchaseOrderServiceImpl）。
- 导入的到货明细无物资编码时自动生成 Code 前缀物资编码。

#### 3.2.2 表与数量字段

主表 t_purchase_main 保存计划、合同、供应商、金额汇总；明细 t_purchase_detail 保存行级物资。

明细关键数量字段：

- purchaseQuantity：采购数量。
- pendingQuantity：未到货数量，导入时初始化为采购数量。
- receivedQuantity：累计到货（已验收）数量，随验收动作累加。
- 价格字段：price 含税单价、priceExcludeTax 不含税单价、totalPrice 含税总价。
- 其他：taxRate 税率、supplier 供货单位、demandDepartment 需求部门、expensesListed 费用列支、materialCode、warehouseName/shelvesName。

#### 3.2.3 到货单状态

到货主表 status 取值（PurchaseMainDO 注释：1未到货 2部分到货 3全部到货）。

状态更新发生在验收动作里（AcceptMainServiceImpl.createAcceptMain）：

- 汇总该到货单所有明细剩余 pendingQuantity。
- 剩余 > 0：到货单 status=2（部分到货）。
- 剩余 <= 0：到货单 status=3（全部到货）。

待办计数：getNoPurchaseCount 统计 status=1（未到货）的到货单数量。

### 3.3 验收（AcceptMainServiceImpl）

#### 3.3.1 发起验收（createAcceptMain）

- 入参为到货主表 ID + 勾选的到货明细（含本次验收数量 arrivalQty）。
- 校验到货主表存在（1101）、验收明细非空（1104）。
- 到货明细转验收明细 AcceptDetailDO（含仓库名、货架名、仓库类别回填）。
- 回写到货明细：receivedQuantity 累加本次验收数，pendingQuantity 扣减本次验收数。
- 按剩余未到货量更新到货主表状态（见 3.2.3）。
- 生成验收单 YS 编号、验收时间、验收地点。
- 汇总本次验收物资的含税/不含税总价。
- 触发进度阶段 12-1（发起验收）。

#### 3.3.2 验收类型与状态

验收主表 acceptType（AcceptMainDO 注释）：

- 1：仓管直接验收。
- 2：远程验收。
- 3：三方到场直接验收。

验收主表 status（AcceptMainDO 注释：1待验收 2验收中 3已验收 4已拒绝）。

- 重新验收接口会把验收单置 status=2（验收中），并把对应确认单 status 重置为 1（AcceptMainServiceImpl.getAcceptMain(reqVO)）。

#### 3.3.3 验收提交与确认单生成

updateAcceptMain（验收信息更新/提交）：

- acceptType=1：仓管部门校验，warehouseCheckerId 取登录人部门。
- acceptType=2（远程）：可更新验收明细图片地址等。
- 更新验收主表后，自动把验收数据转换为一张验收确认单 t_confirm_main（status=1）并复制明细到 t_confirm_detail。

### 3.4 验收确认（ConfirmMainServiceImpl）

#### 3.4.1 状态机

验收确认主表 status 取值（由代码赋值逻辑归纳）：

| status | 含义 |
|---|---|
| 1 | 待确认（初始，刚由验收生成） |
| 2 | 需求部门已审核（等另一方/仓管） |
| 3 | 技术部门已审核（等另一方/仓管） |
| 4 | 需求+技术+仓管三方确认齐 / 仓管直接验收通过 |
| 5 | 填写合格数量等验收结果，确认完成（同时自动生成入库单） |
| 6 | 拒绝验收（验收不通过） |

三方确认顺序不定，谁先审核就先把 status 置 2 或 3。

- isDemandDept 审核通过 → 若技术部门还没审，置 status=2。
- isTechDept 审核通过 → 若需求部门还没审，置 status=3。
- 两个部门都审过之后由仓管部门确认 → status=4（验收通过）。

拒绝路径：

- status=6 时校验当前用户部门属于三个验收部门之一（acceptType=1 只允许仓管部门）。
- 拒绝后同步验收主表 status=4（已拒绝）。

#### 3.4.2 部门一致性硬校验

校验规则与错误码：

- 仓管直接验收（acceptType=1）：登录部门必须等于 warehouseCheckerId，否则 1152/1157。
- 远程/三方（acceptType=2/3）：登录部门必须是需求/技术/仓管之一，否则 1157。
- 需求部门先审时必须是需求部门账号，否则 1151/1153。
- 技术部门先审时必须是技术部门账号，否则 1152/1153。
- 三方已齐由仓管确认时必须是仓管部门账号，否则 1150。

各验收人字段：demandChecker/TechChecker/WarehouseChecker + 各自 UserId + 各自 CheckTime。

#### 3.4.3 验收结果填写（updateConfirmMainInfo）

明细验收结果 acceptResult 由 到货数量-合格数量 计算：

- 差值=0：acceptResult=1（全部合格）。
- 差值=到货数量：acceptResult=2（全部不合格）。
- 差值在中间：acceptResult=3（部分合格）。

主表 acceptResult：

- 明细中出现 2 或 3 → 主表 acceptResult=3（有不合格）。
- 全部为 1 → 主表 acceptResult=1（全部合格）。

累计不合格数量 unqualifiedQuantity 写入主表。

#### 3.4.4 验收完成自动生成入库单

updateConfirmMainInfo 末尾：

- 确认主表置 status=5、确认时间 confirmTime。
- 验收主表同步回写三个部门验收人信息并置 status=3（已验收）。
- 生成入库主表 t_inbound_main（RK 编号），明细只结转合格数量 qualifiedQty。
- 入库明细金额 = 合格数量 × 单价（含税/不含税分别计算）。
- 触发进度阶段 12-2（验收确认完成）。

### 3.5 入库（InboundMainServiceImpl）

#### 3.5.1 入库类型与方式

入库主表 inboundType（InboundMainDO 注释）：

- 1：采购入库。
- 2：调拨归还入库。
- 3：物资退库。
- 4：报废入库。
- 5：盘盈入库。
- 6：盘盈出库（DO 注释如此）。

入库方式 operationType（InboundMainDO 注释：1直接入库 2RFID打印入库）。

入库主表 status（InboundMainDO 注释：1待入库 2已入库 3入库中）。

#### 3.5.2 执行入库（doUpdateInboundMain）

- 记录入库人、入库时间。
- 明细逐条按 物资编码+仓库+货架 定位在库主表 t_bound_main（selectMaterialById）。
- 在库主表不存在：新建在库主表，初始数量为本次合格数量。
- 在库主表存在：累加 inventoryQuantity 与 availableQuantity，累加含税/不含税总价。
- 每次都写一条库存流水 t_bound_detail（types=1 入库），记录期初/本期/期末数量与金额、操作人、库龄、合同号。
- 流水记录 inboundDetailId 关联入库明细（后续出库用它查身份信息）。
- operationType=1：直接入库完成后主表 status=2（已入库）。
- operationType=2：RFID 打印流程，主表先置 status=3（入库中）。
- RFID 绑定打印完成（saveInboundRfid）后：身份记录 status 批量置 2（已打印），入库主表置 status=2。
- status=2 且带 trackingId 时触发进度阶段 13。
- 入库完成调用区块链上链 inboundChainAddLink（type=11）。

#### 3.5.3 退库转入库联动

- inboundType=3（物资退库）执行完成时，把退库主表 status 置 2（已入库）。
- 关联字段：入库主表 returnId 指向退库主表。

#### 3.5.4 数字身份生成

按合格数量逐件生成物资身份记录 t_material_identity：

- identityId：19 位雪花 ID。
- rfidCode：雪花字符串。
- boundMainId：在库主表。
- inboundDetailId：入库明细。
- status：1未打印/2已打印（初始 1）。
- outStatus：0未出库/1已出库（初始 0）。

（来源：InboundMainServiceImpl.validateInboundMainExists）

#### 3.5.5 临时资产库相关

convertToTemporaryAsset（转入库转临时资产）：

- 强制 inboundType=1（采购入库）、operationType=1（直接入库）。
- 仓库与货架替换为临时资产库及其默认货架。
- 临时资产库不存在则自动创建（is_unattended=3，名称"临时资产库"，编号 LSZCK）。
- 默认货架不存在则创建（名称"默认货架"，编号 MRHJ）。

### 3.6 出库/领用（OutboundMainServiceImpl）

#### 3.6.1 状态字典

出库主表 types（OutboundMainDO 注释：1正常领用 2紧急领用 3调拨出库 4盘亏出库 5报废出库 6临时领用）。

出库主表 status（OutboundMainDO 注释：1未出库 2已出库）。

出库主表 approvalStatus（OutboundMainDO 注释字典）：

- 1：待审批。
- 2：审批中。
- 3：审批通过。
- 4：审批不通过。
- 5：已退回。
- 6：已取消。

出库方式 outType（OutboundMainDO 注释：1普通仓库出库 2无人值守仓库出库）。

outType 判定：仓库 is_unattended=1 时 outType=2，否则 outType=1。

（来源：OutboundMainServiceImpl.createOutboundMain）

#### 3.6.2 创建领用单（占用可用库存）

创建流程（createOutboundMain）：

- 生成 CK 出库单号，出库单名称："{申请人}的领用单：{单号}"。
- 申请部门取自登录用户部门；用途写入明细。
- 临时领用（types=6）只能选临时资产库（is_unattended=3）的物资，否则报 1115。
- 明细必须输入领用数量，否则报 1114。
- 查询该在库物资可扣的入库流水（types in 1,3,4 且可用数量不为 0，按入库时间升序 = 先进先出）。
- 只有一个可扣批次：直接扣减该批次可用数量。
- 多个批次：按数量拆多条出库明细逐批扣减。
- 校验各批次可用合计 >= 领用数量，否则报 1112（库存不足）。
- 生成出库明细 t_outbound_detail（inDetailId 指向入库流水、价格按批次价、总额=单价×数量）。
- 生成一条 types=2、outStatus=1 的出库预占流水（写期初/本期/期末数量金额）。
- 扣减在库主表 availableQuantity（注意：此时不动 inventoryQuantity）。
- 普通出库（outType=1）把对应数量的物资身份记录绑定出库明细（outboundDetailId）。
- 触发进度阶段 14-1（出库单创建完成）。

出库明细关键字段：

- currentQuantity：本次领用数量。
- openingQuantity / closingQuantity：该批次的期初/期末数量。
- returnClosingQuantity：可退库剩余量，创建时=领用数量。
- uninstallQuantity：未安装数量，创建时=领用数量（供安装/退库统计）。
- inboundCode / contractNumber / inDetailId：溯源入库流水。
- shareCode：共享调拨出库（types=3）时的共享编号。

#### 3.6.3 审批（initiateApproval）

- 正常领用流程 key：material_outbound。
- 临时领用流程 key：material_temporary_outbound（非 types=6 报 1123）。
- 发起审批后 approvalStatus=2（审批中），记录 instanceId。
- 紧急领用（types=2）：发起审批时直接置 status=2（已出库）。

审批回调（updateApprovalStatus）：

- status=4（审批不通过）或 6（取消）：调用 rejectOutboundApproval 回滚（见下）。
- status=3（通过）且 trackingId 非空且 types in (1,2,6)：
  - 调用 isAllGoodsOutbound 判断该 trackingId 下所有物资是否已全部完成出库。
  - 全部完成则触发进度阶段 14-2。

回滚逻辑（rejectOutboundApproval）：

- 恢复在库主表 availableQuantity（加回领用数量）。
- 恢复对应入库流水 availableQuantity。
- 清空被占用的物资身份记录的 outboundDetailId（允许再领）。
- 删除该出库单的出库明细。
- 删除该单号下 types=2 的出库预占流水。
- 出库主表 status 恢复为 1（未出库）。

#### 3.6.4 确认出库（confirmOutbound，扣库存）

- 幂等保护：status 已为 2 的单据禁止重复确认（抛异常）。
  - 原因：盘亏出库等单据审批通过后已直接完成出库，重复确认会重复扣库存。
- 记录出库人、出库时间，主表 status=2。
- 将该单号下 types=2 的出库预占流水 outStatus 批量置 2（已出库）。
- 逐出库明细扣在库主表 inventoryQuantity 与含税/不含税总价。
- outType=2（无人值守仓库）：走 RFID 天线盘点流程：
  - MQTT 下发指令到 IoT，读写器扫描标签。
  - 通过 Redis 集合 data{outboundId} 汇总读到标签。
  - 盘点数量与实际出库数量不一致则抛错并结束。
  - 一致后把对应物资身份 outStatus 置 1、绑定出库明细。
- types=4（盘亏出库）分支：扣完后同步 availableQuantity = inventoryQuantity，并补 outStatus=2 的出库流水。
- types=3（共享调拨出库）分支：扣共享记录 lockQuantity 与 shareQuantity。
- 事务提交后异步执行区块链上链（outboundChainAddLink，type=12）。

#### 3.6.5 退库的前提条件

只有审批通过（approvalStatus=3）且已确认出库（status=2）的出库单才允许退库。

（来源：OutboundMainServiceImpl.getOutboundMainAndDetailPage）

#### 3.6.6 无人值守预约领用

- appointmentReceive：对接人脸识别机（DevicesDO device_type=6）发起预约。
- 预约时段 startTime/endTime 与照片 photo 写入出库主表。
- isTimeOut：0未预约、1未超时、2已超时。
- 查询出库列表时会扫描把已过期的预约置 isTimeOut=2（updateAppointmentStatus）。

### 3.7 退库（ReturnMainServiceImpl）

#### 3.7.1 创建退库单

- 入参为原出库单号 outboundCode + 退库明细列表。
- 校验退库数量 <= 出库明细 returnClosingQuantity（可退余量），超量报 1122。
- 生成 RT 退库单号，记录退库人/退库部门。
- 原出库明细 returnClosingQuantity 扣减本次退库数量。
- 退库明细写入：
  - totalReturnQuantity = 领用数量 - 扣减后的可退余量（累计已退总量）。
  - usageQuantity = 领用数量 - totalReturnQuantity（实际使用数量）。
  - returnQuantity：本次退库数量。
  - identityIds：本次退回物资的身份号，逗号拼接，并过滤已退过的身份号。
- 原出库主表含税/不含税总价同步扣减本次退库金额。

#### 3.7.2 退库审批与入库

- 审批流程 key：material_return。
- 发起审批置 approvalStatus=2；通过回调置 3。
- 审批通过后 createInbound（退库监听器回调）：生成 RK 入库单，inboundType=3、operationType=1，明细合格数量=退库数量。
- 在 InboundMainServiceImpl 真正执行该入库单时把退库主表 status 置 2（已入库）。

### 3.8 移库（MoveboundMainServiceImpl）

#### 3.8.1 建单与占用

- 移库单 YK：明细含源在库（boundMainId）、目标仓库/货架、移库数量 moveQuantity。
- 建单时校验可用数量（不足报 1112）。
- 在库主表 moveQuantity 累加、availableQuantity 扣减（占用锁定）。
- 移库明细 executed=0（未执行）。
- 修改移库单：按新旧数量差额调整占用（增加校验可用、减少则释放）。
- 删除移库单：回滚占用（moveQuantity 扣减、availableQuantity 恢复），再删明细与主表。

#### 3.8.2 状态机

移库主表 status（按明细执行进度自动更新）：

- 1：待移库（全部明细未执行）。
- 2：移库中（部分明细已执行）。
- 3：已移库（全部明细已执行）。

审批流程 key：material_movebound（approvalStatus=2 审批中）。

#### 3.8.3 执行移库（executeMoveboundDetail）

- 已执行（executed=1）的明细跳过，避免重复。
- 源在库：
  - 校验库存数量 >= 移库数量（不足报 1112）。
  - 扣减 inventoryQuantity。
  - 释放 moveQuantity 占用。
  - 按比例结转金额：金额 × 移出量 / 总库存（保留 2 位）。
- 目标货架按 物资编码+目标仓库+货架 定位：
  - 已存在相同物资：累加 inventoryQuantity、availableQuantity、金额。
  - 不存在：在目标仓库/货架新建在库主表（inventoryQuantity=移库量、availableQuantity=移库量）。
- 源、目标各写一条 types=4 移库库存流水（remark：移库移出/移库移入）。
- 移库入明细会记录单价（金额/数量），供后续共享/出库计价。
- 目标移库入流水的 inboundDetailId 回填为其自身 ID（出库查询身份信息的依据）。
- 源在库上未出库的物资身份记录按移库数量改绑到目标在库主表 + 目标入库明细。
- 明细置 executed=1。

### 3.9 报废（废旧）处置（WasteMainServiceImpl / WasteDetailServiceImpl）

#### 3.9.1 报废主表状态

报废主表 status（WasteMainDO 注释：1待审批 2审批中 3审批通过 4已驳回）。

- 建单后发起审批（material_waste），置 status=2。
- 审批通过（updateApprovalStatus(id,3)）：
  - status=3。
  - warehousedStatus=2（已入库标记）。
  - 注意：审批通过只改状态，不生成出库单/清单/流水。
- 审批驳回（status=4）：
  - status=4。
  - 退回未处置明细锁定的在库数量。
- 删除报废单：同样先退回未处置明细的锁定数量再删除。

#### 3.9.2 报废明细与来源

报废明细 sourceType：

- 1：在库（当前在库物资）。
- 2：出库（已领用出库的物资）。
- 3：无批次。

报废明细 status：0未处置、1已处置。

#### 3.9.3 在库物资报废的数量锁定（重点）

创建报废单（sourceType=1）时锁定数量（lockBoundQuantityForWaste）：

- 校验在库 availableQuantity >= 报废数量，不足报 1192。
- availableQuantity 扣减报废数量。
- wasteQuantity（t_bound_main 报废锁定列）累加报废数量。

明细定位在库记录（getBoundMainByWasteDetail）：

- 优先按 lables 解析：格式 在库主表ID-货架ID。
- 兜底按 sources 解析：格式 仓库名-货架名。
- 按 物资编码+仓库名+货架名 查询，找不到报 1193。
- 注意：前端实际只提交 sources，不提交 lables。

退回锁定（releaseLockedQuantity，驳回/删除时）：

- 只处理 sourceType=1 且 status=0（未处置）的明细。
- availableQuantity 加回报废数量。
- wasteQuantity 扣减报废数量（兜底不为负）。
- 已处置的明细不退回（处置时已扣减）。

#### 3.9.4 处置（updateWasteDetail）

处置操作：

- 明细置 status=1（已处置）。
- 写 t_waste_dispose 处置记录（处置方式、数量、接收人、联系人/电话、处置总价、日期、凭证附件）。
- sourceType=1 的在库物资调用 createOutboundMain 生成报废出库。

生成报废出库单（createOutboundMain）：

- 出库主表 CK 编号、types=5（报废出库）。
- approvalStatus=3、status=2（处置完成即出库）。
- 出库时间 = 处置时间。
- 金额取最近一条在库流水的单价 × 报废数量。
- 出库明细 currentQuantity=报废数量；期初=期末=当前可用数量。
- 生成 types=2、outStatus=2 的库存流水。
- 绑定物资身份到出库明细。
- 扣减 wasteQuantity 与 inventoryQuantity。
- 注意：不动 availableQuantity（建报废单时已扣）。
- 处置完成调用区块链上链（wasteDetailChainAddLink，type=13，含 t_waste_main/t_waste_detail/t_waste_dispose）。

出库清单/记录查询的口径：

- 出库记录页只展示 status=2 的出库单。
- 出库清单 SQL 排除 outStatus=1 的流水。
- 因此报废处置出库必须 status=2、流水 outStatus=2，否则查不到。

#### 3.9.5 出库来源的报废

- 选择"出库"来源时列出出库明细中 currentQuantity > wasteQuantity（未报废完）的物资。
- 处置时按出库单/明细登记报废，不涉及在库数量锁定。

（来源：WasteMainServiceImpl.getWasteSourceInfo）

### 3.10 盘点与差异处理（StockMainServiceImpl）

#### 3.10.1 盘点单状态与类型

盘点主表 stockType（StockMainDO 注释：0在线盘点 1扫码盘点 2普通盘点）。

盘点主表 status（StockMainDO 注释：1已完成 2待盘点 3盘点中 4已取消）。

- 建单：status=2（待盘点）。
- 在线盘点开始（updateStockMainStockTime）：status=3（盘点中）。
- Excel 导入确认全部行（confirmImport）或停止盘点（stopStock）：status=1（已完成）。
- cancelStock：status=4（已取消）。

其他盘点主表字段：

- plantCount：计划盘点数量。
- usageCount：已盘数量。
- differCount：差异数量。
- differRow：差异行数。
- allConfirm：1 表示全部账实相符。
- normalStatus：1不显示盘点数量差异，2显示（普通盘点用）。

#### 3.10.2 建盘点单

- 生成 PD 盘点单号。
- 仓库范围 warehouseRange：-1 表示全部仓库。
- 过滤 available_quantity 不为 0 的在库主表。
- 可选按物资类别过滤（含子类，MaterialCode parentId 递归一层）。
- 从在库快照生成盘点明细：
  - inventoryQuantity：账面库存数量。
  - usageQuantity：实盘数量（初始 0）。
  - differQuantity：差异数量（初始=账面库存量）。
- 明细同步费用列支、供应商、单价信息。

#### 3.10.3 盘点明细字段与状态

盘点明细：

- inventoryQuantity：账面（系统）数量。
- usageQuantity：实盘数量。
- differQuantity = inventoryQuantity - usageQuantity（差异数量）。
- differAmount：差异金额。
- differReason：差异原因说明。
- status：处理状态 0未盘、1已盘（StockDetailDO 注释）。
- handleStatus：审批状态 0未处理、1审批中、2已完成（StockDetailDO 注释）。

#### 3.10.4 在线盘点（RFID）

- 通过 MQTT 下发盘点指令给读写器。
- 标签集合从 Redis 缓存 data{盘点单id} 读取。
- 命中标签的 t_stock_identity 记录 status 置 1。
- 刷新明细 usageQuantity = 命中数。
- 不一致的明细维持未确认，一致的置 status=1。

#### 3.10.5 Excel 导入盘点

- 导入的正确行缓存在 Redis：stock:correct:list:{stockCode}。
- 错误行缓存在：stock:error:list:{stockCode}。
- confirmImport 用正确行回写盘点明细（按物资名+编码+货架匹配）。
- 差异数量、差异金额、明细 status=1 一并回写。
- 全部行都导入时盘点主表 status=1（已完成）。

#### 3.10.6 盘盈盘亏差异审批处理

盘盈（流程 key=material_stock_in，t_instance_code types=4）：

- 差异明细发起审批（initiateApproval）：handleStatus=1（审批中）。
- 审批通过（updateApprovalStatus(id,2)）：
  - handleStatus=2（已完成，幂等：已是 2 则直接返回）。
  - 生成 RK 入库单：inboundType=5（盘盈入库）、operationType=1、status=2（直接完成）。
  - 调用 addStockInventoryForSurplus 增加在库：
    - 按差异数量绝对值增库存。
    - 在库主表不存在则新建，存在则累加 inventoryQuantity/availableQuantity/金额。
    - 插 types=1 入库流水。
- 驳回/取消：handleStatus 回 0（未处理）。

盘亏（流程 key=material_stock_out，t_instance_code types=5）：

- 差异明细发起审批（initiateApprovalOut）：handleStatus=1、明细 status=1。
- 审批通过（updateApprovalStatusOut(id,2)）：
  - handleStatus=2（已完成，幂等）。
  - 生成 CK 出库单：types=4（盘亏出库）、status=2、approvalStatus=3、purpose=盘亏出库。
  - 调用 deductStockInventoryForShortage 扣减在库：
    - 扣 inventoryQuantity 与含税/不含税金额。
    - availableQuantity 同步为 inventoryQuantity。
    - 插 types=2、outStatus=2 出库流水。
- 驳回/取消：handleStatus 回 0。

### 3.11 维修/检修（MaterialRepairServiceImpl）

#### 3.11.1 检修单对象

- 检修针对已出库物资的单件数字身份（identityId）。
- 根据 identityId 查物资身份 → 取其 outboundDetailId 反查出库明细 → 取物资编码。
- 检修单号 WX。

#### 3.11.2 状态

检修单 status：

- 0：待处理（创建默认，getNoRepairCount 统计 status=0）。
- 1：处理中。
- 2：已完成。

状态由 handleStatus 映射（updateMaterialRepair）：

- handleStatus=1（确定/完成）→ status=2（已完成）。
- handleStatus=2（暂存/处理中）→ status=1（处理中）。

完成检修（handleStatus=1）触发区块链上链（repairChainAddLink，type=15）。

创建时也处理 creator 兼容：旧数据存 userId，展示时查用户表取昵称。

### 3.12 共享与调拨（MaterialSharedServiceImpl）

#### 3.12.1 共享登记

- 共享单号 GX；同一在库主表只保留一条共享记录。
- 校验在库 availableQuantity >= 共享数量，不足报 1171。
- 从在库主表与相关入库流水（types in 1,3,4）的 availableQuantity 划出共享量。
- 在库主表 availableQuantity 扣减、shardQuantity 累加。
- 流水级同样维护 availableQuantity 与 shardQuantity。
- 共享价格：平均价 = 各批单价和 / 批次数（保留 4 位）。
- 明细占用 JSON 存于 boundDetail 字段：[{"id":入库流水ID,"num":数量}]。
- 共享目标单位 targetUnit、共享单位 sharedUnit（租户）、操作人 sharedOperator。

#### 3.12.2 共享状态

共享记录 status（MaterialSharedDO 注释：1共享中 2已停用）。

- 停用共享（updateMaterialSharedByStatus status=2）：按 boundDetail JSON 逐流水归还可用数量、扣 shardQuantity。
- 启用共享（status=1）：校验后反向划拨。
- 删除限制：共享中（status=1）禁止删除，报 1172"请关闭共享，再删除"。

#### 3.12.3 共享调拨出库

- 外部单位申请调拨共享物资（RemoteDataServiceImpl 写入 lockQuantity 占用）。
- 本系统生成共享调拨出库单：出库主表 types=3，出库明细带 shareCode。
- 确认出库（confirmOutbound）时扣共享记录 lockQuantity 与 shareQuantity。

### 3.13 直接供货与核销（DirectSupplyServiceImpl）

#### 3.13.1 三层数据模型

- 登记主表/明细（t_register_main/t_register_item）：记录实际直供了哪些物资（项目、乙方、交付日期、数量、单价、批次）。
- 核销申请主表/明细（t_writeoff_main/t_writeoff_item）：记录本次想核销哪些物资，审批通过前只占用数量。
- 核销流水表（t_writeoff_flow）：审批通过后才落流水，是已核销数量与台账统计的最终依据。

#### 3.13.2 登记状态

- 登记主表 status：1正常、2作废（cancelRegister）。
- 金额服务端按明细汇总（totalAmount=Σ数量×单价），防前端篡改。
- 已核销/占用中的登记明细禁止修改数量单价、禁止删除。

#### 3.13.3 核销状态字典

核销申请 status（DirectSupplyServiceImpl 常量注释字典）：

- 1：待审批（草稿/待审批）。
- 2：审批中。
- 3：审批通过。
- 4：审批不通过。
- 5：已退回。
- 6：已取消。

流程 key：material_writeoff。

#### 3.13.4 可核销数量与占用

可核销数量 = 登记数量 - 已核销数量（流水） - 占用数量（待审批+审批中的申请明细）。

- 编辑时通过 excludeWriteoffId 排除当前单自己，避免自占。
- 提交（submit）前逐明细校验剩余量，防并发超核销。
- 提交流程：saveWriteoff(submit=true) → status=2 审批中 → startApproval 发起 BPM。

#### 3.13.5 审批通过落流水

审批通过（updateApprovalStatus）：

- 先校验各明细剩余可核销数量充足。
- 逐明细插入 t_writeoff_flow 流水（beforeQty/writeoffQty/writeoffAmount/操作人/时间）。
- 全部流水落完后再把主表置 status=3（避免"主表通过但无流水"半成品）。
- 写通过时间 passTime。
- upsert 项目台账 t_ledger_main：已核销金额、核销批次、核销率（已核销金额/登记金额）。

审批相关限制：

- 已审批通过的核销申请不能驳回。
- 审批中的核销申请不能删除（需先撤回/取消）。
- 删除已通过的核销单会级联删除流水并重算台账（recalcLedger）。

### 3.14 进度跟踪与区块链存证（横切能力）

#### 3.14.1 进度阶段

通过 WzProgressTrackingClient.addProgressTracking(id, trackingId, stage, ...) 与外部进度系统联动。

阶段值（从各 Service 注释与调用确认）：

| 阶段 | 触发时机 | 来源 |
|---|---|---|
| 11 | 到货单创建/更新 | PurchaseMainServiceImpl |
| 12-1 | 验收发起 | AcceptMainServiceImpl.createAcceptMain |
| 12-2 | 验收确认完成 | ConfirmMainServiceImpl.updateConfirmMainInfo |
| 13 | 直接入库完成或 RFID 入库完成 | InboundMainServiceImpl |
| 14-1 | 出库单创建完成 | OutboundMainServiceImpl.createOutboundMain |
| 14-2 | 出库审批通过且该 trackingId 物资全部出库 | OutboundMainServiceImpl.updateApprovalStatus |

全部出库判定（isAllGoodsOutbound）：

- 汇总该 trackingId 下采购明细采购数量（按物资编码）。
- 汇总该 trackingId 下审批通过出库明细的出库数量（按物资编码）。
- 逐物资比较出库数量 >= 采购数量才算全部完成。

#### 3.14.2 区块链上链 type

- 入库：type=11。
- 出库：type=12。
- 报废（主表+明细+处置）：type=13。
- 检修：type=15。
- belongModule=6。
- 关联字段 relationField = 对应单据编号。
- 采购单位取 t_melc_purchase_company_tenant（按租户）。

---

## 4. 物资主数据与库存模型

### 4.1 主数据

#### 物资编码与类别（t_material_code）

- code：物资编码。
- parentId：类别父子关系（多级树，getSonInfos 取子类）。
- materialType：类别标识，库存/单据上的 material_type 字段引用它。
- sort：排序，level：层级。

#### 仓库（t_warehouse）

- status：0使用中、1停用、2在建。
- isUnattended：0否、1是（无人值守仓）。
- 代码中 is_unattended=3 另作"临时资产库"标记。
  - ensureTemporaryWarehouse 创建/查找（InboundMainServiceImpl）。
  - 临时领用只允许临时资产库物资（OutboundMainServiceImpl）。
  - 页面在库查询可排除临时资产库（BoundMainServiceImpl）。

#### 货架（t_shelves）

- 挂在仓库下：warehouseId/warehouseName。
- 临时资产库自动创建"默认货架"（编号 MRHJ）。

#### 库位层级

仓库(warehouse) → 货架(shelves) → 库位上的在库记录(bound)。

在库记录定位键：物资编码 + 仓库 + 货架（各处 selectMaterialById 均按此三元组查询）。

### 4.2 在库主表 t_bound_main（BoundMainDO）

关键数量与金额字段：

| 字段 | 含义 | 变动时机 |
|---|---|---|
| inventoryQuantity | 库存数量（账面实有） | 入库累加；确认出库、盘亏、报废处置扣减 |
| availableQuantity | 可用数量（可操作余额） | 建领用单即扣、审批驳回归还；共享/移库/报废建单划出 |
| shardQuantity | 共享占用数量 | 共享登记从 available 划入；停用共享归还 |
| moveQuantity | 移库占用数量 | 建移库单划入；执行移库/删除移库单处理 |
| wasteQuantity | 报废锁定数量 | 建报废单从 available 划入；处置/驳回/删除回退 |
| totalPrice | 在库含税总价 | 随数量同增同减 |
| totalPriceExcludeTax | 在库不含税总价 | 随数量同增同减 |
| warningQuantity | 库存预警值 | updateBoundMainWarning 批量设置 |
| warningAccept | 预警接收人 | updateBoundMainWarning 批量设置 |
| trackingId | 进度跟踪链 ID | 入库带出，贯穿领用 |

其他字段：materialName、materialCode、specModel、material、drawingNo、unit、warehouseId/Name、warehouseCategory（库别）、shelvesId、shelfName、materialType、warningTime/warningDays（维保预警）、level。

### 4.3 数量变动时序（关键规则，勿混淆）

- inventoryQuantity（账面库存）只在实际出入库/盘差/报废处置时变动。
- 占用量（领用、共享、移库、报废申请）先扣 availableQuantity 及对应专用列。
- 流程取消/驳回时归还占用量（不动 inventoryQuantity）。
- 流程真正发生（确认出库、处置、执行移库）时再扣 inventoryQuantity 与金额。

举例（领用）：

- 建领用单：availableQuantity -= 领用数量。
- 审批驳回：availableQuantity += 领用数量。
- 确认出库：inventoryQuantity -= 领用数量，金额同步扣减。

举例（报废）：

- 建报废单：availableQuantity -= 报废数、wasteQuantity += 报废数。
- 处置：wasteQuantity -= 报废数、inventoryQuantity -= 报废数。
- 驳回/删除：availableQuantity += 未处置明细报废数、wasteQuantity -= 对应数。

### 4.4 库存流水 t_bound_detail（BoundDetailDO）

- types：1入库、2出库、3退库、4移库。
- docNumber：对应单据编号。
- inboundDetailId：关联入库明细（出库/移库按它查物资身份）。
- outStatus：1未出库（预占流水）、2已出库、3已退库。
- 财务台账字段：opening/current/closing 的 Quantity 与 Amount（期初/本期/期末数量与金额）。
- price / priceExcludeTax：本批含税/不含税单价。
- stockAge：库龄（天）。
- supplier / expensesListed / demandDept / operator / remark 等。

出库金额口径：

- 优先按各入库批次单价计算（同物资多批次时先进先出拆分，按 createTime 升序）。
- 出库清单查询只认 outStatus=2 的流水（排除预占流水）。

### 4.5 物资数字身份 t_material_identity（MaterialIdentityDO）

- identityId：19 位雪花唯一码（数字身份）。
- rfidCode：RFID 标签编码。
- boundMainId：所在在库主表。
- inboundDetailId：来源入库明细（流水）。
- outboundDetailId：出库绑定的出库明细（null 表示未出库占用）。
- status：1未打印、2已打印。
- outStatus：0未出库、1已出库。

生命周期：

- 入库：按合格数量逐件生成。
- 出库（普通仓）：创建领用单时按数量绑定 outboundDetailId。
- 出库（无人值守 RFID）：确认出库时按盘点标签绑定并置 outStatus=1。
- 移库：按数量改绑 boundMainId/inboundDetailId 到目标。
- 报废处置：绑定到报废出库明细。
- 审批驳回出库：清空 outboundDetailId 解绑。

---

## 5. 业务规则与约束（代码级硬规则）

### 5.1 数量校验类

| 规则 | 错误码 | 来源 |
|---|---|---|
| 出库领用数量必须输入 | 1114 | OutboundMainServiceImpl |
| 出库可用数量不足 | 1112 | OutboundMainServiceImpl |
| 共享登记可用数量不足 | 1171 | MaterialSharedServiceImpl |
| 共享物资变更时可用不足 | 1112 | MaterialSharedServiceImpl |
| 报废在库可用数量不足 | 1192 | WasteMainServiceImpl |
| 报废定位不到在库记录 | 1193 | WasteMainServiceImpl |
| 移库创建/修改占用可用不足 | 1112 | MoveboundMainServiceImpl |
| 退库数量超过可退余量 | 1122 | ReturnMainServiceImpl |
| 临时领用只能选临时资产库 | 1115 | OutboundMainServiceImpl |
| 非临时领用单不能走临时领用审批 | 1123 | OutboundMainServiceImpl |

### 5.2 审批与库存一致性规则

- 出库驳回/取消：必须走 rejectOutboundApproval 归还可用数量、解绑身份、删除明细与预占流水。
- 出库已出库（status=2）禁止重复确认（幂等保护）。
- 报废审批通过只置状态（status=3、warehousedStatus=2），不生成出库；处置时才生成 types=5 出库单。
- 报废驳回/删除：退回未处置明细的锁定数量。
- 盘盈/盘亏审批通过：handleStatus=2 幂等，直接生成单据并真正动库存。
- 共享启用中禁止删除（1172）。
- 核销通过：先落流水再置主表通过，避免半成品。
- 移库已执行明细（executed=1）不重复执行。

### 5.3 部门/角色硬校验

- 验收确认按 acceptType 校验登录人所属部门：
  - acceptType=1（仓管直验）只允许仓管部门。
  - acceptType=2/3（远程/三方）必须属于需求/技术/仓管三部门之一。
  - 各环节只能由对应部门账号操作。
- 错误码：1150 仓管部门未验收、1151 需求部门未验收、1152 技术部门未验收、1153 需求/技术未验收、1157 用户部门与验收部门不一致。
- 申请出库必须能取到登录人部门（否则报部门不存在错误）。

### 5.4 错误码分组速查（MaterialErrorCodeConstant）

| 分组 | 编号 | 说明 |
|---|---|---|
| 主数据 | 1001-1006 | 物资类别/仓库/货架/供应商/物资编码/设备不存在 |
| 到货验收确认 | 1101-1106 | 到货、验收、确认主/明细不存在 |
| 入库在库 | 1107-1113 | 入库单、在库主/明细、出库单不存在，库存不足、身份不存在 |
| 出库领用 | 1114-1115 | 未输入领用数量、临时领用只能选临时资产库 |
| 退库 | 1117-1123 | 退库单不存在、退库数量不合理、非临时领用类型 |
| 移库/预警/提取 | 1130-1133 | 移库主/明细不存在、预警记录不存在、生成需求物资单失败、采购订单不存在/已提取/无明细 |
| 验收部门 | 1150-1157 | 仓管/需求/技术部门验收相关 |
| 维保 | 1154-1156 | 维保规则/记录/预警不存在 |
| 共享 | 1170-1172 | 共享物资不存在、库存不足、共享中不可删除 |
| 盘点 | 1180 | 盘点主/明细不存在 |
| 报废 | 1190-1193 | 报废不存在、明细不存在、可用不足、在库记录不存在 |
| 安装/检修 | 2000-2010 | 安装登记不存在、安装数量超限、检修管理不存在 |
| 评价 | 2020-2022 | 评价规则/记录/结果不存在 |
| 流程 | 2030 | 单据编号（流程实例关联）不存在 |

### 5.5 审批流 BPM key 清单

| 流程 key | 业务 | 来源类 |
|---|---|---|
| material_outbound | 正常领用出库 | OutboundMainServiceImpl |
| material_temporary_outbound | 临时领用出库 | OutboundMainServiceImpl |
| material_return | 退库 | ReturnMainServiceImpl |
| material_waste | 报废 | WasteMainServiceImpl |
| material_stock_in | 盘点盘盈入库 | StockMainServiceImpl |
| material_stock_out | 盘点盘亏出库 | StockMainServiceImpl |
| material_movebound | 移库 | MoveboundMainServiceImpl |
| material_writeoff | 直供核销 | DirectSupplyServiceImpl |

### 5.6 其他规则

- 金额精度：展示统一 4 位小数（HALF_UP）；不含税单价 = 含税单价/(1+税率) 保留 4 位 DOWN。
- 到货 Excel 导入：必填校验 计划名称/合同名称/合同编号/物资名称/单位/数量/单价/总价/税率/供货单位/需求部门；校验含税单价×数量≈含税总价（误差 > 0.0001 报错）。
- 多租户与异步：出库上链等异步任务手动恢复 TenantContext（CompletableFuture + TenantContextHolder），上链失败仅记日志不影响主流程。
- 预约超时：查询出库列表时把已过期的预约标记 isTimeOut=2。
- 库存预警：在库主表支持 warningQuantity/warningAccept 批量维护（BoundMainServiceImpl.updateBoundMainWarning）。

---

## 6. 关键表与字段映射

### 6.1 主链路单据表

| DO（domain 包） | 表名 | 关键字段 |
|---|---|---|
| PurchaseMainDO | t_purchase_main | arrivalCode(DH)、status 1未到货/2部分/3全部、planName/contractName/contractNumber、totalPriceWithTax |
| PurchaseDetailDO | t_purchase_detail | mainId、materialCode、purchaseQuantity、receivedQuantity、pendingQuantity、price、taxRate、supplier、demandDepartment、warehouseName、shelvesName |
| AcceptMainDO | t_accept_main | acceptCode(YS)、acceptType 1仓管/2远程/3三方、status 1待验/2验中/3已验/4拒绝、demandChecker/techChecker/warehouseChecker+UserId+Time |
| AcceptDetailDO | t_accept_detail | acceptMainId、arrivalQty、qualifiedQty、acceptResult 1全合/2全不合/3部分 |
| ConfirmMainDO | t_confirm_main | confirmCode、status 1→2/3→4通过→5完成/6拒绝、acceptMainId、acceptCode、三部门校验人+时间、acceptResult、unqualifiedQuantity |
| ConfirmDetailDO | t_confirm_detail | confirmMainId、acceptDetailId、arrivalQty、qualifiedQty、acceptResult |
| InboundMainDO | t_inbound_main | inboundCode(RK)、inboundType 1采购/2调拨归还/3退库/4报废/5盘盈/6盘盈出库、operationType 1直接/2RFID、status 1待入/2已入/3入中、acceptCode、returnId |
| InboundDetailDO | t_inbound_detail | inboundId、qualifiedQty、price、totalPrice、materialCode、warehouseId+shelvesId |

### 6.2 库存与出入库表

| DO | 表名 | 关键字段 |
|---|---|---|
| BoundMainDO | t_bound_main | materialCode、inventoryQuantity、availableQuantity、shardQuantity、moveQuantity、wasteQuantity、totalPrice(含税)、totalPriceExcludeTax、warehouseId/Name/Category、shelvesId/shelfName、warningQuantity、warningAccept、trackingId |
| BoundDetailDO | t_bound_detail | mainId、inboundDetailId、docNumber、types 1入/2出/3退/4移、outStatus 1未出/2已出/3已退、openingQuantity/Amount、currentQuantity/Amount、closingQuantity/Amount、price、stockAge、operator |
| OutboundMainDO | t_outbound_main | outboundCode(CK)、types 1正常/2紧急/3调拨/4盘亏/5报废/6临时、status 1未出/2已出、approvalStatus 1-6 字典、outType 1普通/2无人值守、outPerson、outTime、isTimeOut、trackingId |
| OutboundDetailDO | t_outbound_detail | outboundId、boundMainId、currentQuantity、opening/closingQuantity、returnClosingQuantity、uninstallQuantity、inDetailId、inboundCode、contractNumber、shareCode |
| ReturnMainDO | t_return_main | returnCode(RT)、status(入库完成置2)、returnPerson/Dept、approvalStatus、instanceId |
| ReturnDetailDO | t_return_detail | returnId(退库单号)、outboundDetailId、returnQuantity、totalReturnQuantity、usageQuantity、identityIds |
| MoveboundMainDO | t_movebound_main | moveCode(YK)、status 1待移/2移中/3已移、approvalStatus、instanceId |
| MoveboundDetailDO | t_movebound_detail | mainId、boundMainId、moveQuantity、targetWarehouseId/Name、targetShelfId/Name、executed 0/1 |

### 6.3 专用业务表

| DO | 表名 | 关键字段 |
|---|---|---|
| WasteMainDO | t_waste_main | wasteCode(BF)、types(物资种类数)、reason、surveyReport、status 1待审/2审中/3通过/4驳回、warehousedStatus 1未/2已入、instanceId |
| WasteDetailDO | t_waste_detail | mainId、sourceType 1在库/2出库/3无批次、wasteNum、status 0未处置/1已处置、sources(仓库名-货架名)、lables(在库ID-货架ID) |
| WasteDisposeDO | t_waste_dispose | detailId、disposalWay、disposalNum、disposalTotal、receiver、contactPerson/Phone、fixtureDate、fileUrl |
| StockMainDO | t_stock_main | stockCode(PD)、stockType 0在线/1扫码/2普通、status 1完成/2待盘/3盘/4取消、plantCount、usageCount、differCount、differRow、allConfirm、normalStatus、operator |
| StockDetailDO | t_stock_detail | stockId、boundId、materialId、inventoryQuantity、usageQuantity、differQuantity、differAmount、differReason、status 0未盘/1已盘、handleStatus 0未处理/1审中/2完成、instanceId |
| StockIdentityDO | t_stock_identity | stockDetailId、rfidCode、status(盘点命中) |
| StockFileDO | t_stock_file | 盘点附件 |
| MaterialIdentityDO | t_material_identity | identityId、rfidCode、boundMainId、inboundDetailId、outboundDetailId、status 1未打印/2已打印、outStatus 0未出/1已出 |
| MaterialSharedDO | t_material_shared | shareCode(GX)、boundMainId、shareQuantity、lockQuantity、inventoryQuantity、status 1共享中/2停用、boundDetail(JSON)、targetUnit、sharedUnit、sharedTime、sharedOperator |
| MaterialRepairDO | t_material_repair | repairCode(WX)、code(身份ID)、status 0待处理/1处理中/2已完成、handleStatus、repairStartTime/EndTime、creator |
| MaterialCodeDO | t_material_code | code、name、parentId、materialType、sort、level |
| MaterialInstallDO | t_material_install | 安装登记（AZ） |
| WarehouseDO | t_warehouse | code、name、status 0用/1停/2建、isUnattended 0否/1是/3临时资产库、category |
| ShelvesDO | t_shelves | code、name、warehouseId、warehouseName、states、types |
| InstanceCodeDO | t_instance_code | code(单号)、instanceId(BPM)、types 1出库/2退库/3报废/4盘盈/5盘亏/6移库 |
| MaterialTypeDO | t_material_type | 物资类别 |
| DevicesDO | t_devices | 硬件：device_type(1出库读写器/6人脸机)、ipAddress、portNumber、outboundAntennaId |
| THardwareServerDO | t_hardware_server | IoT 服务 ipUrl/ipPord/topic |

### 6.4 直接供货与核销表

| DO | 表名 | 关键字段 |
|---|---|---|
| DirectSupplyRegisterDO | t_register_main | projectCode/Name、companyName、registerBatch、status 1正常/2作废、totalAmount、registerUser/Time |
| DirectSupplyRegisterItemDO | t_register_item | registerId、materialCode/Name、qty、price、deliveryDate |
| DirectSupplyWriteoffDO | t_writeoff_main | writeoffApplyNo(HX)、status 1待审/2审中/3通过/4不通过/5退回/6取消、processInstanceId、applyUser/Time、passTime |
| DirectSupplyWriteoffItemDO | t_writeoff_item | writeoffId、registerItemId、applyQty、price、materialName |
| DirectSupplyWriteoffFlowDO | t_writeoff_flow | writeoffId、registerItemId、beforeQty、writeoffQty、writeoffAmount、writeoffUser/Time |
| DirectSupplyLedgerDO | t_ledger_main | projectCode/Name、writtenAmount、writeoffRate、批次 |

### 6.5 外部同步表（只读主数据）

| DO | 表名 | 说明 |
|---|---|---|
| WzContractDO | t_wz_contract | 合同 |
| WzSupplierDO 及风控各表 | t_wz_supplier* | 供应商与风控画像（datasync 批量同步） |
| MelcPurchaseOrderDO | t_melc_purchase_order | 采购订单（提取到货来源） |
| MelcPurchaseCompanyTenantDO | t_melc_purchase_company_tenant | 租户-采购单位关系（上链用） |
| WzProgressTracking 相关 | （外部服务） | 进度跟踪 11/12-1/12-2/13/14-1/14-2 |

---

## 7. RAG 检索注意事项（防误用提示）

- 同前缀多业务：RK 入库单可能来自验收合格、退库转入库、盘盈入库三处，用 inboundType 区分。
- 同前缀多业务：CK 出库单有 6 种 types，报废处置出库与盘亏出库在生成时 status 已=2 且流水 outStatus=2。
- 统计口径：出库记录/出库清单必须过滤 status=2 与 outStatus=2，不要把预占流水（outStatus=1）当已出库。
- 报废不等于出库：审批通过不生成出库，处置时才生成 types=5 报废出库单。
- 两步扣减：领用创建扣可用数量（availableQuantity），确认出库才扣账面库存（inventoryQuantity）与金额；答疑时区分"可领用余额/账面库存/已出库"。
- 在库记录按 物资编码+仓库+货架 定位；改库位（移库）会新建或累加目标在库记录并结转金额。
- 报废明细定位：前端只传 sources（仓库名-货架名），后端按 materialCode+仓库名+货架名 匹配在库记录。


---

## 第二部分：数据库结构（第 6 章）

> 数据来源：`D:\idea\materials_back\echo-module-material\echo-module-material-server\src\main\java` 下 DO/实体类（mybatis-plus `@TableName` 注解）及 `src\main\resources\mapper\*.xml`。未连接数据库，字段含义一律以代码注释为准；无注释字段标注"代码中无注释"。
>
> 通用约定：
> 1. 所有实体均继承框架 `BaseDO`（yudao/芋道风格），自带公共审计列：`create_time`(创建时间)、`update_time`(最后更新时间)、`creator`(创建者，存 SysUser id，String)、`updater`(更新者，存 SysUser id，String)、`deleted`(逻辑删除，Boolean，`@TableLogic`)。下文中各表字段表不再重复列出这 5 列。
> 2. 部分实体继承 `TenantBaseDO`（在 BaseDO 基础上多 `tenant_id` 多租户编号列，查询自动按租户隔离）；另有部分表打了 `@TenantIgnore`（跳过租户拦截）或干脆是普通 `BaseDO`（无 tenant_id 字段，物理表可能另有，但代码层不映射）。
> 3. 字段列名默认由 Java 驼峰属性经 mybatis-plus 映射为下划线，如 `materialCode` → `material_code`；个别表（如 `t_wz_*`、`t_hardware_server`）显式用 `@TableField` 指定了列名。
> 4. Java 类型即实体属性类型；数据库长度、精度等未在代码中体现，无法推断。
> 5. 单据编号规则见第 3 节，主键 `@TableId` 未特殊说明均为数据库自增（部分表带 `@KeySequence` 兼容 Oracle/Kingbase 等，MySQL 下不生效）。

## 1. 表清单总览

共 73 张唯一业务表（另有两份 DO 类指向同一张表 `t_material_code`，见备注）。按业务域划分：

### 1.1 主数据类（物资、供应商、合同、仓库货架）

| DO 类名 | 表名 | 租户 | 用途一句话 |
|---|---|---|---|
| MaterialTypeDO | t_material_type | 否(BaseDO) | 物资类别（物资大类），type 区分金属/非金属 |
| MaterialCodeDO | t_material_code | @TenantIgnore | 物资编码（物资档案树，含物资名称/编号/父级/分类/单位等） |
| MaterialCodeDO（driver 包冗余副本） | t_material_code | @TenantIgnore | 同一张表，driver 包下重复声明的同类 DO |
| ProviderDO | t_provider | 否(BaseDO) | 供应商信息（旧版手工维护供应商档案：名称/地址/联系人/主营产品） |
| WzSupplierDO | t_wz_supplier | @TenantIgnore | 供应商主档（外部企业信用接口同步，含工商基础信息、同步状态） |
| WzSupplierBusinessLicenseDO | t_wz_supplier_business_license | @TenantIgnore | 供应商营业执照详情（工商登记全字段） |
| WzSupplierBasicQualityDO | t_wz_supplier_basic_quality | @TenantIgnore | 供应商基本素质（注册年限/经营状态/曾用名等画像） |
| WzSupplierScoreDO | t_wz_supplier_score | @TenantIgnore | 供应商评分（市场/信用风险/基本素质/技术/ESG 评分） |
| WzSupplierLabelDO | t_wz_supplier_label | @TenantIgnore | 供应商标签（两级标签类型+分数） |
| WzSupplierDishonestyDO | t_wz_supplier_dishonesty | @TenantIgnore | 供应商失信被执行人/限制高消费记录 |
| WzSupplierAnnoCancelFillDO | t_wz_supplier_anno_cancel_fill | @TenantIgnore | 注销清算公告（清算组+债权人公告信息） |
| WzSupplierAnnoTaxArrearsDO | t_wz_supplier_anno_tax_arrears | @TenantIgnore | 欠税公告（欠税金额/税种/公告机关） |
| WzSupplierCheckInspectionDO | t_wz_supplier_check_inspection | @TenantIgnore | 抽查检查记录（市监抽查任务/结果明细 JSON） |
| WzSupplierChattelMortgageDO | t_wz_supplier_chattel_mortgage | @TenantIgnore | 动产抵押登记 |
| WzSupplierEquityFreezeDO | t_wz_supplier_equity_freeze | @TenantIgnore | 股权冻结信息 |
| WzSupplierEquityPledgeDO | t_wz_supplier_equity_pledge | @TenantIgnore | 股权出质信息 |
| WzSupplierInquiryEvaluationDO | t_wz_supplier_inquiry_evaluation | @TenantIgnore | 司法询价评估（被执行人财产评估） |
| WzSupplierJudicialAuctionDO | t_wz_supplier_judicial_auction | @TenantIgnore | 司法拍卖记录 |
| WzSupplierLawsuitDO | t_wz_supplier_lawsuit | @TenantIgnore | 法律诉讼（开庭公告/裁判文书）记录 |
| WzSupplierLawsuitExecDO | t_wz_supplier_lawsuit_exec | @TenantIgnore | 被执行信息（诉讼被执行/终本案件） |
| WzSupplierNonCompliantTaxDO | t_wz_supplier_non_compliant_tax | @TenantIgnore | 税务非正常户记录 |
| WzSupplierPunishmentDO | t_wz_supplier_punishment | @TenantIgnore | 行政处罚记录 |
| WzSupplierSimpleCancelDO | t_wz_supplier_simple_cancel | @TenantIgnore | 简易注销公告 |
| WzContractDO | t_wz_contract | @TenantIgnore | 合同（外部招标/采购合同同步快照，按 sync 批次） |
| WarehouseDO | t_warehouse | 否(BaseDO) | 仓库档案（位置/尺寸/库别/无人值守等） |
| ShelvesDO | t_shelves | 否(BaseDO) | 货架档案（所属仓库、设备/标签绑定、货位类型） |

### 1.2 物资身份与库存

| DO 类名 | 表名 | 租户 | 用途一句话 |
|---|---|---|---|
| MaterialIdentityDO | t_material_identity | 否(BaseDO) | 物资数字身份（RFID 标签，绑定入库/出库明细与在库主记录） |
| BoundMainDO | t_bound_main | 是(TenantBaseDO) | 在库物资主表（现存量/可用/共享/报废锁定数量、仓位、维保预警） |
| BoundDetailDO | t_bound_detail | 是(TenantBaseDO) | 库存出入库流水/批次明细（期初/本期/期末数量金额，类型=出入库退移） |
| BoundWarningDO | t_bound_warning | 是(TenantBaseDO) | 库存预警记录（不足/超储/临期及处理动作） |

### 1.3 单据类（采购到货→验收→入库→在库→出库→退库/移库/报废）

| DO 类名 | 表名 | 租户 | 用途一句话 |
|---|---|---|---|
| MelcPurchaseOrderDO | t_melc_purchase_order | 否(BaseDO) | 外部采购订单同步主表（旧物资全生命周期项目快照） |
| MelcPurchaseOrderDetailDO | t_melc_purchase_order_detail | 否(BaseDO) | 外部采购订单物料明细同步表 |
| MelcPurchaseCompanyTenantDO | t_melc_purchase_company_tenant | @TenantIgnore | 采购单位→租户映射（同步订单时据此回填 tenant_id） |
| PurchaseMainDO | t_purchase_main | 是(TenantBaseDO) | 物资到货单/到货计划主表（编号 DH-，关联采购订单） |
| PurchaseDetailDO | t_purchase_detail | 否(BaseDO) | 到货单明细（采购/未到/已到数量） |
| AcceptMainDO | t_accept_main | 是(TenantBaseDO) | 验收主表（编号 YS-，需求部/技术部/仓管部三段验收） |
| AcceptDetailDO | t_accept_detail | 是(TenantBaseDO) | 验收明细（到货/合格数量、验收结果、图片） |
| ConfirmMainDO | t_confirm_main | 否(BaseDO) | 验收确认主表（终验结果汇总，关联 acceptMainId） |
| ConfirmDetailDO | t_confirm_detail | 否(BaseDO) | 验收确认明细（快照验收明细，可多选） |
| InboundMainDO | t_inbound_main | 是(TenantBaseDO) | 入库单主表（编号 RK-，类型=采购/调拨归还/退库/报废/盘盈等） |
| InboundDetailDO | t_inbound_detail | 是(TenantBaseDO) | 入库单明细（合格数量、仓库货架落位） |
| OutboundMainDO | t_outbound_main | 是(TenantBaseDO) | 出库单主表（编号 CK-，类型=正常/紧急领用、调拨、盘亏、报废、临时） |
| OutboundDetailDO | t_outbound_detail | 是(TenantBaseDO) | 出库单明细（绑定库存批次、领用数量、安装/报废数量回写） |
| ReturnMainDO | t_return_main | 否(BaseDO) | 退库单主表（编号 RT-，关联原出库单，审批后生成入库） |
| ReturnDetailDO | t_return_detail | 否(BaseDO) | 退库单明细（领用/使用/退还数量，绑在库主记录） |
| MoveboundMainDO | t_movebound_main | 否(BaseDO) | 移库主表（编号 YK-，同仓/跨仓） |
| MoveboundDetailDO | t_movebound_detail | 否(BaseDO) | 移库明细（源/目标仓库货架，绑在库主记录） |
| WasteMainDO | t_waste_main | 是(TenantBaseDO) | 废旧报废单主表（编号 BF-，审批后待处置） |
| WasteDetailDO | t_waste_detail | 是(TenantBaseDO) | 报废明细（来源类型=在库/出库/无批次，报废数量锁定） |
| WasteDisposeDO | t_waste_dispose | 是(TenantBaseDO) | 报废处置记录（拍卖/招标/直接销售/销毁等） |
| MaterialSharedDO | t_material_shared | 否(BaseDO) | 物资共享（共享数量/截止时间/可见范围，锁定可用量） |
| MaterialInstallDO | t_material_install | 是(TenantBaseDO) | 安装登记（编号 AZ-，绑出库明细，安装位置/照片） |
| MaterialRepairDO | t_material_repair | 是(TenantBaseDO) | 检修管理（编号 WX-，故障/紧急程度/检修内容） |
| InstanceCodeDO | t_instance_code | @TenantIgnore | 审批流程实例与单据编号映射（用于审批详情反查单据） |

### 1.4 盘点、维保、评价、预警、系统配置

| DO 类名 | 表名 | 租户 | 用途一句话 |
|---|---|---|---|
| StockMainDO | t_stock_main | 否(BaseDO) | 物资盘点主表（编号 PD-，在线/扫码/普通盘点） |
| StockDetailDO | t_stock_detail | 否(BaseDO) | 盘点明细（系统数/实盘数/差异，差异走审批处理） |
| StockFileDO | t_stock_file | 否(BaseDO) | 普通盘点上传文件存储（按盘点单号） |
| StockIdentityDO | t_stock_identity | 否(BaseDO) | 盘点物资 RFID 身份（逐标签盘到状态） |
| MaintenanceRuleDO | t_maintenance_rule | 是(TenantBaseDO) | 维保规则（按物资/分类定义维保周期与预警天数） |
| MaintenanceAlertDO | t_maintenance_alert | 是(TenantBaseDO) | 维保预警（到期物资预警，状态=正常/即将到期/已到期） |
| MiantenanceRecordDO | t_miantenance_record | 否(BaseDO) | 维保记录（表名 miantenance 为代码拼写，实际表名如此） |
| ReviewRuleDO | t_review_rule | 否(BaseDO) | 供应商评价规则（质量/服务/价格/交付/合规权重配置） |
| ReviewRecordDO | t_review_record | 是(TenantBaseDO) | 供应商评价记录（一次到货验收后评价打分，绑验收主/明细） |
| ReviewResultDO | t_review_result | 否(BaseDO) | 供应商评价结果汇总（按供应单位聚合评分排名） |
| DevicesDO | t_devices | 否(BaseDO) | RFID 硬件设备（读写器，出/入库/盘点天线，IP/信道） |
| THardwareServerDO | t_hardware_server | 显式 tenant_id 列 | 硬件服务配置（每租户一套，IP/端口/MQTT topic，主键注释为租户id） |
| MenuDO | t_user_menu | 否(BaseDO) | 用户选中的菜单（userId + 菜单 id 串） |
| ExportTemplateRouteDO | t_export_template | 是(TenantBaseDO) | 导出模板路由配置（feature→Spring Bean，按租户覆盖） |

### 1.5 直供物资（登记→核销，跨租户全局业务）

| DO 类名 | 表名 | 租户 | 用途一句话 |
|---|---|---|---|
| DirectSupplyRegisterDO | t_register_main | @TenantIgnore | 直供物资登记主表（按项目+乙方分批登记） |
| DirectSupplyRegisterItemDO | t_register_item | @TenantIgnore | 直供登记明细（物资快照，核销申请来源） |
| DirectSupplyWriteoffDO | t_writeoff_main | @TenantIgnore | 直供核销申请（编号 HX-，审批通过即成为已核销批次） |
| DirectSupplyWriteoffItemDO | t_writeoff_item | @TenantIgnore | 核销申请明细（直供总量/已核销/本次申请/剩余） |
| DirectSupplyWriteoffFlowDO | t_writeoff_flow | @TenantIgnore | 核销流水（核销前后数量变化，审批通过后生成） |
| DirectSupplyLedgerDO | t_ledger_main | @TenantIgnore | 直供核销台账（一项目一行，核销金额/未核销/核销率汇总） |

> 说明：`DriverMainDO`、`MaterialStockAgeDO`、`MaterialTurnoverRateDO`、`MaterialAlertDO`（driver 与 maintenancealert 两处同名类）、`OutboundMainDetailDO` 均**无 @TableName**，是驾驶舱报表/接口 VO 聚合对象或请求 VO，不落库。`OutboundMainDetailDO` 实际继承 `OutboundDetailDO` 用作"确认出库"请求体。

## 2. 核心表结构详解

> 通用物资快照列（多张单据明细表几乎都含以下同名字段，语义一致，下文"标准快照列"即指这些）：
> `materialName`物资名称(String)、`materialCode`物资编码(String)、`specModel`规格型号(String)、`material`材质(String)、`drawingNo`图号(String)、`price`单价含税(BigDecimal)、`priceExcludeTax`单价不含税(BigDecimal)、`unit`单位(String)、`supplier`供应单位(String)、`demandDept`需求部门(String)、`expensesListed`列支费用(String)、`warehouseId`仓库ID(Integer)、`warehouseName`仓库名称(String)、`warehouseCategory`库别(String)、`shelvesId`货架ID(Integer)、`shelfName`货架名称(String)、`materialType`物资类别(String)、`remark`备注(String)。

### 2.1 物资类别 t_material_type

用途：物资大类字典（金属/非金属等），供物资编码树与单据物资归类引用。

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Long | 序号(@TableId) |
| name | String | 类别名称 |
| code | String | 类别编码 |
| type | String | 类型仅可选：0(金属)；1(非金属) |
| state | Integer | 状态仅可选：0(使用)；1(停用) |

### 2.2 物资编码 t_material_code

用途：物资档案/编码树（@TenantIgnore，全租户共享同一物资目录）。注意本模块存在两份指向本表的 DO（materialcode 包与 driver 包冗余副本）。

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Long | id(@TableId) |
| name | String | 物资名称 |
| code | String | 物资编号（业务上用前缀 Code 生成） |
| parentId | Long | 父级id（编码树） |
| sort | Integer | 显示顺序 |
| status | Integer | 编码状态（0正常 1停用） |
| typeCode | String | 分类编码 |
| typeName | String | 分类名 |
| materialType | String | 物料类型 |
| unit | String | 基本计量单位 |
| materialDescription | String | 物料描述 |

### 2.3 仓库 t_warehouse（主数据-仓库货架）

用途：仓库档案主数据；单据与在库记录通过冗余 warehouseId/warehouseName 引用。

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Integer | 唯一编号(@TableId, IdType.INPUT) |
| code | String | 仓库编码（默认临时仓库由系统生成前缀 LSZCK） |
| name | String | 仓库名称 |
| position | String | 仓库位置 |
| whLength / whWidth / whHeight | String | 仓库长度 / 宽度 / 高度 |
| features | String | 仓库特性 |
| requirement | String | 存放物品要求 |
| status | Integer | 仓库状态 0 使用中 1 停用 2 在建 |
| pictureUrl | String | 仓库CAD图地址 |
| isUnattended | Integer | 是否是无人值守类型，0-否，1-是 |
| category | String | 仓库库别 |

### 2.4 货架 t_shelves（主数据-仓库货架）

用途：货架档案；通过 warehouseId 挂到仓库（业务关联即"仓库名-货架名"定位在库物资）。

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Integer | 唯一编号(@TableId) |
| code | String | 货架编号（默认货架由系统生成前缀 MRHJ） |
| name | String | 货架名称 |
| warehouseId | Integer | 所属仓库ID |
| warehouseName | String | 注释误写"货架位置"，实际为冗余的仓库名称 |
| position | String | 货架位置 |
| sLength / width / height | String | 货架长度 / 宽度 / 高度 |
| states | Integer | 货架状态（代码中无注释） |
| types | Integer | 货位类型 1一物一码 2一类一码 |
| equipmentId | Integer | 所属仓库的设备ID |
| labelId | Integer | 有源标签的ID |
| materialTypeId | String | 物资类别ID |

### 2.5 在库物资主表 t_bound_main（核心：在库现状）

用途：实时库存主档，一物一仓一位一行；`inventoryQuantity` 为账面总量，`availableQuantity` 为可用量（出库扣减），`shardQuantity` 为共享占用，`wasteQuantity` 为报废单锁定数量（创建报废单时从可用划入、处置时扣减）。出入库/移库/退库/盘点等动作都会同步维护本表数量与仓库货架。

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Integer | 主键ID(@TableId) |
| materialName | String | 物资名称 |
| materialCode | String | 物资编码 |
| specModel | String | 规格型号 |
| material | String | 材质 |
| drawingNo | String | 图号 |
| unit | String | 单位 |
| totalPrice | BigDecimal | 含税总价 |
| totalPriceExcludeTax | BigDecimal | 不含税总价 |
| inventoryQuantity | BigDecimal | 库存数量 |
| availableQuantity | BigDecimal | 可用数量 |
| shardQuantity | BigDecimal | 共享数量 |
| warningQuantity | BigDecimal | 库存预警值 |
| warningAccept | String | 预警接收人 |
| warehouseId | Integer | 仓库ID |
| warehouseName | String | 仓库名称 |
| warehouseCategory | String | 库别 |
| shelvesId | Integer | 货架ID |
| shelfName | String | 货架名称 |
| materialType | String | 物资类别 |
| remark | String | 备注 |
| warningTime | LocalDateTime | 维保预警截止时间 |
| warningDays | Integer | 维保预警提前天数 |
| level | Integer | 层级优先级 |
| moveQuantity | BigDecimal | 移库数量 |
| wasteQuantity | BigDecimal | 报废数量（创建报废单时从可用数量划入，处置时扣减） |
| trackingId | String | 进度跟踪id |

### 2.6 库存出入库流水 t_bound_detail（核心：批次/流水）

用途：一张在库主记录下按单据产生多条库存流水（入库/出库/退库/移库），记录期初-本期-期末数量与金额及库龄、出库状态（出库与退库按批次扣减的依据）。

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Integer | 主键ID(@TableId) |
| mainId | Integer | 库存主表ID（→ t_bound_main.id） |
| inboundDetailId | Integer | 入库明细ID（关联 t_inbound_detail，用于出库时查询物资身份信息） |
| docNumber | String | 出入库编号（入库时存入库单号，出库批次选择时被读走） |
| types | Integer | 类型:1入库 2出库 3退库 4移库 |
| stockAge | Integer | 库龄（天） |
| contractNumber / contractName | String | 合同编号 / 合同名称 |
| unit | String | 单位 |
| openingQuantity / currentQuantity / closingQuantity | BigDecimal | 期初数量 / 本期数量 / 期末数量 |
| availableQuantity | BigDecimal | 可用数量 |
| shardQuantity | BigDecimal | 共享数量 |
| openingAmount / currentAmount / closingAmount | BigDecimal | 期初金额(元) / 本期金额(元) / 期末金额(元) |
| price | BigDecimal | 单价（含税） |
| priceExcludeTax | BigDecimal | 单价(不含税) |
| expensesListed | String | 列支费用 |
| supplier | String | 供应单位 |
| demandDept | String | 需求部门 |
| operationAddress | String | 操作地址 |
| operator | String | 操作人 |
| materialType | String | 物资类别 |
| warehouseCategory | String | 库别 |
| remark | String | 备注 |
| outStatus | Integer | 出库状态(1未出库,2已出库,3已退库) |

### 2.7 验收单主表 t_accept_main（核心：三段式验收主单，编号 YS-）

用途：到货后的验收主单（需求部→技术部→仓管部依次验收），记录到货单号（arrivalCode 即到货 DH- 单号）、合同与采购计划、三段验收人/时间，状态流转到"已验收"后进入验收确认（见 2.9）。

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Integer | 主键ID(@TableId) |
| arrivalCode | String | 到货单编号（指向 t_purchase_main 的 DH 到货单） |
| acceptCode | String | 关联单据编号（本单编号，YS- 前缀，由系统生成） |
| planName / planNumber | String | 采购计划名称 / 采购计划编号 |
| contractName / contractNumber | String | 合同名称 / 合同编号 |
| materialCategory | String | 物资种类 |
| totalPriceWithTax | BigDecimal | 含税总价 |
| totalPriceWithoutTax | BigDecimal | 不含税总价 |
| arrivalTime | Date(java.util) | 到货时间 |
| acceptTime | Date(java.util) | 验收时间 |
| acceptAddress | String | 验收地址 |
| acceptType | Integer | 验收类型(字典-1仓管直接验收 2远程验收 3三方到场直接验收) |
| status | Integer | 状态(字典-1待验收 2验收中 3已验收 4已拒绝) |
| demandUserId | Long | 需求部门验收人员用户ID |
| demandChecker | String | 需求部门验收人员名称 |
| demandCheckerId | String | 需求部门ID |
| demandCheckTime | LocalDateTime | 需求部验收时间 |
| techUserId | Long | 技术部验收人员用户ID |
| techChecker | String | 技术部验收人员名称 |
| techCheckerId | String | 技术部门ID |
| techCheckTime | LocalDateTime | 技术部验收时间 |
| warehouseUserId | Long | 仓管部验收人员用户ID |
| warehouseChecker | String | 仓管部验收人员名称 |
| warehouseCheckerId | String | 仓管部门ID |
| warehouseCheckTime | LocalDateTime | 仓管部验收时间 |
| remark | String | 备注 |
| trackingId | String | 代码中无注释（进度跟踪id，与其它表一致推测） |

### 2.8 验收明细 t_accept_detail

用途：验收单物资明细，含到货/合格数量与验收结果。表结构 = 主键/外键 + 标准快照列 + 下表差异列：

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Integer | 主键ID(@TableId) |
| acceptMainId | Integer | 验收单主表ID（→ t_accept_main.id） |
| arrivalQty | BigDecimal | 到货数量 |
| qualifiedQty | BigDecimal | 合格数量 |
| taxRate | BigDecimal | 税率 |
| arrivalTime | LocalDateTime | 到货时间 |
| acceptResult | Integer | 验收结果(字典-1合格 2不合格 3部分合格) |
| acceptImages | String | 物资验收图片URL |
| 标准快照列 | — | materialName/materialCode/specModel/material/drawingNo/price/priceExcludeTax/unit/supplier/demandDept/expensesListed/warehouseName/shelfName/warehouseId/shelvesId/warehouseCategory/materialType/remark |

### 2.9 验收确认主表 t_confirm_main（核心）

用途：验收"终验确认"，一条验收单可生成一条确认单（acceptMainId 关联），记录最终验收结果与累计不合格数量；确认完成后由本模块生成入库单（RK）。注意本表仅继承 BaseDO，代码中无 tenant_id（验收明细 t_accept_detail 却有租户列，属代码不一致点）。

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Integer | 主键ID(@TableId) |
| acceptMainId | Integer | 物资验收主表ID（→ t_accept_main.id） |
| arrivalCode | String | 到货单编号 |
| acceptCode | String | 关联单据编号 |
| planName / planNumber | String | 采购计划名称 / 采购计划编号 |
| contractName / contractNumber | String | 合同名称 / 合同编号 |
| materialCategory | String | 物资种类 |
| totalPriceWithTax | BigDecimal | 含税总价 |
| totalPriceWithoutTax | BigDecimal | 不含税总价 |
| arrivalTime | LocalDateTime | 到货时间 |
| acceptTime | LocalDateTime | 验收发起时间 |
| confirmTime | LocalDateTime | 最终验收日期 |
| acceptAddress | String | 验收地址 |
| acceptResult | Integer | 验收结果：1合格 2不合格 3部分合格 |
| unqualifiedQuantity | Long | 累计不合格数量 |
| acceptType | Integer | 验收类型(1仓管直接验收 2远程验收 3三方到场验收) |
| status | Integer | 状态(字典-1未验收 2需求部 3技术部 4仓管部 5已验收 6已拒绝) |
| demandUserId | Long | 需求部门验收人员用户ID |
| demandChecker | String | 需求部门验收人员名称 |
| demandCheckerId | String | 需求部门ID |
| demandCheckTime | LocalDateTime | 需求部验收时间 |
| demandCheckResult | String | 需求部门验收结果：验收意见文本 |
| techUserId | Long | 技术部验收人员用户ID |
| techChecker | String | 技术部验收人员名称 |
| techCheckerId | String | 技术部部门ID |
| techCheckTime | LocalDateTime | 技术部验收时间 |
| techCheckResult | String | 技术部验收结果：验收意见文本 |
| warehouseUserId | Long | 仓管部验收人员用户ID |
| warehouseChecker | String | 仓管部验收人员名称 |
| warehouseCheckerId | String | 仓管部部门ID |
| warehouseCheckTime | LocalDateTime | 仓管部验收时间 |
| remark | String | 备注 |
| trackingId | String | 代码中无注释 |

### 2.10 验收确认明细 t_confirm_detail

用途：确认单可勾选多条验收明细生成（acceptDetailId 关联验收明细），物资快照字段基本同验收明细。差异列：

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Integer | 主键ID(@TableId) |
| confirmMainId | Integer | 验收确认主表ID（→ t_confirm_main.id） |
| acceptDetailId | Integer | 物资验收明细ID（→ t_accept_detail.id） |
| arrivalQty / qualifiedQty | BigDecimal | 到货数量 / 合格数量 |
| taxRate | BigDecimal | 税率 |
| acceptResult | Integer | 验收结果(字典-1合格 2不合格 3部分合格) |
| acceptImages | String | 物资验收图片URL |
| 标准快照列 | — | 同 2.8 所列（materialName…materialType/remark） |

### 2.11 入库单主表 t_inbound_main（核心：入库单据，编号 RK-）

用途：入库业务主单。入库类型覆盖采购入库、调拨归还、物资退库（退库单生成）、报废入库、盘盈等；验收确认通过后即生成 RK 入库单；入库完成把物资写入 t_bound_main 并在 t_bound_detail 记入库流水。`returnId` 记录退库来源，`acceptCode` 记录关联单据编号（退库场景实测填的是退库单 RT 单号）。

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Integer | 主键ID(@TableId) |
| inboundCode | String | 入库单编号（RK-，系统生成） |
| acceptCode | String | 关联单据编号（退库入库场景 = 退库单号 returnCode） |
| planName / planNumber | String | 采购计划名称 / 采购计划编号 |
| contractName / contractNumber | String | 合同名称 / 合同编号 |
| totalPriceWithTax | BigDecimal | 入库总金额(含税) |
| totalPriceWithoutTax | BigDecimal | 入库总金额(不含税) |
| inboundPerson | String | 入库人 |
| inboundUserId | Long | 入库人用户ID |
| inboundTime | LocalDateTime | 入库时间 |
| acceptAddress | String | 入库地点 |
| acceptTime | LocalDateTime | 验收时间 |
| inboundType | Integer | 入库类型(1采购入库 2调拨归还入库 3物资退库 4报废入库 5盘盈入库 6盘盈出库) |
| status | Integer | 状态(1待入库 2已入库 3入库中) |
| remark | String | 备注 |
| operationType | Integer | 入库方式：1直接入库 2RFID打印入库 |
| returnId | Integer | 退库单id（→ t_return_main.id） |
| trackingId | String | 进度跟踪id |

### 2.12 入库单明细 t_inbound_detail

用途：入库物资明细，明确落位仓库/货架并带入库单价税金。差异列（含标准快照列）：

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Integer | 主键ID(@TableId) |
| inboundId | Integer | 入库单主表ID（→ t_inbound_main.id） |
| taxRate | BigDecimal | 税率 |
| qualifiedQty | BigDecimal | 合格数量 |
| materialImages | String | 物资图片URL |
| trackingId | String | 进度跟踪id |
| 标准快照列 | — | materialName/materialCode/specModel/material/drawingNo/price/priceExcludeTax/totalPrice含税总价/totalPriceExcludeTax不含税总价/unit/supplier/demandDept/expensesListed/warehouseName/warehouseId/shelvesId/warehouseCategory/shelfName/materialType/remark |

### 2.13 出库单主表 t_outbound_main（核心：出库单据，编号 CK-）

用途：出库/领用主单，领用、调拨、盘亏、报废处置共用 CK 前缀，以 `types` 区分；审批状态与出库状态分离（审批通过≠已出库，前端只展示 status=2 的记录）；报废处置出库由报废明细处置时生成（types=5）。

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Integer | 主键ID(@TableId) |
| outboundCode | String | 出库单编号（CK-，系统生成） |
| outboundName | String | 出库单名称 |
| applyTime | LocalDateTime | 申请日期 |
| applyDept | String | 申请人部门 |
| applyPerson | String | 申请人 |
| applyUserId | Long | 申请人用户ID |
| outTime | LocalDateTime | 出库日期 |
| approvalStatus | Integer | 审批状态(字典)：1待审批 2审批中 3审批通过 4审批不通过 5已退回 6已取消 |
| totalPriceWithTax | BigDecimal | 入库总金额(含税)（注释如此，实为出库总额） |
| totalPriceWithoutTax | BigDecimal | 入库总金额(不含税) |
| purpose | String | 用途 |
| address | String | 领用地点 |
| instanceId | String | 审批实列ID |
| taskId | String | 任务ID |
| types | Integer | 出库类型：1正常领用 2紧急领用 3调拨出库 4盘亏出库 5报废出库 6临时领用 |
| status | Integer | 状态(1未出库 2已出库) |
| remark | String | 备注 |
| belongUnit | String | 调拨物资所属单位 |
| phone | String | 调拨物资联系方式 |
| outPerson | String | 出库人员 |
| outUserId | Long | 出库人用户ID |
| outType | Integer | 出库种类:(1普通仓库出库 2无人值守仓库出库) |
| startTime / endTime | LocalDateTime | 预约领用开始 / 结束时间 |
| isTimeOut | Integer | 是否预约超时(0未预约 1未超时 2已超时) |
| photo | String | 预约图片 |
| trackingId | String | 进度跟踪id |

### 2.14 出库单明细 t_outbound_detail

用途：出库物资明细；出库时从库存流水 t_bound_detail 选批次扣减（inDetailId 存被扣流水的 id，inboundCode 存该批次的入库单号，多个逗号分隔），并回写安装/退库/报废数量。差异列（含标准快照列）：

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Integer | 主键ID(@TableId) |
| outboundId | Integer | 出库单主表ID（→ t_outbound_main.id） |
| inDetailId | Integer | 入库流水id（实测存 t_bound_detail.id，即被出库的库存批次） |
| boundMainId | Integer | 在库物资id（→ t_bound_main.id） |
| inboundCode | String | 入库单编号(多个使用英文逗号隔开) |
| taxRate | BigDecimal | 税率 |
| openingQuantity | BigDecimal | 库存数量（注释如此） |
| currentQuantity | BigDecimal | 领用数量 |
| closingQuantity | BigDecimal | 剩余数量 |
| purpose | String | 用途 |
| outboundName | String | 出库单名称 |
| installQuantity | BigDecimal | 已安装数量 |
| uninstallQuantity | BigDecimal | 未安装数量 |
| returnClosingQuantity | BigDecimal | 退库剩余数量 |
| contractNumber | String | 合同编号 |
| shareCode | String | 共享编号 |
| wasteQuantity | BigDecimal | 已报废数量 |
| 标准快照列 | — | materialName/materialCode/specModel/material/drawingNo/price/priceExcludeTax/unit/totalPrice含税总价/totalPriceExcludeTax不含税总价/supplier/demandDept/expensesListed/warehouseId/warehouseName/warehouseCategory/shelvesId/shelfName/materialType/remark |

### 2.15 废旧报废单主表 t_waste_main（核心：报废单据，编号 BF-）

用途：报废申请审批单。审批通过只更新状态（status=3 审批通过、warehousedStatus=2），**不自动生成出库**；真正的"报废出库单+明细+流水"在废旧台账对明细做"处置"时生成（见 2.17）。

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Integer | 主键ID(@TableId) |
| wasteName | String | 报废名称 |
| wasteCode | String | 报废编号（BF-，系统生成） |
| types | Integer | 物资种类（代码中无注释） |
| reason | String | 报废原因 |
| surveyReportName | String | 鉴定报告名称 |
| surveyReport | String | 鉴定报告URL |
| pictureUrl | String | 图片url |
| status | Integer | 审批状态(字典)：1待审批 2审批中 3审批通过 4已驳回 |
| warehousedStatus | Integer | 入库状态(字典)：1未入库 2已入库 |
| instanceId | String | 审批实例ID |
| taskId | String | 审批任务ID |
| proposer | String | 申请人 |
| department | String | 申请部门 |
| remark | String | 备注 |

### 2.16 报废明细 t_waste_detail

用途：报废单物资明细，登记来源（在库/出库/无批次）并锁定可报废数量（创建报废单时从 t_bound_main.availableQuantity 划入 wasteQuantity，不足报 1192 错误）。

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Integer | 主键ID(@TableId) |
| mainId | Integer | 主表ID（→ t_waste_main.id） |
| materialName | String | 物资名称 |
| materialCode | String | 物资编码 |
| specModel / material / drawingNo | String | 规格型号 / 材质 / 图号 |
| materialType | String | 物资类别 |
| sourceType | Integer | 来源类型(字典)1在库 2出库 3无批次 |
| sources | String | 来源（在库场景存"仓库名-货架名"下拉值，出库场景存出库来源标识） |
| unit | String | 单位 |
| lables | String | 在库物资：仓库ID+货架ID；出库：出库明细ID；无批次：无 |
| canWasteNum | BigDecimal | 可报废数量 |
| wasteNum | BigDecimal | 报废数量 |
| storageAddress | String | 存放地址 |
| remark | String | 备注 |
| status | Integer | 状态:0未处置 1已处置 |

### 2.17 报废处置 t_waste_dispose

用途：报废明细的处置记录（一次处置一条明细），处置后生成 CK 报废出库单与出库明细、库存流水（出库单须置 status=2 且流水 outStatus=2，否则出库记录/出库清单页查不到）。

| 字段 | 类型 | 含义 |
|---|---|---|
| id | Integer | ID(@TableId) |
| detailId | Integer | 明细ID（→ t_waste_detail.id） |
| disposalWay | Integer | 处置方式:1拍卖 2招标 3直接销售 4销毁 5其他 |
| disposalWayOther | String | 处置方式其他描述 |
| disposalNum | BigDecimal | 处置数量 |
| receiver | String | 接收方 |
| contactPerson | String | 联系人 |
| contactPhone | String | 联系方式 |
| disposalTotal | BigDecimal | 处置总价 |
| fixtureDate | LocalDate | 成交日期 |
| fileName / fileUrl | String | 附件名称 / 附件地址 |
| remark | String | 备注 |

### 2.18 其余单据/台账关键字段（节选）

- **t_purchase_main（到货单，DH-）**：arrivalCode 到货单编号、orderNo 关联订单编号、contractName/contractNumber、planName/planNumber、category 物资种类、totalPriceWithTax/totalPriceWithoutTax、status 到货状态(1未到货 2部分到货 3全部到货)、estimatedArrivalTime 预计到货时间、trackingId。
- **t_purchase_detail**：mainId 到货单主表ID、标准快照列（drawingNumber 图号、warehouseName/shelvesName 名称冗余）、purchaseQuantity 采购数量、pendingQuantity 未到货数量、receivedQuantity 已到货数量、supplier 供应单位、taxRate 税率、expensesListed、demandDepartment 需求部门。
- **t_return_main（退库单，RT-）**：returnCode 退库单编号、outboundCode 出库单编号、returnTime 退库日期、returnDept/returnPerson、totalPriceWithTax/WithoutTax、approvalStatus 审批状态(同出库字典)、instanceId、status 状态(1未入库 2已入库)、remark（maintainer 为 @TableField(exist=false) 移动端展示字段）。
- **t_return_detail**：returnId（注释"退库单编号"，实测代码 `setReturnId(returnCode)` 存的是 RT 单号而非主表 id）、标准快照列、currentQuantity 领用数量、usageQuantity 使用数量、returnQuantity 退还数量、totalReturnQuantity 总退还数量、boundMainId 在库物资主ID、outboundDetailId（代码中无注释，按名称为出库明细ID）、identityIds（代码中无注释）。
- **t_movebound_main（移库，YK-）**：moveCode 移库编号、types 类型(1同仓 2跨仓)、reason 原因、docUrl 附件、status(1待移库 2移库中 3已移库)、approvalStatus、instanceId、taskId、remark。
- **t_movebound_detail**：mainId 移库主表ID、标准快照列、inventoryQuantity 库存数量、moveQuantity 移动数量、sourceWarehouseId/Name、sourceShelfId/Name（源仓库/货架）、targetWarehouseId/Name、targetShelfId/Name（目标仓库/货架）、boundMainId 在库物资主表ID、executed(0未执行 1已执行)、remark。
- **t_stock_main（盘点，PD-）**：stockCode 盘点编号、stockTask 盘点任务、stockTime、stockType(0在线盘点 1扫码盘点 2普通盘点)、warehouseRange 仓库范围(Long)、plantCount 计划盘点数量、usageCount 已盘数量、differCount 差异数量、differRow 差异行数、materialType、startTime/endTime、status(1已完成 2待盘点 3盘点中 4已取消)、normalStatus(1不显示盘点数量差异 2显示)、allConfirm(0未完成 1已完成)、operator、warehouseName。
- **t_stock_detail**：stockId 盘点id、materialId 物资id、boundId 在库物资主表id、标准快照列（含 code 条码、picture 图片）、inventoryQuantity 系统数量、usageQuantity 实盘数量、differQuantity 差异、differReason、handleTime 扫码时间、status(0未盘 1已盘)、handleStatus 审批状态(0未处理 1审批中 2已完成)、instanceId、supplier、expensesListed、price 含税单价、priceExcludeTax、differAmount 差异金额。
- **t_stock_file**：fileName/fileUrl/time/stockCode 盘点单号。
- **t_stock_identity**：rfidCode 物资Rfid编码、stockDetailId 盘点详情ID、status(0未盘到 1已盘到)。
- **t_material_identity（物资数字身份）**：identityId 数字身份唯一ID、inboundDetailId 在库物资入库明细ID、outboundDetailId 在库物资出库明细ID、status(1未打印 2已打印)、outStatus(0未出库 1已出库)、rfidCode、boundMainId 在库主表id；（materialName/materialCode/specModel/material/drawingNo/warehouseName/shelfName/supplier/contractNumber/planNumber/totalPriceWithTax 等为 @TableField(exist=false) 关联展示字段，不落库）。
- **t_material_shared（共享，GX-）**：shareCode、boundMainId 在库物资主ID、仓库/货架冗余列、标准快照列（drawingNumber 图号）、inventoryQuantity、shareQuantity 共享数量、sharedTime 共享截止时间、sharedUnit 共享单位、targetType(1全部厂家可见 2指定厂家可见)、targetUnit、supplier、expensesListed、warehouseCategory、sharedOperator、moreDescription、boundDetail（明细 JSON `[{"id":1,"num":2}]`，指 t_bound_detail 行与数量）、status(1共享中 2已停用)、lockQuantity 锁定数量、availableQuantity 可用数量。
- **t_material_install（安装登记，AZ-）**：outboundDetailId 出库明细id、标准快照列、installCode 安装编码、outboundName、installLocation 安装位置、person 负责人(存用户id)、installStartTime/EndTime/installTime、installQuantity 安装数量、installDetailLocation、installPerson 安装人员、photo/vedio、code 物资码、status(0未登记 1已登记)、trackingId。
- **t_material_repair（检修，WX-）**：materialCode/materialName/code 物资码、repairCode 检修编号、installLocation、description 故障描述、urgent(0一般 1紧急 2加急)、repairPerson 主要成员、repairTime 保修时间、photo/vedio、outDep(0本单位 1外部单位)、outDepName、repairStartTime/EndTime、person 负责人、status(0待处理 1处理中 2已完成)、content 检修内容、outboundName、handleStatus(2暂存 1已完成)。
- **t_bound_warning（库存预警）**：标准快照列、availableQuantity 当前库存、warningQuantity 预警阈值、warningType(1不足 2超储 3临期)、warningContent、operater、operateTime、operaterContent(1生成采购需求 2发起调拨申请 3标记为已处理)、status(0待处理 1已处理)。
- **t_maintenance_rule（维保规则）**：materialType/typeCode/materialName/materialCode（可空规则）、maintenanceDay 维保日期（天）、maintenanceTime 下一次维保日期、maintenanceMethod、maintenanceAlert 维保预警（天）、maintenanceFunction(0检修 1保养 2其它)、outDep(0是 1否 注释如此)、maintenanceDep 维保单位、contactPeople/contactNumber、status(0常规维保 1特殊维保)、parentId 分类id、maintenanceNumber 维保电话、maintenanceAddress 维保单位地址。
- **t_maintenance_alert（维保预警）**：materialId 维保物资id（→ t_bound_main.id 维度）、materialName/materialType、warehouseName/shelfName、miantenanceDay 维保周期（天）、miantenanceTime 下次维保日期、alertTime 预警时间、maintenanceMethod、outDep、miantenanceDep、miantenanceNumber、contactPeople、newMiantenanceTime 最新维保日期、alertContent 预警内容、status 预警状态(0正常 1即将到期 2已经到期)、maintenanceStatus 维保状态(0常规维保 1特殊维保)、remark。
- **t_miantenance_record（维保记录，注意表名拼写）**：materialId、miantenanceQuantity 维保数量、miantenanceDep/Number/Address、miantenanceDay、miantenanceReason、miantenanceTime 下次维保日期、status、remark、materialCode/materialName/specModel/material/drawingNo、creator。
- **t_review_rule（评价规则）**：ruleName、quality/service/price/delivery/compliance 五维权重、remark、status(1已启用 2已停用)。
- **t_review_record（评价记录）**：contractName、planName/planNumber、supplier、arrivalCode、arrivalTime、materialName/materialCode、arrivalQuantity、totalRevuew 综合评分、quality/service/price/delivery/compliance、description、fileUrl、status(1已评价 2待评价)、trackingId、acceptMainId 验收单主表ID、acceptDetailId 验收明细表ID、qualifiedQty、unit。
- **t_review_result（评价结果汇总）**：supplier、purchaseTotal 采购次数、reviewTotal 评价次数、totalRevuew、五维分、reviewRank 排名、reviewTime、status。
- **t_instance_code（审批单号映射）**：instanceId 审批实列ID、code 单据编号、types 审批类型（1出库审批 2退库审批 3废旧审批 4盘盈入库 5盘亏出库）。
- **t_export_template**：feature 功能标识（如 material.accept-detail）、targetTenantId 目标租户ID(0默认)、templateBean Spring Bean名、priority 优先级、enabled(0禁用 1启用)。
- **t_user_menu**：userId 用户id、menuList 菜单id字符串（menus 为 @TableField(exist=false) 数组）。
- **t_devices**：deviceType 设备类型（读写器等字典）、deviceModel/Brand、locationArea、ipAddress、types(如24口)、deviceName/Number/Purpose、warehouse 所属仓库、macAddress、outboundAntennaId/inboundAntennaId/checkAntennaId 出/入/盘点天线ID、portNumber、username/password、videoUrl、groupNumber 组号、channelNumber 信道号。
- **t_hardware_server**：id 主键id(租户id)、ipUrl ip地址、ipPord 端口、tenantId 租户编号、topic mqtt主题、sendTo 发送消息目标（格式 TO+地址拼音，如给广东:TOGuangDong，无注释列）。
- **t_provider（旧供应商）**：name/address/types(1生产商 2代理商 3施工企业 4服务企业)/postalCode/companyEmail/companyPhone/companyFax/contactName/contactPhone/contactEmail/products。
- **t_wz_contract（合同）**：tenantId、biddingId/biddingName 招标编号/名称、purchaserCode/Name 采购方、contractCode/Name 合同编号/名称、categoryCode/Name 品类、signedDatetime、valuationType(Code)、amount 合同金额、payType(Code)、startDatetime/endDatetime、performancePlace 履约地点、guaranteeType(Code)、note、contractSellerName/sellerSocialCreditCode 卖方、syncBatchNo/syncTime 同步批次与时间。
- **t_melc_purchase_order（外部采购订单同步）**：orderId 采购订单ID（String，@TableId INPUT 主键）、tenderId/tenderNo 采购单、orderNo/orderName 订单编号/名称、productCatalog 产品目录、tenderMethod/PurchaseType 采购方式/类型、purchaseCompanyId/Name 采购单位、supplierId/Code/Name 供应商、totalBudget/projectTotalBudget/orderTotalMoney/contractTotalMoney 各类金额(String)、orderStatus(00新增 01已确认 02审核中 03不通过 04待撤销 05已撤销)、planId/planNo、frameworkAgreementId/No、deliveryTime、contractName/contractCode（回填自 t_wz_contract）、extractStatus 提取状态(0未提取 1已提取)、purchaseMainId 关联物资到货主表ID、trackingId、syncBatchNo；（orderDetailList 不落库）。
- **t_melc_purchase_order_detail**：subjectMatterId 物料ID(String,主键)、orderId 订单ID、purchaseRequestNo/Name、demandUnit 需求单位、monthlyPlanId/Name、materialsNo/materialsName 物资编码/名称、specModel、materialQuality 材质、quantity、unit、sourceType 采购申请来源、lineNo、batchId、planType(01货物 02工程 03服务 04销售)、unitPrice、totalBudget、singleTotalOfferPrice 成交总价含税、taxUnitPrice 成交单价含税、taxRate、syncBatchNo。
- **t_melc_purchase_company_tenant**：purchaseCompanyId/Name 采购单位（对应订单 purchase_company_id）、tenantId 租户ID、remark。
- **直供 t_register_main**：registerBatch 登记批次号（按项目+乙方递增）、projectCode/Name、companyName 乙方企业、chargePerson/contactPhone、totalAmount 本次直供登记总金额、attachmentName/Url、registerUser、registerTime、status(1正常 2作废)。
- **直供 t_register_item**：registerId 直供登记主表ID、materialName/materialCode、spec 规格/材质/图号、unit、qty 直供数量、price、amount 合计金额、deliveryDate 交付日期、remark 备注/用途。
- **直供 t_writeoff_main（核销申请 HX-）**：writeoffApplyNo（审批通过后即核销批次编号）、projectCode/Name、companyName、periodType(1按月 2按季度)、periodValue(如2026-04或2026Q1)、voucherName 凭证名称、evidenceFiles 工程量证明文件JSON、drawingFiles 施工图纸文件JSON、applyUser、applyTime、passTime 审批通过时间(核销时间)、approvalRemark、status 审批状态字典同前、processInstanceId BPM流程实例ID。
- **直供 t_writeoff_item**：writeoffId 核销申请ID、registerItemId 来源直供登记明细ID、materialName/materialCode/spec/unit/deliveryDate、totalQty 直供总量、writtenQty 已核销数量、applyQty 本次申请核销数量、remainQty 剩余未核销数量、price、amount 本次核销金额、workDesc 工程量描述。
- **直供 t_writeoff_flow（核销流水）**：writeoffId、registerItemId、materialName/spec/unit/deliveryDate、beforeQty 核销前剩余、writeoffQty 本次核销、afterQty 核销后剩余、price、writeoffAmount、workDesc、writeoffUser 核销人、writeoffTime 核销时间。
- **直供 t_ledger_main（台账）**：projectCode/Name、totalAmount 直供物资总金额、writtenAmount 已核销金额、remainAmount 未核销金额、writeoffRate 核销率、writtenBatchCount 已核销批次数。

## 3. 表间关系

### 3.1 单据主表—明细表关联方式（全部为 ID 关联，明细冗余主表编号字段）

| 主表 | 明细表 | 关联列（明细→主表） | 备注 |
|---|---|---|---|
| t_purchase_main | t_purchase_detail | `mainId` → `t_purchase_main.id` | |
| t_accept_main | t_accept_detail | `acceptMainId` → `t_accept_main.id` | |
| t_confirm_main | t_confirm_detail | `confirmMainId` → `t_confirm_main.id` | |
| t_inbound_main | t_inbound_detail | `inboundId` → `t_inbound_main.id` | |
| t_outbound_main | t_outbound_detail | `outboundId` → `t_outbound_main.id` | |
| t_return_main | t_return_detail | `returnId` 存退库单**编号字符串**（代码 `setReturnId(returnCode)`） | 明细没有数值主表外键，靠单号字符串关联；另由 t_inbound_main.returnId 反向回指 |
| t_movebound_main | t_movebound_detail | `mainId` → `t_movebound_main.id` | |
| t_waste_main | t_waste_detail | `mainId` → `t_waste_main.id` | |
| t_waste_detail | t_waste_dispose | `detailId` → `t_waste_detail.id` | 处置明细 1:1 |
| t_stock_main | t_stock_detail | `stockId` → `t_stock_main.id` | |
| t_stock_detail | t_stock_identity | `stockDetailId` → `t_stock_detail.id` | RFID 逐标签盘点 |
| t_register_main | t_register_item | `registerId` → `t_register_main.id` | 直供登记 |
| t_writeoff_main | t_writeoff_item | `writeoffId` → `t_writeoff_main.id` | 直供核销 |
| t_writeoff_main | t_writeoff_flow | `writeoffId` → `t_writeoff_main.id` | 审批通过生成流水 |
| t_melc_purchase_order | t_melc_purchase_order_detail | `orderId` → `t_melc_purchase_order.order_id` | 字符串主键(order_id=订单ID) |

### 3.2 单据编号前缀→单据（由各 Service 的 NumberGenerator 调用证实）

| 前缀 | 落在哪张表哪个字段 | 业务单据 |
|---|---|---|
| DH | t_purchase_main.arrivalCode | 物资到货单（采购到货计划） |
| YS | t_accept_main.acceptCode | 验收单 |
| RK | t_inbound_main.inboundCode（退库入库、盘盈入库也生成 RK 入库单） | 入库单 |
| CK | t_outbound_main.outboundCode | 出库单（领用/调拨/盘亏/报废处置出库共用，types 区分） |
| RT | t_return_main.returnCode | 退库单 |
| YK | t_movebound_main.moveCode | 移库单 |
| BF | t_waste_main.wasteCode | 报废单 |
| PD | t_stock_main.stockCode | 盘点单 |
| AZ | t_material_install.installCode | 安装登记 |
| WX | t_material_repair.repairCode | 检修单 |
| GX | t_material_shared.shareCode | 共享单 |
| HX | t_writeoff_main.writeoffApplyNo（直供核销申请） | 直供核销 |
| Code | t_material_code.code | 物资编码（非单据） |
| LSZCK / MRHJ | t_warehouse.code / t_shelves.code | 系统临时仓库 / 默认货架（非单据） |

### 3.3 业务单据链（采购→到货→验收→入库→在库→出库）

```
外部采购订单 t_melc_purchase_order(同步) 
   → 到货单 t_purchase_main (DH, orderNo 关联订单; 提取生成)
   → 验收单 t_accept_main (YS, arrivalCode 引用到货单号 DH)
   → 验收确认 t_confirm_main (acceptMainId → t_accept_main.id; 明细 acceptDetailId → t_accept_detail.id)
   → 入库单 t_inbound_main (RK; ConfirmMainServiceImpl 生成; 退库场景 acceptCode=退库单号RT、returnId→退库主表id)
   → 在库 t_bound_main (入库完成生成/累加; 明细流水写 t_bound_detail, types=1, docNumber=RK单号)
   → 出库 t_outbound_main (CK; 明细从 t_bound_detail 选批次: inDetailId=被扣流水id、inboundCode=流水入库单号、boundMainId=在库主id)
       ├→ 安装登记 t_material_install (AZ, outboundDetailId)
       ├→ 退库 t_return_main (RT, outboundCode 引用原出库单) → 退库入库(RK, inboundType=3) 回库
       ├→ 移库 t_movebound_main (YK) 调整 t_bound_main 仓位
       ├→ 共享 t_material_shared (GX, boundMainId + boundDetail JSON) 锁定可用量
       ├→ 盘点差异: 盘盈生成 RK 入库 / 盘亏生成 CK 出库
       └→ 报废处置 t_waste_dispose → 生成 CK 出库单(types=5)+流水后回写
```
关键点：
- **在库主表是唯一的库存现状源**：数量语义 = 账面 `inventoryQuantity`、可用 `availableQuantity`（可领可借）、共享 `shardQuantity`、报废锁定 `wasteQuantity`；报废创建时从可用划入 wasteQuantity 锁定、处置时扣 wasteQuantity+inventoryQuantity；移库/退库/共享同样围绕这几个量加减。
- **库存批次/流水 t_bound_detail** 承载"哪一批物资"：`mainId`→在库主表，`inboundDetailId`→入库明细，`docNumber`=来源单据号，`types`(1入/2出/3退/4移)，`outStatus`(1未出库/2已出库/3已退库) 控制出库清单可见性（前端只展示已出库 status=2 的出库单，出库清单 SQL 排除 outStatus=1 流水）。
- **报废→出库的触发点**在废旧台账"处置"（WasteDetailServiceImpl.updateWasteDetail → createOutBoundInfo），不在审批环节（审批通过只改状态）。处置需把新出库单置 status=2 并把流水 outStatus=2，同时按 materialCode+仓库名+货架名 反查在库主记录（与创建报废单时锁定所用定位方式一致，lables 仅兜底）。
- 审核流（出库/退库/报废/盘盈亏）单据上冗余存 `instanceId`/`taskId`（BPM 流程实例/任务），`t_instance_code` 提供 instanceId↔单据编号(code) 反查，types=1出库审批/2退库/3废旧/4盘盈/5盘亏。

### 3.4 物资档案与在库、RFID 身份的关系

- t_material_code / t_material_type 是全租户共享的物资目录（@TenantIgnore），业务单据与在库记录上以**冗余文本**存 materialCode/materialName/specModel/materialType 快照，未在代码中见到强外键约束，回查档案按编码串匹配。
- t_material_identity（RFID 数字身份）通过 `boundMainId`→t_bound_main、`inboundDetailId`→t_inbound_detail、`outboundDetailId`→t_outbound_detail 把"一物一码/一类一码"标签串到出入库轨迹；盘点按 rfidCode 逐标签核对（t_stock_identity）。
- t_shelves.warehouseId → t_warehouse.id（货架挂仓库）；在库/单据上另冗余 warehouseId+warehouseName、shelvesId+shelfName（定位键 = 仓库名+货架名+物资编码，多处业务按此三要素反查在库记录）。

### 3.5 租户 / 用户（system 侧）关系

本模块不落 system 用户/租户表，仅以 ID/编号弱关联（yudao 多租户体系，system 侧典型表为 system_tenant、system_users）：
- **租户隔离**：业务数据表（t_bound_main、t_inbound_*、t_outbound_*、t_accept_*、t_waste_*、t_purchase_main、t_material_install/repair、维保 rule/alert、t_review_record、t_export_template 等）继承 TenantBaseDO 带 `tenant_id`，mybatis-plus 自动追加租户条件。**例外**：t_confirm_main/detail、t_warehouse、t_shelves、t_stock_*、t_return_*、t_movebound_*、t_material_type/identity/shared、t_devices、t_review_rule/result 等仅 BaseDO 无租户字段；直供（t_register_*、t_writeoff_*、t_ledger_main）、物资目录 t_material_code、t_wz_contract、供应商 t_wz_supplier_*、采购单位映射、t_instance_code 打 @TenantIgnore 全租户共享（直供按"项目+乙方"跨租户核算，台账一项目一行）。
- **租户相关辅助表**：t_melc_purchase_company_tenant 把外部"采购单位ID"映射成本系统 tenant_id，供采购订单同步回填；t_hardware_server 每租户一套硬件服务配置（主键即租户维度）；t_export_template.targetTenantId=0 表示默认模板、>0 按租户覆盖。
- **用户弱关联（均指向 system_users.id）**：BaseDO.creator/updater（注释"目前使用 SysUser 的 id"）、单据操作人：t_inbound_main.inboundUserId、t_outbound_main.applyUserId/outUserId、t_accept_main.demandUserId/techUserId/warehouseUserId、t_material_install.person（存用户id）、t_review_record 等。t_user_menu.userId 存用户选中的菜单 id 串（menuList），属用户个性化配置。

### 3.6 其它值得注意的代码事实

1. `t_return_detail.returnId` 与主表 `t_return_main.returnCode` 同为单号字符串（实测代码写入 returnCode），并非主表数值 id；而同链路 `t_inbound_main.returnId`(Integer) 才是指向 t_return_main.id 的外键。
2. 表名/字段拼写照代码原样：`t_miantenance_record`（maintenance 拼错）、`totalRevuew`(应为 review)、`shardQuantity`(应为 shared)、`warehousedStatus`、`operater`/`operaterContent`、`belongUnit` 等，检索/建表请以实际为准。
3. mapper XML（resources/mapper/*.xml）未发现跨表 JOIN，复杂汇总（出库清单、台账、驾驶舱等）由 Java Service 层分步查询组装完成。


---

## 第三部分：前端功能结构（第 7 章）

> **代码库**：`D:\idea\materials_web`（前端）。包名 `yudao-ui-admin-vue3` v2.6.0-snapshot，即基于**芋道 yudao 开源后台（Vue3 版）**二开的物资仓储系统。
> **口径说明**：本知识全部来自对上述代码的真实抽样（package.json、views/api/router/store/utils 关键文件、material 全部业务目录的页面标签与按钮提取、出库/报废/盘点三页逐行阅读）。凡属推断处均标注「不确定」，不编造。
> **抽样策略**：先列 `src/views/material` 61 个业务子目录→再对每个目录的 `index.vue` 做标签/按钮关键词提取→再读 `src/api/material` 全部 36 个接口文件的 VO 注释与 URL 前缀→最后深读 出库单、报废单（主表+台账+处置）、盘点 三个典型页面的关键实现。

---

## 1. 前端技术栈与整体结构

### 1.1 技术栈（据 package.json）
| 分类 | 选型 |
|---|---|
| 框架 | Vue 3.5.12 + TypeScript 5.3.3，`<script setup>` 单文件组件 |
| 构建 | Vite 5.1.4；多环境脚本 `vite --mode env.local/dev/test/stage/prod`（`.env`/`.env.dev`/`.env.local`/`.env.stage`/`.env.test`/`.env.prod`）；产物构建 `build:xxx = node --max_old_space_size=4096 vite build` |
| UI | element-plus 2.9.1 + @element-plus/icons-vue；unocss 原子类（模板中常见 `!w-240px`、`mr-5px` 等）；自动按需加载：unplugin-auto-import、unplugin-vue-components、unplugin-element-plus |
| 状态 | Pinia 2.1.7（store/modules：app、dict、locale、lock、permission、tagsView、user）+ pinia-plugin-persistedstate |
| 路由 | vue-router 4.4.5，history 模式（createWebHistory，base=`VITE_BASE_PATH`） |
| HTTP | axios 1.9.0，封装在 `src/config/axios`；api 文件统一 `import request from '@/config/axios'` |
| 其它重依赖 | echarts、@wangeditor、bpmn-js 17.9（流程设计器）、@form-create（表单设计）、vue-i18n 9.10、@vueuse/core、qrcode、markmap、driver.js（引导）、video.js 等 |

### 1.2 src 顶层结构
`api`（后端接口封装，按模块目录镜像后端）、`assets`、`components`（通用组件库）、`config`（axios 等）、`directives`（权限指令）、`hooks`（useMessage/useI18n/useHardware 等）、`layout`（主框架布局）、`locales`（i18n）、`plugins`、`router`、`store`（pinia）、`styles`、`types`、`utils`、`views`（页面，一级目录=bpm/infra/material/system + Home/Login/Profile/Redirect/Error）。

### 1.3 HTTP 请求封装约定
- api 文件定义 `export interface XxxVO`（字段名即后端 VO，中文注释标语义）+ `export const XxxApi = {…}`。
- 方法命名/URL 五件套约定：`page`(GET 分页 `?params`)、`get`(GET `?id=`)、`create`(POST)、`update`(PUT)、`delete`(DELETE)、`export-excel`(经 `request.download`)，业务扩展点另加（如 `initiate`、`confirm`、`dispose`）。
- 后端统一前缀 **`/material/*`**（见第 2 节每模块）。
- 前端导出 Excel：`request.download` 拿 blob → `utils/download` 的 `download.excel(data, '文件名.xls')`；导出前常 `await message.exportConfirm()` 二次确认。

### 1.4 前端通用组件/能力约定（yudao 风格，页面里到处复用）
| 组件/工具 | 用途 |
|---|---|
| `ContentWrap` | 卡片容器：搜索栏一个、表格一个 |
| `Dialog` | 弹窗基座（title/v-model/footer 插槽） |
| `Pagination` | 分页（pageNo/pageSize，事件 pagination） |
| `DictTag` + `DICT_TYPE`（`src/utils/dict.ts`） | 字典渲染，如 `<dict-tag :type="DICT_TYPE.MATERIAL_APPROVAL_STATUS" :value="row.status"/>` |
| `Icon` | iconify 图标 `<Icon icon="ep:search"/>` |
| `UploadFile`/`UploadImgs` | 附件/图片上传组件（多返回 URL） |
| `v-hasPermi` / `v-hasRole` | 按钮权限指令（directives/hasPermi.ts、hasRole.ts） |
| `useMessage()` | 成功/错误提示与 `delConfirm()`、`exportConfirm()` 二次确认 |
| `dateFormatter/dateFormatter2` | `src/utils/formatTime` 日期列格式化 |
| 搜索区 | `el-form inline` + queryParams(reactive) + `handleQuery`/`resetQuery`，`ref="queryFormRef"`，输入框回车触发搜索 |
| 全局自动导入 | ref/reactive/defineOptions/`useMessage`/`useI18n`/`Icon` 等无需显式 import（unplugin-auto-import/全局注册），页面 <script setup> 内直接可用 |

### 1.5 页面组件命名与"打开弹窗"约定
每个业务目录通常含 `index.vue`（列表页）+ `XxxForm.vue`（新增/编辑弹窗）+ `DetailForm.vue`/`detail.vue`/`WasteMainDetail.vue`（详情弹窗）。子弹窗组件约定：内部维护 `dialogVisible/dialogTitle/formType(formLoading)`；对外 `defineExpose({ open })`；`open(type, id?)` 由列表页 `openForm('create'|'update', id)` 触发；操作成功 `emit('success')` 让列表页刷新。详情类由 `showDetailDialog(res)` 或 `open(id)` 触发。

### 1.6 状态/字典驱动 UI 的通用模式（务必记住，RAG 高频命中点）
多业务主单共用同一套"**审批状态 + 业务状态**"双状态字段与字典数字：
- `approvalStatus/status`：**1 待审批 2 审批中 3 审批通过 4 已驳回**（出库单 VO、报废单 VO 注释原文），字典 `approval_status`（`DICT_TYPE.MATERIAL_APPROVAL_STATUS`）；
- 业务状态字段各自定义，如出库 `status`(1 未出库/2 已出库)、报废 `warehousedStatus`(1 未入库/2 已入库，字典 `waste_inbound_status`)、盘点 `status`(1 已完成/2 待盘点/3 盘点中/4 已取消)。
- **按钮显隐 = `v-if` 状态条件 + `v-hasPermi` 权限串**，行内操作多为 `el-button link`。
- "发起审批"模式：行按钮仅当 `status===1`（待审批）显示 → 调 `XxxApi.initiateApproval({id})`（部分带 `types`）→ 后端返回 instanceId/taskId，之后审批动作发生在 BPM 侧，页面通过隐藏路由进入审批详情（见 4 节 remaining.ts）。

---

## 2. 功能模块清单（重点 material，全部 10 个业务域）

> 页面目录=`src/views/material/...`，接口目录=`src/api/material/...`；「主要操作按钮」为对目录 index.vue 提取的真实按钮词。

### 2.1 总览
| 一级目录 | 职责（据目录+API VO 注释） | 页面子目录数 | 接口 URL 前缀（抽样全量） |
|---|---|---|---|
| standard | 基础档案：物资编码/类别/仓库/货架/供应商/设备 | 6(+bpmtest) | `/material/code`、`/type`、`/warehouse`、`/shelves`、`/provider`(/wz)、`/devices`、`/bpm-test` |
| arrival | 采购订单→到货→验收→验收确认 | 4 | `/material/purchase-order`(+data-sync)、`/purchase-main`、`/purchase-detail`、`/accept-main`、`/accept-detail`、`/confirm-main` |
| warehouseIn | 入库（直接入库/转临时资产/RFID）、入库记录、退库 | 5 | `/material/inbound-main`、`/return-main`、`/return-detail` |
| warehouseing | 在库管理：在库物资台账/资产、库存预警、移库、共享、**盘点**、复核 | 6 | `/material/bound-main`、`/bound-warning`、`/movebound-main`、`/material-shared`、`/stock-main`、`/driver`(驾驶舱) |
| warehouseOut | 出库：正常领用/紧急/临时/调拨/物资出库/出库清单/出库记录 | 7 | `/material/outbound-main`、`/outbound-detail` |
| waste | 废旧报废单(主+明细) + 报废台账/处置 | 2 | `/material/waste-main`、`/waste-detail` |
| directSupply | 直供物资（登记/核销/核销管理） | 3 | `/material/direct-supply` |
| maintenance | 维保预警/维保记录/维保规则 | 3 | `/material/maintenance-alert`、`/miantenance-record`(注意拼写)、`/maintenance-rule` |
| usage | 物资使用：条码/数字身份、安装登记、检修(报修) | 3 | `/material/material-identity`、`/material-install`、`/material-repair` |
| review | 供应商评价：评价记录/评价结果(月度季度年度报告)/评价规则 | 3 | `/material/review-record`、`/review-result`、`/review-rule` |
| 其它 | usermenu(首页快捷菜单)、warehouse/driver(驾驶舱) | — | `/material/menu`、`/material/app`、`/material/driver` |

### 2.2 standard 基础档案（供所有业务下拉引用）
| 功能 | 页面 | 主要按钮/要点 | 接口 |
|---|---|---|---|
| 物资编码 | `standard/code` | 搜索(物资编码/名称/分类)；新增/详情/编辑/删除 | `/material/code` |
| 物资类别 | `standard/type` | 类别名称/编码/状态；新增/详情/编辑/删除 | `/material/type` |
| 仓库 | `standard/warehouse` | 仓库编码/名称/位置/状态；新增/编辑/删除；表单含 `isHardware` 开关逻辑（设备仓） | `/material/warehouse`（下拉常用 `getWarehouseList`） |
| 货架 | `standard/shelves` | 货架编号/名称/所属仓库/位置；增删改查 | `/material/shelves` |
| 供应商 | `standard/provider` | 供应商名称/性质/注册地/联系人；增删改查 | `/material/provider`、`/material/wz` |
| 设备 | `standard/devices` | 设备名称/编号/型号/类型；增删改查 | `/material/devices` |
| （流程测试） | 仅接口存在 `standard/bpmtest`，未见对应视图目录 | 不确定是否被页面引用 | `/material/bpm-test` |

### 2.3 arrival 采购到货与验收（链式业务：采购订单→到货→验收→验收确认→入库）
| 功能 | 页面 | 主要按钮/要点（真实提取） | 接口模块 |
|---|---|---|---|
| 采购订单 | `arrival/purchaseOrder`（index/detail/importForm） | 按 签约单位/合同名称/订单编号/状态 查询；查询/重置/刷新数据/详情/**提取采购清单** | `/material/purchase-order`、`/material/data-sync` |
| 到货单 | `arrival/purchasemain`（index/detailIndex/mainDetail/AcceptInfo/purImportForm） | 到货单编号/合同名称；导入/**确认到货**/详情/验收记录；到货状态：未到货/部分到货 | `/material/purchase-main`、`/purchase-detail` |
| 到货详情页 | 隐藏路由 `/purchasedetailIndex`（PurchaseDetail，指向 detailIndex.vue） | remaining.ts 注册，详情查看用 | 同上 |
| 验收单 | `arrival/acceptmain`（index/IitiateeAcceptance/detailIndex） | 验收单编号/关联单据编号；**发起验收**/再次发起/详情/下载 | `/material/accept-main`、`/accept-detail` |
| 验收确认 | `arrival/acceptconfirm`（index/acceptanceConfirm/confirmDetail） | 关联单据编号/合同名称/到货时间；**验收确认**/详情 | `/material/confirm-main` |

> 判断：验收确认后进入入库环节（warehouseIn）。验收通过→入库的准确字段联动在验收确认表单组件 `acceptanceConfirm.vue` 中，本次未深读其提交字段，**不确定**。

### 2.4 warehouseIn 入库与退库
| 功能 | 页面 | 主要按钮/要点 | 接口模块 |
|---|---|---|---|
| 入库（执行） | `warehouseIn/inbound`（index/inboundOperation/inboundDetail） | 入库单编号/合同名称；**转临时资产、直接入库、RFID 打印**（`v-show="(status===1||status===3)&&isHardware"`，硬件受租户开关控制）；导出 | `/material/inbound-main` |
| 入库单列表(批次明细) | `warehouseIn/inboundList` | 物资编码/名称/单据编号/入库日期；导出/**确认出库**/详情 —— 具体业务角色**不确定**（同目录下同时出现"确认出库"按钮，疑似入库后的出库执行清单） | `/material/inbound-main` |
| 入库记录 | `warehouseIn/inboundRecord`（index/inboundDetail） | 待入库/已入库 状态筛选；详情/下载（历史只读） | `/material/inbound-main` |
| 退库单 | `warehouseIn/returnmain`（index/initiateApprovalDetail/ReturnDetailForm/ReturnMainForm） | 退库单编号/原领用单编号/退库部门/退库人；**新增退库、确认入库、发起审批**、详情 | `/material/return-main`、`/return-detail` |
| 退库明细 | `warehouseIn/returndetail`（index/ReturnDetailForm） | 物资维度明细管理：新增/编辑/删除/导出 | `/material/return-detail` |

### 2.5 warehouseing 在库/仓储（核心在库数据 + 盘点）
| 功能 | 页面 | 主要按钮/要点 | 接口模块 |
|---|---|---|---|
| 在库物资/资产台账 | `warehouseing/asset`（index/assetDetail/assetWater/assetShared/warningConfig） | 物资名称/编码/仓库/类别；**库存值预警配置**、导出、详情、**共享**；含流水(assetWater)与共享子页 | `/material/bound-main` |
| 库存预警 | `warehouseing/boundwarning`（index/WarningDetail/WarningOperate） | 预警记录 待处理/已处理；**批量生成采购需求、标记为已处理、生成采购需求**、导出Excel | `/material/bound-warning` |
| 移库 | `warehouseing/moves`（index/MoveboundMainForm/MoveboundExecuteDialog/initiateApprovalDetail/MoveboundMainDetail） | 移库类型：**同仓移库/跨仓移库**；**移库申请、发起审批、执行移库**、导出 | `/material/movebound-main` |
| 物资共享 | `warehouseing/shared`（index/SharedForm/SharedDetail） | 共享单位维度；**新增共享**、编辑、详情、导出 | `/material/material-shared` |
| 盘点（重点，见 3.3） | `warehouseing/stock`（index/StockMainForm/StartForm/NormalStartForm/DetailForm/ReportForm/SwatchForm/purImportForm/initiateApprovalDetail） | 盘点类型：0 在线盘点/1 扫码盘点(前端选项已注释)/2 普通盘点；新增盘点任务/开始盘点/继续盘点/取消盘点/盘点详情/盘点报告/差异填报/导出清单 | `/material/stock-main`（含 check-status/stop/confirm/confirm-more/initiate/initiate-out/导出/文件上传等扩展点） |
| 在库复核页 | `warehouseing/review` | 查询用 bound-main 接口，页面含 新增/编辑/删除 —— 与"复核"菜单的业务语义**不确定**（`src/api/material/review` 下另有"评价"模块，勿混淆：前者供应商评价、后者在库复核页面） | 复用 `/material/bound-main` |

> 提醒区分两个 `review`：`views/material/review`(供应商评价，见 2.10) vs `views/material/warehouseing/review`(在库复核页，调 bound-main)。

### 2.6 warehouseOut 出库（出库单主 outbound-main 一张表，前端按类型分页面呈现）
| 功能 | 页面 | 主要按钮/要点（真实提取） | 接口模块 |
|---|---|---|---|
| 正常领用出库 | `warehouseOut/outbound`（index/OutboundMainForm/detailForm/OutboundHandleForm/initiateApprovalDetail） | 领用编号/领用日期；**新增领用、发起审批、详情、下载、预约领取/重新预约/查看预约信息**（预约三态按钮）；列表过滤 `types!==2`（即不含紧急） | `/material/outbound-main`、`/outbound-detail` |
| 紧急出库 | `warehouseOut/urgent`（index/OutboundMainForm/detailForm） | 新增领用/发起审批/确认出库/详情/下载；行内含 `isHardware` 判断 | 同 outbound-main |
| 临时领用 | `warehouseOut/tempOutbound`（index/OutboundMainForm/detailForm） | 新增临时领用/发起审批/详情/下载 | 同 outbound-main |
| 调拨出库 | `warehouseOut/allocation`（index/detailForm） | 调拨申请编号/单位；**确认出库**/详情/下载 | 同 outbound-main |
| 物资出库（执行页） | `warehouseOut/materialOutbound`（index/confirm.vue） | 出库单编号/出库状态(未出库/已出库)；**确认出库**（confirm.vue 明细级逐条确认出库）/详情 | 同 outbound-main |
| 出库清单 | `warehouseOut/outboundList`（index/detailForm） | 物资编码/名称/单据编号/出库日期/仓库；**确认出库**/导出/详情（=物料维度的出库流水） | `/material/outbound-main`(outboundList-page/export-outboundList-excel) |
| 出库记录 | `warehouseOut/outboundRecord`（index/OutboundDetailForm） | 出库单编号/状态；详情/下载（历史只读） | 同 outbound-main |

> 页面与 API 存在**新旧两套同名目录**：`api/material/outbound/outboundmain`（独立、较旧五件套）与 `api/material/warehouse/outbound`（页面实际 import 的、扩展最全）。页面 import 证据：`warehouseOut/*` 各页均 `from '@/api/material/warehouse/outbound'`。旧目录是否仍被引用**不确定**（建议检索时以 `warehouse/outbound` 为准）。

### 2.7 waste 废旧报废（主表申请审批 + 台账处置出库）
| 功能 | 页面 | 主要按钮/要点 | 接口模块 |
|---|---|---|---|
| 报废单 | `waste/wastemain`（index/WasteMainForm/WasteMainDetail/wasteApproval/MaterialSelectDialog） | 搜索 报废名称/编号；**报废物资申请**(新增)、**发起审批**、详情、编辑、删除（后三者 `v-if=status===1`）；审批状态字典列、入库状态字典列 | `/material/waste-main`（page/get/create/update/delete/export-excel/`get-source-info`/`initiate-approval`/`get-instance-id`） |
| 报废台账 | `waste/ledger`（index/WasteDetail/disposeForm） | 搜索 物资编码/名称/来源类型(1 在库 2 出库批次 3 无批次)/状态(0 未处置 1 已处置)；**处置**（`status===0` 才显示）、详情、导出 | `/material/waste-detail`（page/get/**dispose**/export-excel） |

### 2.8 directSupply 直供物资
| 功能 | 页面 | 主要按钮/要点 | 接口模块 |
|---|---|---|---|
| 直供登记 | `directSupply/register`（index/DirectSupplyRegisterForm/importForm） | 项目编号/名称/乙方企业；**直供物资登记**、导出、物资明细 | `/material/direct-supply` |
| 直供核销 | `directSupply/writeOff`（index/detail） | 项目维度；导出、**查看核销批次**、下载 | `/material/direct-supply` |
| 核销管理 | `directSupply/writeOffManage`（index/form） | 核销申请编号/核销周期/凭证名称；**发起核销申请**、编辑、删除、查看详情 | `/material/direct-supply` |

### 2.9 maintenance 维保 + usage 使用（设备物资的后生命周期）
| 功能 | 页面 | 主要按钮/要点 | 接口模块 |
|---|---|---|---|
| 维保预警 | `maintenance/alert`（index/detailForm/updateFrom/batchUpdateFrom） | 预警内容/仓库货架；**批量维保、确认维保**、详情、删除 | `/material/maintenance-alert` |
| 维保记录 | `maintenance/record`（index/MiantenanceRecordForm/detailForm） | 维保单位/数量/电话；**新增维保**、编辑、导出、详情 | `/material/miantenance-record` |
| 维保规则 | `maintenance/rule`（index/MaintenanceRuleForm/detailForm） | 物资分类/维保类型(常规/特殊)；**新增维保规则**、编辑、导出、详情 | `/material/maintenance-rule` |
| 条码/数字身份 | `usage/code`（index/MaterialDetailCodeForm） | 状态(已生成/已打印)；**批量打印**、详情、下载（打印物资条码/数字身份） | `/material/material-identity` |
| 安装登记 | `usage/install`（index/MaterialInstallForm/RegisterForm/DetailForm） | 负责人/状态(待登记/已登记)；**新增安装任务、登记**、详情、导出 | `/material/material-install` |
| 检修/报修 | `usage/repair`（index/MaterialRepairForm/RegisterForm/DetailForm） | 报修人/状态(待处理/处理中)；**新增维修任务、继续**、详情、导出 | `/material/material-repair` |

### 2.10 review 供应商评价（arrival 采购到货后触发）
| 功能 | 页面 | 主要按钮/要点 | 接口模块 |
|---|---|---|---|
| 评价记录 | `review/record`（index/ReviewRecordForm/DetailForm/UpdateBatchForm） | 采购订单/供应单位/状态(已评价/待评价)/到货日期；**立即评价、批量评价**、导出 | `/material/review-record` |
| 评价结果 | `review/result`（index/ReviewResultForm） | 供应单位/评价周期(月度/季度/年度)；**新增、评价报告**、导出 | `/material/review-result` |
| 评价规则 | `review/rule`（index/ReviewRuleForm/DetailForm） | 规则名称/状态(已启用/已停用)；新增/编辑/查看/导出 | `/material/review-rule` |

---

## 3. 核心操作页面详解（出库 / 报废 / 盘点）

### 3.1 正常领用出库 —— `views/material/warehouseOut/outbound/index.vue` + `OutboundMainForm.vue` + `OutboundHandleForm.vue`
**页面布局**：搜索栏(领用编号、领用日期 daterange) → 工具栏(搜索/重置/**新增领用** `v-hasPermi="['outbound:outbound-main:create']"`) → 表格 → 行内操作 → 底部三个弹窗组件 `<OutboundMainForm/>`、`<OutboundDetailForm/>`、`<OutboundHandleForm/>`。
**表格列与状态**：领用单编号/申请日期/申请人/领用日期/领用部门/出库类型(types)/审批状态(approvalStatus，着色：1/2 红、3 绿、4 橙)/出库状态(status 1 未出库红 2 已出库绿)。
**状态驱动按钮（真实代码 v-if 逻辑）**：
- 发起审批：`approvalStatus==1` → `initiateApproval(id)` 传 `{id, types:1}` → `OutboundMainApi.initiateApproval`(PUT `/material/outbound-main/initiate`)；
- 详情：`OutboundMainApi.getOutboundMain(id)` → `OutboundDetailForm.showDetailDialog(res)`；
- 下载：`OutboundDetailApi.exportOutboundDetail({outboundId})` → 导出文件名「正常领用明细.xls」；
- 预约领取/重新预约/查看预约：条件 `approvalStatus===3 && status===1 && outType===2` 且分别按 `isTimeOut` 0/2/1 显示三个按钮 → 打开 `OutboundHandleForm.open('appointment'|'reschedule'|'detail', outboundCode, id)`；提交 `OutboundMainApi.appointmentReceive({outboundCode, appointmentTime:[起,止], photo:[图片URL]})`（字段名注释：`outType` 1 正常 2 无人值守；`isTimeOut` 0/1/2 对应三态，具体语义代码注释未写全，**不确定**）。
- 旧版「确认出库」按钮在该页面已被整段注释（确认出库动作迁移到 materialOutbound/outboundList/allocation 等页：`confirmOutbound({id})` PUT `/material/outbound-main/confirmOutbound`）。
- 列表加载后 `res.list.filter(item => item.types !== 2)`（紧急出库单在 urgent 页管理）；行内权限串历史遗留仍为 `inbound:inbound-main:*`（与 outbound 页并存，**事实如此**，权限需后端放行才能显示）。
**新增领用表单（OutboundMainForm）提交关键参数**：
1. 左侧条件搜在库物资：`BoundMainApi.getBoundMainList({...searchParams, excludeTempWarehouse:true})`，结果过滤 `availableQuantity > 0`；
2. 勾选行组成 `outDetailRespVOList`，行内填领用数量 `currentQuantity`（上限=行 `availableQuantity` 可用数量，`el-input-number :max`）；
3. 提交前 `checkSameWarehouse` 校验所选行是否同一仓库；
4. `createOutboundMain({ purpose, address:undefined, remark:undefined, types:1, details: rows.map(item => ({...item, boundMainId:item.id, id:null})) })` —— 即主表头只交 purpose + types=1(正常)，明细每行用**在库记录 id 映射为 boundMainId**，id 置空。

### 3.2 报废单 + 报废台账处置 —— `waste/wastemain/*` + `waste/ledger/*`
**报废单列表（wastemain/index.vue）**：搜索(报废名称/编号/创建时间)；新增按钮「报废物资申请」权限 `t:waste-main:create`（注意前缀 `t:`，与其它页 `material:`/`outbound:` 不同，后端菜单资源串如此配置）。表格列含 报废编号/名称/申请日期/申请人/部门/物资种类 types/鉴定报告(surveyReportName)/审批状态(`dict-tag` approval_status)/入库状态(`dict-tag` waste_inbound_status)。
**行按钮状态驱动**：发起审批/编辑/删除 均 `v-if="status===1"`；发起审批 `WasteMainApi.initiateApproval({id})`(PUT `/material/waste-main/initiate-approval`)；编辑走 `WasteMainForm.open('update',id)`（编辑态回显时把 `wasteDetailList[].sourceType` 转字符串、`pictureUrl` 逗号串拆数组）。
**报废申请表单（WasteMainForm.vue）提交要点**（前端唯一入参通道，后端据此锁定数量）：
- 主表字段：wasteName、reason、surveyReportName、surveyReport(鉴定报告URL)、pictureUrl（提交前 **数组 join(',') 转逗号串**）、remark、department 等；
- 明细行 `wasteDetailList[]` 每条：物资编码/名称(从 `MaterialSelectDialog` 多选带入，去重) + 下拉三选：
  - `sourceType`：1 在库物资 / 2 出库批次 / 3 无批次；
  - 选 1/2 时触发 `getWasteMainSourceInfo({sourceType, materialCode})`(GET `/material/waste-main/get-source-info`)，返回项含 `values/lables/num`，前端把 **value=`values` 绑到行 `sources`、label=`lables`、可报废上限=`num` 赋给 `canWasteNum`** —— 即提交行 `sources`(如"仓库名-货架名")而不提交显示用 `lables`（**重要字段约定**）；选 3 无批次则无上限；
  - 报废数量 `wasteNum`：正整数；sourceType 1/2 时前端校验 `wasteNum <= canWasteNum`；
- 提交：create 调 `WasteMainApi.createWasteMain(data)`，update 调 updateWasteMain（`surveyReport==''` 时同时清 surveyReportName）。
**报废台账（ledger/index.vue）处置链路**：状态 `status` 0 未处置/1 已处置；行按钮「处置」仅 `status===0` 且权限 `material:waste-detail:dispose` 显示 → `disposeForm.open(id, wasteNum)`。
**处置弹窗（disposeForm.vue）提交关键参数** → `WasteDetailApi.disposeWasteDetail(submitData)`(PUT `/material/waste-detail/dispose`)：
`{ detailId, disposalWay(1 拍卖/2 招标/3 直接销售/4 销毁/5 其他), disposalWayOther(选 5 时必填文本), disposalNum(处置数量，:max=可处置数量), receiver(接收方), contactPerson, contactPhone, disposalTotal(成交总价), fixtureDate(成交日期 YYYY-MM-DD), fileUrl(附件 UploadFile 单文件) }`。
> 处置数量=报废数量时后端才会把台账明细置「已处置」并联动生成报废出库/流水（后端细节本次未读，前端仅此一个 dispose 调用点，**后端联动逻辑不确定**，勿凭前端臆断）。

### 3.3 盘点 —— `views/material/warehouseing/stock/*`
**列表页（stock/index.vue）**：搜索(盘点编号/盘点任务名称/盘点日期/盘点类型(下拉仅 0 在线盘点、2 普通盘点，扫码盘点 1 的选项被注释)/仓库范围(下拉取 `WarehouseApi.getWarehouseList`)/盘点状态)；新增盘点任务权限 `material:stock-main:create`。
**表格列**：盘点编号/任务/日期/类型(0 在线→'在线盘点' 其余显示'普通盘点')/仓库范围/计划盘点数量 plantCount/已盘数量 usageCount/差异项 differRow/状态（1 已完成绿 2 待盘点红 3 盘点中橙 4 已取消灰）。
**行按钮状态机（真实 v-if 组合，RAG 高频）**：
| 按钮 | 条件 | 动作 |
|---|---|---|
| 开始盘点 | `status===2 && stockType===0` | 先 `checkStockMainStatus()`（GET check-status）防在线盘点并行，再 `StartForm.open(id,1)` |
| 继续盘点(在线/扫码) | `status===3 && stockType!==2` | `StartForm.open(id,2)` |
| 继续盘点(普通) | `status===3 && stockType===2` | `NormalStartForm.open(id)` |
| 取消盘点 | `status===3` | `cancelStockMain(id)` |
| 盘点详情 | `status===1` | `DetailForm.open(id)` |
| 盘点报告 | `status===1` | `ReportForm.open(id)`（内含差异→审批发起，见下） |
| 差异填报 | `status===1 && stockType===0 && differRow!==0 && allConfirm===0` | `StartForm.open(id,3)` |
| 导出清单 | `stockType===2 && status===2` | `exportDetail({id})` 下载「仓库普通盘点详情.xls」 |
| 编辑/删除 | `status===2 \|\| 4` | `openForm('update')` / `deleteStockMain` |

**盘点执行弹窗**：`StartForm`(在线/扫码)、`NormalStartForm`(普通) 均为盘点作业界面：单行确认 `confirmStockMain(row)`、批量 `confirmStockMainMore(selectedRows)`（PUT confirm / confirm-more）；普通盘点还含清单导入/上传文件（`save-file-info`、`get-file-info`、`delete-file`、`confirm-import`、`download-error-rows`、`download-detail` 等扩展 API 在 `StockMainApi` 可见）。`DetailForm` 亦支持差异确认。差异与盘盈盘亏：`ReportForm`(盘点报告弹窗) 中按差异结果调 `initiateApproval(params)`(注释：盘盈入库发起审批 PUT `/material/stock-main/initiate`) 与 `initiateApprovalOut`(注释：盘盈出库发起审批 PUT `/material/stock-main/initiate-out`)——**API 注释如此，业务命名(盘盈/盘亏)以前端注释为准，未必与后端语义一致，不确定**。新建盘点任务时默认盘点类型由租户硬件开关决定：`StockMainForm` 里 `stockType = isHardware ? 0(在线) : 2(普通)`；「在线盘点」radio 仅 `v-if="isHardware"` 显示（关联 RFID/盘点终端硬件，来自 `hooks/web/useHardware.ts` → `userStore.getHasHardware`，即登录时后端下发的 `tenant.hasHardware`，会话内不刷新——改库后须重新登录）。

---

## 4. 菜单与权限组织

### 4.1 菜单/路由来源机制（关键架构事实）
- **一级/二级菜单与页面路由不写死在前端代码**：登录时 `api/login` 的 `getInfo()`（对应后端 `/system/auth/get-permission-info` 类接口）一次性返回 `{user, tenant{id,name,hasHardware}, roles, permissions, menus}`；`store/modules/user.ts` 的 `setUserInfoAction` 把 `userInfo.menus` 缓存进 `wsCache(CACHE_KEY.ROLE_ROUTERS)`（web-storage-cache，本地缓存），permissions 存入 Pinia Set。
- `store/modules/permission.ts` 的 `generateRoutes()`：读 ROLE_ROUTERS → `utils/routerHelper.ts` 的 `generateRoute(menus)` 转成 vue-router 记录：**菜单里存的 `component` 字符串（如 `material/warehouseOut/outbound/index`）经 `import.meta.glob('../views/**/*.{vue,tsx}')` 匹配到真实文件**（`registerComponent` 用 `defineAsyncComponent` 动态加载），并把后端菜单的 name(标题)/icon/visible/keepAlive/alwaysShow 映射进 `meta`；追加 404 兜底后 `addRoute`。`meta` 扩展字段语义见 `remaining.ts` 头注释：`hidden`(不进侧边栏)、`canTo`(hidden 也能跳)、`noCache`(不进 keep-alive)、`activeMenu`(高亮父菜单)、`alwaysShow`、`affix`、`noTagsView`、`followAuth`、`breadcrumb`。
- 前端**静态/隐藏路由**集中在 `src/router/modules/remaining.ts`（全项目仅此一份路由文件，约 466 行）：首页 `/`(Home/Index)、个人中心 `/user/profile`、我的站内信、字典数据隐藏路由 `/dict/type/data/:dictType`、BPM 模型创建/编辑隐藏路由、以及一批 **BPM 审批详情跳转用隐藏路由**：
  - `material/warehouseOut/outbound/initiateApprovalDetail`(name=outboundDetail1，查看领用详情，activeMenu 指回 bpm/manager/model)
  - `material/waste/wastemain/wasteApproval`(name=wasteApproval，查看报废详情)
  - `material/directSupply/writeOffManage/form`(writeOffManageForm，查看核销详情)
  - `material/warehouseIn/returnmain/initiateApprovalDetail`(returnDetail1，查看退库详情)
  - 以及 `/material` 下的兼容跳转（`/purchasedetailIndex`→到货详情等）。可见**多类业务单据的"发起审批"是从业务列表跳 BPM 的流程审批页/详情页**。
- 前端另有两个静态容器路由 `/bpm`（含 OA 请假等业务示例）与 404。

### 4.2 权限控制三层
1. **路由层**：菜单由后端按角色下发（4.1），看不到菜单即无路由；
2. **按钮层**：`v-hasPermi="['模块:资源:操作']"`（directives/hasPermi.ts，比对 Pinia permissions Set）；权限串风格如 `outbound:outbound-main:create`、`material:stock-main:start`、`material:waste-detail:dispose`、`t:waste-main:create`（报废模块用 `t:` 前缀，与其它模块不一致，是现状）；
3. **租户能力层**：`useHardware()`→`tenant.hasHardware` 控制 RFID/在线盘点等硬件功能显隐；租户配置界面在 `views/system/tenant/TenantForm.vue`（hasHardware 开关）。

### 4.3 一级模块划分（views/api 双维度证据，非后端菜单表）
| 一级模块 | 管什么（据 views/api 目录与抽样） | 关键子目录 |
|---|---|---|
| material | **核心物资业务**（10 域见第 2 节），后端前缀 `/material/*` | arrival/warehouseIn/warehouseing/warehouseOut/waste/standard/directSupply/maintenance/usage/review |
| bpm | 工作流：流程定义/模型设计(bpmn-js)、任务(待办/已办)、流程实例、表达式、监听器、用户组、表单、OA 请假示例 | bpm/model、task、processInstance、definition、form、category、userGroup、processExpression、processListener、simple、group、oa、leave |
| system | 系统管理/权限：用户、角色、菜单、部门、岗位、字典、公告、站内信、租户与套餐、短信/邮件、社交登录、OAuth2、操作/登录日志、区域 | system/user、role、menu、dept、post、dict、notice、notify、tenant、tenantPackage、sms、mail、social、oauth2、operatelog、loginlog、area |
| infra | 基础设施：代码生成、文件(配置)、定时任务(及日志)、Redis、系统配置、数据源、API 访问/错误日志、监控(服务器/swagger/druid/skywalking)、WebSocket、演示代码 | infra/codegen、file、fileConfig、job、jobLog、redis、config、dataSourceConfig、apiAccessLog、apiErrorLog、server、swagger、druid、skywalking、webSocket、demo、build |
| 其余静态 | Home(工作台首页)、Login、Profile、Redirect、Error | Home/Login/Profile/Redirect/Error |

### 4.4 面向检索的补充事实
- 菜单标题/图标/排序存**后端菜单表**，前端渲染侧边栏的 title 来自后端菜单 `name` 字段（generateRoute 里 `meta.title = route.name`）；要改菜单文案/加菜单需走后端菜单管理（`views/system/menu`）。
- 每个模块的"当前用户可见菜单"API 在 `src/api/material/usermenu`（首页快捷菜单，URL `/material/menu`、`/material/app`），首页驾驶舱类接口在 `src/api/material/warehouse/driver`（`/material/driver`），均未在本轮深读（不确定字段语义）。

---

## 附录 A：全仓状态字典数字速查（RAG 直接命中）
| 字段 | 取值 | 适用模块 |
|---|---|---|
| approvalStatus(审批状态) | 1 待审批 / 2 审批中 / 3 审批通过 / 4 已驳回 | 出库单、报废单、退库单、移库、直供核销等所有走 BPM 的主单（字典 approval_status） |
| outbound.status(出库状态) | 1 未出库 / 2 已出库 | 出库记录页只显示 `status===2`（后端 SQL 亦排除未出库，出库清单页不显示 outStatus=1） |
| outbound.types(出库类型) | 1 正常 / 2 紧急 / 3 调拨 / 4 盘亏（页面 switch 文案） | warehouseOut 各页按 types 过滤呈现 |
| outbound.outType(出库种类) | 1 正常 / 2 无人值守（VO 注释） | 预约领取三态(预约/重新预约/查看)依赖 outType=2 + isTimeOut 0/2/1 |
| waste.status(报废单审批) | 同 approvalStatus（approval_status） | waste/wastemain |
| waste.warehousedStatus(入库状态) | 1 未入库 / 2 已入库（waste_inbound_status） | waste/wastemain |
| waste-detail.status(台账处置状态) | 0 未处置 / 1 已处置 | waste/ledger |
| waste-detail.sourceType(来源类型) | 1 在库物资 / 2 出库批次 / 3 无批次 | waste/ledger、WasteMainForm |
| stock.status(盘点状态) | 1 已完成 / 2 待盘点 / 3 盘点中 / 4 已取消 | stock-main |
| stock.stockType(盘点类型) | 0 在线 / 1 扫码(选项注释停用) / 2 普通 | stock-main；默认可由 isHardware 决定 0/2 |
| stock.normalStatus | 1 不显示盘点数量/差异，2 显示（VO 注释） | 普通盘点 |

## 附录 B：字段/提交约定与易错点（后端联调语境，含本系统记忆要点）
1. **报废申请行只提交 `sources`（"仓库名-货架名" 下拉 value），不提交 `lables`**；后端按 materialCode+仓库名+货架名定位在库记录（与处置出库 createOutBoundInfo 路径一致），`lables` 仅展示/兜底。
2. **处置出库链**：台账「处置」`disposeWasteDetail` 是唯一生成报废出库(types=5)+流水(outStatus=2)的前端入口；审批通过本身只改主单状态、不生成出库（前端证据：wastemain 审批仅 initiate-approval，出库/流水均无其它 create 调用点）。
3. 在库主档 `bound-main`：`inventoryQuantity`(库存)/`availableQuantity`(可用)/`shardQuantity`(共享)/`warningQuantity`(预警值)/warningAccept/warningTime/warningDays 等字段同时被出库选料、报废选料、资产页复用；报废锁定走新增 `waste_quantity`（后端逻辑，前端未见直接字段名，**不确定**前端是否展示）。
4. 图片类字段提交前 join(',')、回显时 split(',')；UploadFile 返回数组/URL。
5. 单号生成在后端（`/material/outbound-main/...` 等单据编号字段如 outboundCode/stockCode/wasteCode 由后端按规则生成），前端只读展示。
6. 多页面共用 outbound-main 单表：出库列表页做前端过滤（如正常页 `types!==2`），是"一表多入口"架构。
7. 接口拼写注意：`miantenance-record`（maintenance 模块接口缺字母）、`/material/wz`（provider 模块旧前缀，与 `/material/provider` 并存）——检索/改后端时小心。

> 知识覆盖范围：2026 年该仓库当前状态抽样（未覆盖：仓库操作日志/审批中表单的逐字段细节、system/infra/bpm 页面内部逻辑、i18n 文案、后端 service 实现）。如需更细粒度，建议再补充 `src/views/material/warehouseIn/inbound/inboundOperation.vue`（入库执行/RFID 打印链路）与 `StartForm.vue`/`NormalStartForm.vue` 全量、以及 `src/config/axios` service 拦截器与 `hooks/web/useHardware.ts` 的展开阅读。
