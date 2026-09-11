# 物资管理系统后端业务知识（RAG 检索用）

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
