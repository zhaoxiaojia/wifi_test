# 数据库级联建表方案

## 总体目标
在现有配置保存与测试执行流程中，引入数据库持久层，将配置文件(`config`)中的层级信息按照 DUT、Execution、Test Case 三层分别持久化到 MySQL。通过级联建表机制保证：

1. 每次保存配置或执行测试时，数据库中的结构和数据与实际配置完全一致；
2. 能够支持当前的性能(performance)测试目录，也能方便扩展到后续的其他测试目录；
3. 表之间建立清晰的父子关系，便于查询与追溯；
4. 重复执行时自动清理旧表，保证结构及数据的一致性。

## 数据模型设计

### 1. DUT 层（第一层表）
- **表名：** `dut_settings`
- **主键：** `dut_id`（自增或 UUID）
- **字段：**
  - 初始字段集包含 `connect_type`、`software_version`、`hardware_version`、`android_version`、`fpga_version`、`serial_port`、`created_at`（默认当前时间）、`updated_at`；
  - **动态扩展字段：** 当 `config` 中出现新的 DUT 属性（例如新增的硬件标签、固件配置等）时，通过比对元数据表或 `INFORMATION_SCHEMA`，对缺失字段执行 `ALTER TABLE dut_settings ADD COLUMN`。
- **数据来源：** `config` 中 DUT Settings 的全部字段，包含未来新增项。
- **写入策略：**
  - 每次保存配置时，根据唯一键（如 `serial_number` 或组合键）判断是否存在，存在则更新，不存在则插入；
  - 插入/更新前，先完成字段比对与扩展，确保所有配置键都有对应列；
  - 返回 `dut_id` 用于后续层级关联。

### 2. Execution 层（第二层表）
- **表名：** `execution_settings`
- **主键：** `execution_id`
- **外键：**
  - `dut_id` 引用 `dut_settings.dut_id`，确保 Execution 级联在 DUT 上；
- **字段策略：**
  - **动态字段生成：** Execution Settings 中出现的所有键值对都需要同步到表结构中。初始化时先落地一组核心字段（如 `router`、`test_type`、`csv_path`、`script_branch`、`test_time`、`created_at`、`updated_at`），随后在每次写入前比对配置中的键；若发现表中不存在的字段，则通过 `ALTER TABLE execution_settings ADD COLUMN` 的方式补充对应列。
  - **字段类型推断：** 优先根据配置值类型（布尔、整数、浮点、字符串、列表/字典）映射到 MySQL 类型；列表/字典统一落在 `JSON` 字段。
  - **字段变更记录：** 通过元数据表（例如 `schema_registry`）记录当前 Execution 表所包含的字段及其类型，便于后续 diff 与维护。
- **数据来源：** Execution Settings 的全部字段，包含未来新增项。
- **写入策略：**
  - 每次执行测试时创建一条新的 execution 记录，关联 `dut_id`；
  - 若在配置保存阶段需要预写，则先创建占位记录，在执行时更新真实时间与状态；
  - 动态字段写入时，需保证在事务中先完成字段补全，再执行 `INSERT`/`UPDATE`。

### 3. Test Case 层（第三层表）
- **表名：** 动态按测试目录命名，例如 `performance`；后续若有 `stability`、`throughput` 等目录，同样按目录名命名。
- **主键：** `id`（自增）
- **外键：**
  - `execution_id` 引用 `execution_settings.execution_id`；
  - `dut_id` 引用 `dut_settings.dut_id`，确保 Test Case 层同时能从 Execution 与 DUT 两条路径进行级联查询。
- **字段：** 针对 `testResult.log_file` 中性能测试记录的结构化字段，例如：
  - `case_name`
  - `sub_case`
  - `metric`
  - `unit`
  - `value`
  - `threshold`
  - `result`（PASS/FAIL）
  - `log_path`
  - `created_at`
- **写入策略：**
  - 在执行脚本前，根据即将执行的测试目录列表，依次对每个目录执行：
    1. `DROP TABLE IF EXISTS {table_name}`；
    2. `CREATE TABLE {table_name} (...)`。建表时包含 `execution_id` 与 `dut_id` 两个外键，以保证双向级联；
  - 测试过程中，当解析 `testResult.log_file` 时，将记录写入对应目录的表，关联当前 `execution_id` 与 `dut_id`；
  - 若某目录无数据，也可保留空表以保证结构一致；
  - 如遇新的性能指标字段，同样通过 `ALTER TABLE` 动态扩展列，或在重建时根据解析得到的字段集合生成完整结构。

## 级联建表与写入流程

1. **配置保存阶段**
   - 解析配置文件，构造 DUT Settings 数据模型。
   - 调用数据库操作层 `upsert_dut_settings(data)`，在内部通过 `sync_table_schema('dut_settings', data)` 自动补齐字段，返回 `dut_id`。
   - 如需提前建立 Execution 记录，可调用 `create_execution_placeholder(dut_id, execution_config)`，在内部通过 `sync_table_schema('execution_settings', execution_config)` 自动补齐字段并写入初始信息。

2. **执行测试阶段**
   - 根据当前执行上下文获取 `dut_id` 与 `execution_id`；如果执行阶段才创建 Execution，需调用 `create_execution(dut_id, execution_config)`，内部同样执行 `sync_table_schema('execution_settings', execution_config)`。
   - 构建待执行的测试目录列表（如 `performance`）。
   - 遍历目录列表，对每个目录调用 `recreate_test_table(table_name, schema_definition)` 完成级联建表：
     - 使用统一的建表模板，字段集合由解析器提供。
     - 建表前通过 `sync_table_schema(table_name, schema_definition)` 与元数据表完成字段对齐。
   - 在测试脚本解析日志或生成结果时，通过 `insert_test_result(table_name, dut_id, execution_id, record)` 写入数据。

3. **事务与一致性**
   - 建议在配置保存和执行写入关键步骤使用事务：
     - DUT / Execution 写入可各自封装在事务内。
     - Test Case 数据的 `DROP + CREATE + INSERT` 需要确保操作顺序一致，可使用单独事务。
   - 如遇异常（例如连接失败或建表错误），回滚并在脚本中输出错误日志，确保不会影响原有脚本逻辑。

## 扩展与维护

- **字段变动：**
  - 引入统一的 `schema_registry` 元数据表，记录每个业务表当前的字段、数据类型与最后一次同步时间；
  - 在 DUT 与 Execution 写入前，通过对比配置键与元数据表决定是否需要 `ALTER TABLE`；
  - 提供 `sync_table_schema(table_name, payload)` 通用接口，自动完成列存在性校验与新增。
- **目录扩展：** 新增测试目录时，只需在配置或执行流程中传入目录名与对应字段结构，自动完成建表与写入。
- **查询接口：** 可在后续补充查询工具，用于按 `dut_id`、`execution_id` 检索测试结果。

## 实施步骤概览

1. 新增数据库操作封装模块，提供连接管理、建表、写入、事务等函数。
2. 在配置保存流程中调用 DUT 层写入逻辑，返回 `dut_id`。
3. 在执行流程中调用 Execution 层写入逻辑，生成 `execution_id`。
4. 在测试执行前对每个测试目录执行 `DROP + CREATE`，建立对应 Test Case 表。
5. 在日志解析阶段，将结果按目录写入对应表，关联 `execution_id`。
6. 增加异常处理与日志输出，确保数据库操作失败时仍可继续执行脚本（或给出明确提示）。

