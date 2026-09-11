# 物资管理系统数据库结构知识

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
