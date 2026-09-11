# 物资管理系统前端功能知识（面向大模型 RAG 检索）

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
