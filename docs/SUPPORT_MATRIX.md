# 转换支持矩阵

状态说明：**直接**表示结构和主要参数有明确映射；**近似**表示会生成 LS-DYNA 卡，但报告要求人工复核；**报告错误**表示没有安全、唯一的自动映射，严格模式会停止输出。

## 模型、网格和装配

| Abaqus 定义 | LS-DYNA 输出 | 状态 |
|---|---|---|
| `*INCLUDE` | 递归读入并合并 | 直接 |
| `*PART` / `*ASSEMBLY` / `*INSTANCE` | 实例展开、全局重新编号 | 直接 |
| 实例平移与轴角旋转 | 坐标变换 | 直接 |
| `*SYSTEM` | 节点坐标转换到全局 | 直接 |
| `*NODE` | `*NODE` | 直接 |
| `C3D8/R/I` | `*ELEMENT_SOLID`, ELFORM 1/2 | 直接 |
| `C3D4`, `C3D5`, `C3D6` | 退化实体，ELFORM 10/15 | 直接，需检查网格质量 |
| `C3D10/M` | 10 节点 `*ELEMENT_SOLID`, ELFORM 16 | 直接 |
| `COH3D8` | `*ELEMENT_SOLID`, ELFORM 19 | 近似；材料必须专门配置 |
| `S4/R/RS`, `S3/R`, `M3D4/3`, `R3D4/3` | `*ELEMENT_SHELL` | 直接；刚体壳材料需复核 |
| `CPE*`, `CPS*`, `CAX*`（一阶） | 二维壳族 ELFORM 13/12/15 | 近似；核对厚度与积分 |
| `B31/H`, `T3D2` | `*ELEMENT_BEAM` | 近似；核对截面方向和积分 |
| `MASS` + `*MASS` | `*ELEMENT_MASS` | 直接 |
| 其他高阶/特殊/声学/流体/粒子单元 | 无 | 报告错误，可配置单元映射 |
| `*NSET`, `*ELSET`, `GENERATE` | 节点集、截面分组、接触集合 | 直接 |
| 元素表面 S1…S6、SPOS/SNEG | `*SET_SEGMENT` | 直接 |
| 节点表面 | `*SET_NODE_LIST`（节点-面接触） | 直接 |
| 实体/壳/梁/膜截面 | `*SECTION_*` + `*PART` | 直接/近似 |
| 复合铺层、材料方向、梁方向 | 无 | 报告错误 |

## 材料、失效和 EOS

| Abaqus 定义 | LS-DYNA 输出 | 状态 |
|---|---|---|
| `*DENSITY` + 各向同性 `*ELASTIC` | `*MAT_ELASTIC` | 直接 |
| 工程常数/正交弹性 | `*MAT_ORTHOTROPIC_ELASTIC` | 近似；核对泊松比约定和材料轴 |
| 表格 `*PLASTIC` | `*MAT_PIECEWISE_LINEAR_PLASTICITY` + `*DEFINE_CURVE` | 直接（首两列）；温度/场变量依赖会警告 |
| Johnson-Cook 塑性/速率 | `*MAT_JOHNSON_COOK` | 近似；核对温度和速率单位 |
| Neo-Hooke / Mooney-Rivlin / Ogden | 对应橡胶材料 | 近似；核对应变能和可压缩性约定 |
| Drucker-Prager | `*MAT_DRUCKER_PRAGER` | 近似；必须重新核对标定参数 |
| Crushable/low-density foam | `*MAT_CRUSHABLE_FOAM` 占位 | 报告错误，需 LS-DYNA 曲线 override |
| 延性/剪切损伤起始 | `*MAT_ADD_EROSION` 的 EFFEPS | 近似 |
| 损伤演化、Lode/三轴度/温度依赖失效 | 标量侵蚀不能保持全部语义 | 警告或报告错误，建议 GISSMO/DIEM override |
| `*EOS, TYPE=USUP` | `*EOS_GRUNEISEN` | 直接，核对单位 |
| 理想气体 / 线性多项式 EOS | 对应 `*EOS_*` | 近似，核对热力学参数 |
| `*USER MATERIAL`、VUMAT、复杂混凝土、复合材料 | 无通用映射 | 报告错误，使用 material override |
| 热膨胀、比热、电磁、渗透等多物理属性 | 无 | 报告错误 |

## 接触、边界、载荷和分析步

| Abaqus 定义 | LS-DYNA 输出 | 状态 |
|---|---|---|
| General contact, all exterior | `*CONTACT_AUTOMATIC_SINGLE_SURFACE` | 直接 |
| `*CONTACT PAIR` 元素面-元素面 | `*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE` | 直接 |
| 节点面-元素面 | `*CONTACT_AUTOMATIC_NODES_TO_SURFACE` | 直接 |
| `*TIE` | `*CONTACT_TIED_*` | 近似；核对 offset/adjust |
| 常数摩擦 | FS/FD | 直接 |
| 压力/过闭合/粘结/接触损伤的复杂表格 | 无唯一映射 | 报告错误或人工 override |
| 零值 `*BOUNDARY`、ENCASTRE/PINNED/对称 | `*BOUNDARY_SPC_*` | 直接 |
| 非零位移/速度/加速度 | `*BOUNDARY_PRESCRIBED_MOTION_*` | 直接 |
| `*AMPLITUDE`（TABULAR） | `*DEFINE_CURVE` | 直接 |
| `*CLOAD` | `*LOAD_NODE_POINT/SET` | 直接 |
| `*DLOAD, GRAV` | `*LOAD_BODY_X/Y/Z` | 直接 |
| `*DSLOAD, P` | `*LOAD_SEGMENT_SET` | 直接 |
| `*INITIAL CONDITIONS, TYPE=VELOCITY` | `*INITIAL_VELOCITY_NODE` | 直接 |
| 其他分布载荷、基底运动、声学/热载荷 | 无 | 报告错误 |
| 显式动力步 | 终止时间、时间步和数据库控制 | 直接 |
| 静力/隐式动力步 | 基础 `*CONTROL_IMPLICIT_*` | 近似；收敛控制需调整 |
| 多分析步中的激活/停用、`OP=NEW` | 单一 K 文件不能完整保持历史 | 警告/报告错误 |
| 接触质量缩放、ALE、自适应、CEL、耦合约束 | 无通用默认 | 报告错误或项目卡片追加 |

## 项目扩展

`mapping.example.json` 支持三类扩展：

1. `material_overrides`：替换任意材料的完整 LS-DYNA 卡片；
2. `element_type_overrides`：补充项目单元类型与 ELFORM；
3. `append_cards`：追加经过审核的控制、数据库、约束或用户卡片。

override 的目的不是压掉诊断，而是把项目中已经完成标定和验证的 LS-DYNA 定义显式保存下来。
