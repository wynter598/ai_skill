# SQL 代码格式规范化工具集（SQL Formatter）

## 基础信息

1. **创建人**：`<姓名/团队>`（团队内部 Skill，请按实际维护情况填写）
2. **维护人**：`<姓名/团队>`
3. **创建时间**：`2026-03-31`（以 v1.0 首次整合发布为基准）

## 版本迭代说明

- **`v1.0`（2026-03-31）**：初始版本，整合 **AS 对齐**与 **CREATE TABLE 列定义对齐**，支持 `--as-only` / `--table-only` 与改进后的验证逻辑。
- **`v1.1`–`v1.8`（2026-04-01）**：修复 AS 起始位置估算、`display_width` / `get_width` 与建表验证定位等问题，统一按**显示宽度**计算列别名对齐。
- **`v2.0`–`v2.7`（2026-04-11）**：新增 `--char-mode`、`--cjk-width`，修复嵌套 `cast`、`float` 空格、`round()` 与行首缩进宽度等边界问题，对齐逻辑更多固化在 `sql_aligner.py` 中。
- **`v3.1`（2026-04-21）**：与 `skill.md` 定稿对齐——**ON 单独成行**、**WHERE/HAVING 与 AND/OR 列规则**、**全局行首逗号**、注释 `--` 与正文整体处理；接入 **跨行圆括号对齐**、子查询后 **ON 与 JOIN 同列**、CASE/HAVING/`add_missing_as_keywords` 等工具侧修复；README 补充 **CJK / 多 IDE 视觉差异**与 `docs/KNOWN_ISSUES.md`（含 Issue #4）。

## 功能描述

本 Skill / 工具集用于**自动化 SQL 代码格式规范检查与对齐**，与 `skill.md` 中的团队规范一致，核心能力包括：

- **统一对齐入口**：`sql_aligner.py`（推荐）整合 SELECT 中 **`as` 分级/闸门对齐**、**CREATE TABLE** 列名 / 类型 / `COMMENT` 对齐、**跨行圆括号**对齐等。
- **规范级能力**：`ON` 换行与列对齐、`WHERE`/`HAVING` 与谓词及 `and`/`or` 的排版、行首逗号、`CASE`/`WHEN` 列锚、运算符与注释处理等（详见下文「v3.1 规范摘要」及 `skill.md`）。
- **验收与 CI**：支持 `--verify-only` 仅校验不改写，便于提交前或流水线检查。

## 详细文档说明

1. **背景与问题**：数仓 / 风控等场景下 SQL 文件体积大、风格不一，人工对齐 `as`、建表字段与复杂嵌套子查询成本高且易不一致；本工具将规范**可执行化**，减少评审返工。
2. **SOP 与规范全文**：以仓库内 **`skill.md`** 为单一事实来源（与 README「规范摘要」同步维护）。
3. **已知问题与排障**：**`docs/KNOWN_ISSUES.md`**（如 PyCharm 中文宽度 Issue #1、cast/CASE Issue #2/#3、多行 `case` + 独占 `)` 后行首逗号 Issue #4 等）。
4. **IDE 字体与 CJK**：**`docs/pycharm_font_fix.md`**（PyCharm 字体配置参考）。
5. **若篇幅继续膨胀**：可将长篇 SOP、评审清单沉淀到飞书文档，在本节**直接替换为**对应文档链接即可。

### v3.1 规范摘要（与 `skill.md` 同步）

- **ON**：一律单独成行，与同层 `from` / `left join` / `join` 等**首列对齐**；子查询 `) as alias` 后的 `on` 亦对齐到该 **join** 列（不与 `)` 对齐）；无「条件短则与 join 同行」例外。
- **WHERE / HAVING**：各自与**第一个谓词同一行**；该块内后续 **`and` / `or`** 单独成行，且与同块的 **`where` 或 `having`** 首列对齐。
- **逗号**：**全局行首逗号**（`select`、`group by` 等列表风格一致）；**子查询括号内**以 `,` 开头的行，**逗号列**与同块 **`select` / `group by` 首行首字段** 对齐（`align_subquery_brackets`）；**多行 `case … end` 后独占行 `) as col`** 时，`align_field_names` 须把 `end` 与 `)` 视为同一字段尾部，否则后续行首逗号会错位（见 `docs/KNOWN_ISSUES.md` **Issue #4**）。
- **关键字**：**禁止**将 `inner join`、`left join`、`group by` 等拆成两行。
- **运算符空格**：`set`、`partition(...)`、条件中的 `=`、`>=` 等由工具预处理为两侧加空格（与规范一致）。
- **注释**：**`--` 与注释正文视为一个整体**，不得在 `--` 与正文之间插入或删除空格；仅允许调整**行首缩进**及注释前后空行。
- **CASE**：`case` 与 `end` 首字母同列；所有 `when` 与 `else` 首字母同列（工具 `align_case_when_columns`，在字段/子查询对齐之后执行）。
- **跨行圆括号**：`align_cross_line_parens` 在预处理中执行；跨行匹配的 `)` 与对应 `(` 同列，扫描时忽略引号/反引号/注释内的括号，且仅当该行 `)` 前全为空白时才改写。
- **验收口径**：`sql_aligner.py` **默认不加参数**，**以终端等宽字体下的 `as` 竖线对齐为准**；与 IDE 视觉差异见下一节。

### 中文（CJK）与多 IDE 中的列别名缩进

当某一行内出现**中文字符**（例如中文注释、中文字符串字面量、或字段表达式里含中文）时，工具会按 `unicodedata` 东亚宽度规则计算**显示宽度**（默认宽字符约 **2 个 ASCII 列宽**），再据此插入空格，使 **`as` 与别名列对齐**。

**现象**：同一文件在**终端**里往往竖线对齐，但在 **PyCharm、VS Code、Cursor** 等不同 IDE 中，由于**字体 metrics、CJK 是否等宽、缩放比例**等差异，同一行里中文的**实际占位**可能与工具采用的宽度**不一致**，于是会出现：**终端里列别名对齐，在 IDE 里看起来略偏左或略偏右**。这不表示 SQL 被改坏，而是**不同环境下的「列」定义不同**（显示宽度 vs 像素宽度）。

**可选处理**：

1. **团队约定**：以 **终端 / CI 日志** 下的对齐为验收标准（当前默认）。
2. **本地 IDE 更接近终端**：可尝试 `--cjk-width 1.5` 或 `1.33` 等（见版本历史 v2.1 与 `docs/KNOWN_ISSUES.md` Issue #1）。
3. **不按显示宽度、按字符个数对齐**：使用 `--char-mode`（每个字符占 1 列），IDE 与终端观感可能更接近，但与「宽字符占 2 列」的终端规则不一致，需团队统一。

## 初始化要求或前置准备

- **运行环境**：本目录或 `docs/scripts/` 下具备 **`python3`**；依赖以脚本自身及标准库为准（若后续增加 `requirements.txt`，在此条补充 `pip install -r requirements.txt`）。
- **配置文件**：**无需**单独配置文件；行为由命令行参数与 `skill.md` / 代码内默认常量共同约定。
- **初始化步骤**：将本 Skill 置于 Claude / Cursor 可识别的 skills 路径；处理具体 SQL 时，在脚本所在目录执行下文命令，或使用绝对路径调用 `sql_aligner.py`。
- **建议先读**：`skill.md`（规范）、`docs/KNOWN_ISSUES.md`（踩坑）。

## 使用示例

### 示例 1

**输入**（用户需求 / 上下文）：

> 对 `warehouse/xxx.sql` 做完整格式化，并确认无遗留对齐问题。

**输出**（期望操作与结果说明）：

```bash
python3 sql_aligner.py warehouse/xxx.sql
python3 sql_aligner.py warehouse/xxx.sql --verify-only
```

期望：`as`、建表块、括号与规范摘要一致；`--verify-only` 退出码与终端提示表明通过。

### 示例 2

**输入**：

> 只修 SELECT 里的 `as` 对齐，不改建表段；在 PyCharm 里中文别名看起来偏一位。

**输出**：

```bash
python3 sql_aligner.py file.sql --as-only
# 按需尝试（与团队约定一致任选其一）：
python3 sql_aligner.py file.sql --as-only --cjk-width 1.5
python3 sql_aligner.py file.sql --as-only --char-mode
```

期望：在约定验收环境（终端或指定 IDE）下别名竖线对齐可接受。

### 附：常用命令速查

```bash
python3 sql_aligner.py file.sql
python3 sql_aligner.py file.sql --verify-only
python3 sql_aligner.py file.sql --as-only
python3 sql_aligner.py file.sql --table-only
python3 sql_aligner.py file.sql --as-only --verify-only
```

## 边界条件或不适用场景

- **非 HiveQL / 非本团队规范方言**：关键字列表、注释规则可能与工具假设不一致，需评估或扩展后再用。
- **极端复杂动态 SQL / 由程序拼接且无法稳定解析的片段**：不适合作为「整文件自动对齐」对象，建议仅对静态可解析部分处理。
- **强依赖「像素级」跨编辑器一致**：CJK 与字体导致 IDE 与终端观感必然存在差异，若不接受 `--cjk-width` / `--char-mode` 与团队验收口径，则**不适用**「一刀切自动对齐」预期。
- **含特殊多行函数、隐藏制表符或非断行空格**：可能出现「肉眼看齐但校验失败」，需先清洗字符或升级工具版本（见 `docs/KNOWN_ISSUES.md`）。
- **许可与范围**：内部工具，仅供团队使用；对外分发需另行合规确认。

---

## 工具文件说明（补充）

### 核心工具：`sql_aligner.py`（`docs/scripts/sql_aligner.py`）⭐ 推荐使用

**统一的 SQL 对齐工具**，整合了主要对齐能力：

- AS 关键字分级对齐（SELECT 语句）
- CREATE TABLE 列定义对齐（列名、数据类型、COMMENT）
- 跨行圆括号列对齐（`align_cross_line_parens`，忽略字符串与注释内括号）

## 对齐规则说明（补充）

### 1. AS 关键字对齐（与 `sql_aligner.py` 一致）

**适用范围**：所有 SELECT 语句（主查询、子查询、CTE）

**整块统一（闸门）**：选列区逐行按「句首 ref → 列别名 `as` 前」量字符长，若极差 ≤ `SELECT_AS_UNIFY_HEAD_CHAR_SPAN_MAX`（默认 50），则该块**不分档**，所有 `as` 同一列。

**分级标准**（否则；阈值对应 `SHORT_FIELD_MAX` / `MEDIUM_FIELD_MAX`）：

- 短：`tier_len` ≤ 50
- 中：50 < `tier_len` ≤ 100
- 长：`tier_len` > 100

其中 **`tier_len`** 为与闸门同源的显示宽度（`_field_gate_rel_display_width`）；**组内目标列**为 `max(gate_abs_end)+AS_SPACING`（见 `skill.md` §2.2）。

**对齐规则**：

- 同组内 AS 关键字垂直对齐
- 不同组 AS 可以在不同列
- 短字段 AS 列 < 中字段 AS 列 < 长字段 AS 列（整块统一时除外）

**示例**：

```sql
select user_id        as user_id        -- 短字段组
     , operator_email as operator_email
     , status         as frozen_status
     , from_unixtime(cast(time_created / 1000 as bigint), 'yyyy-MM-dd') as created_date  -- 中字段组
     , from_unixtime(cast(time_updated / 1000 as bigint), 'yyyy-MM-dd') as updated_date
from table_name as a
;
```

### 2. CREATE TABLE 列定义对齐

**适用范围**：所有 CREATE TABLE 语句

**对齐规则**：

- 列名与数据类型间隔：最长列名 + 至少 6 个空格
- 所有数据类型起始位置垂直对齐
- 所有 COMMENT 关键字起始位置垂直对齐

**计算公式**：

```
数据类型列 = 缩进(2) + 逗号空格(2) + 最长列名长度 + 6
COMMENT 列 = 数据类型列 + 最长数据类型长度 + 1
```

**示例**：

```sql
create table if not exists dm_id.dm_id_ad_df_callback_convert_monitor
(
  observation_date         string        comment '观测日期'
, ad_event_code            string        comment '海鱼事件code'
, media_ad_event_code      string        comment '媒体事件名'
, convert_count            decimal(22,6) comment '转化数'
, convert_value            decimal(22,6) comment '转化价值'
, payout_principal         decimal(22,6) comment '放款金额'
) comment '投放事件转化统计-回传监控报表'
partitioned by (`dt` string)
stored as orc;
```

## 工作流程建议

### 场景 1：格式化新 SQL 文件

```bash
python3 sql_aligner.py new_file.sql
python3 sql_aligner.py new_file.sql --verify-only
```

### 场景 2：仅修复 AS 对齐

```bash
python3 sql_aligner.py file.sql --as-only
```

### 场景 3：仅修复建表语句

```bash
python3 sql_aligner.py file.sql --table-only
```

### 场景 4：代码审查/提交前检查

```bash
python3 sql_aligner.py file.sql --verify-only
```

## 技术细节（简述）

### AS 对齐算法

1. **字段检测**：自动检测所有 SELECT 块
2. **整块闸门**：`select_block_unify_as_by_head_char_span` — 极差 ≤ 50 则整块单列 `as`
3. **字段分组**（否则）：按 `tier_len` 分短/中/长；无闸门宽度时回退 `field_len`（`analyze_select_block`）
4. **字段起始与表达式**：`parse_select_field` + `align_fields_in_place`；**目标列**用 `max(gate_abs_end)+AS_SPACING`（`calculate_target_as_column`）
5. **对齐执行**：调整空格使同组内 AS 精确垂直对齐
6. **验证检查**：整块统一时验全块 `as` 一列；分档时验组内一致及短/中/长相对位置

### 建表语句对齐算法

1. **表检测**：自动检测所有 CREATE TABLE 语句
2. **列分析**：提取列名、数据类型、COMMENT
3. **目标计算**：数据类型列 = 2 + 2 + max(列名长度) + 6；COMMENT 列 = 数据类型列 + max(数据类型长度) + 1
4. **对齐执行**：调整空格使列定义精确对齐
5. **验证检查**：数据类型位置一致性、COMMENT 位置一致性、列名与数据类型间隔 ≥ 6 空格

## 常见问题（摘录）

### Q: 为什么验证显示「仍有问题」但看起来已经对齐？

**A**：可能含特殊多行函数、隐藏制表符或旧版本工具。可先重新格式化；仍失败则对照 `docs/KNOWN_ISSUES.md` 按行排查。

### Q: 如何处理包含复杂 CASE WHEN 的字段？

**A**：分档用 **`tier_len`**（含 `as` 的那一行上，从闸门 **ref** 到列别名 `as` 前的显示宽度）。跨行且 `as` 在续行时按续行闸门宽度分档（见 `skill.md` §2.2）。整块极差 ≤50 时不分档。

### Q: 子查询的对齐规则是什么？

**A**：每个 SELECT（主查询、子查询、CTE）独立应用分级对齐；子查询内行首逗号与同块 `select`（或 `group by`）首字段列对齐。若上一字段为 **`end` 换行后再单独一行 `) as alias`**，见 **Issue #4**。

## 相关文档

- `skill.md` — 完整 SQL 格式规范
- `docs/KNOWN_ISSUES.md` — 已知问题与解决方案
- `docs/pycharm_font_fix.md` — PyCharm 字体配置指南
- 格式规范参考：HiveQL 标准

## 故障排查

遇到对齐问题优先查看 **`docs/KNOWN_ISSUES.md`**。

## 许可

内部工具，仅供团队使用。
