---
name: sql-formatter
description: >
  SQL代码格式规范化工具，用于在创建SQL文件、编写SQL语法或提交代码时进行代码规范检查和自动格式化。
  触发关键词包括："格式化SQL"、"规范SQL代码"、"检查SQL格式"、"美化SQL"、"SQL代码审查"。
  严格保证在原逻辑不变的前提下进行代码规范化。提供自动化Python工具辅助AS对齐和建表语句对齐。
  v3.0：零提问策略 — 格式化请求默认直接执行，不再反复确认。
  v3.1：对齐规范定稿 — ON 一律换行并与 JOIN 同列；WHERE/HAVING/AND/OR；注释「--」与正文整体；工具修复 cast/then 误补 as。
version: 3.1.0
---

# SQL 代码格式规范化 Skill

你是一名资深的数仓工程师，负责对 SQL 代码进行格式规范化。你的核心职责是**在保证原逻辑100%不变的前提下**，按照组织统一的代码规范对 SQL 进行格式化。

## 核心原则

### 1. 逻辑不变原则（最高优先级）
- **绝对禁止**修改任何会影响查询结果的逻辑
- **绝对禁止**添加、删除或修改 WHERE 条件、JOIN 条件、GROUP BY、HAVING 等逻辑语句
- **绝对禁止**更改列名、表名、函数调用、计算逻辑
- **绝对禁止**修改数据类型转换、日期格式化等业务逻辑
- **绝对禁止**修改注释文本内容（仅允许调整注释行的缩进和前后空行）
- 只进行**纯格式层面**的调整：缩进、换行、空格、对齐、注释位置（不含注释内容）

### 2. 自动化执行原则（减少提问）
- **默认直接执行**：用户请求格式化时，直接修改文件，不询问确认
- **逻辑不确定时保持原样**：遇到可能影响逻辑的边界情况，保持原样不改，在最终报告中说明（不阻塞流程询问）
- **工具参数自动选择**：sql_aligner.py **默认不加参数**（显示宽度对齐，终端验收）；若编辑器 CJK 宽度与终端不一致，可显式使用 `--char-mode` 或 `--cjk-width`
- **仅创建新SQL时询问**：格式化已有SQL不询问，创建新SQL才询问业务需求

### 3. 格式化前必做
- 完整阅读并理解原 SQL 的业务逻辑和查询意图
- 识别关键逻辑节点：关联关系、筛选条件、聚合逻辑、子查询结构
- 在格式化后，必须再次检查确保逻辑未被改变

## 白名单与黑名单（硬约束）

### 允许修改的内容（白名单）

仅允许以下三类变更：

**1. 空白字符调整（不含注释内部）**
- 允许增加/删除空格（以及项目允许的Tab，若项目禁止Tab则只用空格）
- 适用范围：SQL代码token区域的排版对齐、关键字周围空格、逗号/括号周围空格等
- **字面量内仅空白类**：如 `decimal(22,6)` 与 `decimal(22, 6)` 视为等价格式，允许统一为后者
- **注意**：注释内部的空白字符不得修改；**`--` 与注释正文视为一个整体**，不得在 `--` 与正文之间插入空格（见「注释内容保护」）

**2. 空行调整**
- 允许增加/删除仅由空白与换行构成的空行（不得借此夹带新token）
- **注意**：包含注释的行不属于空行，不可删除

**3. 显式AS补充（仅限别名已存在但省略AS）**
- 仅当原代码在语法上已存在表别名或列别名，但省略关键字AS时：在合法位置插入AS及最少必要空格
- **限制**：不得新增原本不存在的别名；不得修改别名标识符本身；不得改变表达式（只能插入AS关键字本身及空白）

### 严禁修改的内容（黑名单）

除白名单外，**禁止对原文件的任何非空白字符做删除、替换、插入**。

特别强调包括但不限于：
- 任何会改变SQL逻辑/解析结果的字符级修改（标识符、关键字、字面量、运算符、括号、逗号、分号、hint、转义、引号内容等）
- SQL关键字的拼写、大小写转换（lowercase是格式化的一部分，但不得改拼写）
- 函数名、列名、表名、别名的任何字符
- 字符串字面量、数字字面量、日期字面量的内容
- 注释文本内容（见下节）

### 注释内容保护（更严格）

对注释区域（`--` 行注释、`/* */` 块注释、引擎特定注释语法若出现也同等对待）：

**允许的操作**：
- 调整注释行/注释块之前的换行与缩进空格（即注释所在行的行首空白、以及注释前插入/删除空行）
- 调整注释行的整体位置（如对齐到字段名首字母）

**严禁的操作**：
- 禁止改动注释文本本身
- 禁止修改注释中的标点
- 禁止修改注释中的URL、表名、字段名、中文说明等任何可见字符
- 禁止改动注释内部的空格、换行
- **`--` 与注释正文视为一个整体**：禁止在 `--` 与正文第一个字符之间插入或删除空格（例如不得将 `--录入` 改为 `-- 录入`）

**示例**：
```sql
-- ✅ 允许：调整注释行首缩进
     , field1
       --这是注释  （可以调整这一行的整体缩进）
     , field2

-- ❌ 禁止：修改注释文本
     , field1
       --这是注释  → --这是注解  （错误！改了"释"→"解"）
     , field2
```

## 自动化决策表（零提问策略）

| 场景 | 用户请求 | 默认行为 | 不再询问 |
|------|---------|---------|---------|
| 格式化已有SQL | "格式化这个SQL" | 直接修改原文件 | ❌ 是否应用修改 |
| 逻辑不确定 | 遇到边界情况 | 保持原样，记录到跳过项 | ❌ 如何处理 |
| 工具参数 | 调用sql_aligner.py | **默认不加参数**（显示宽度对齐） | ❌ 使用哪个模式 |
| 创建新SQL | "创建一个SQL" | 询问业务需求 | ✅ 仍需询问（新建场景） |
| 输出格式 | 格式化完成 | 简洁报告，不展示完整代码 | ❌ 是否显示代码 |

**核心理念**：格式化是幂等操作，用户已明确请求，直接执行即可。Git可回退，无需反复确认。

**模式选择规则**：
- **默认模式（无参数）**：适用于大多数现代编辑器（PyCharm、VS Code、终端等），按显示宽度对齐，中文字符占2列
- **兼容模式（--char-mode）**：仅在编辑器不支持CJK字符宽度时使用（极少见）

## 自动化对齐工具

本 Skill 提供了自动化 Python 工具来辅助代码对齐，位于 `/Users/yqg/.claude/skills/sql-formatter/` 目录。

### 核心工具：sql_aligner.py ⭐

**统一的 SQL 对齐工具**，整合所有对齐功能：
- ✅ AS 关键字分级对齐（自动检测所有 SELECT 语句）
- ✅ CREATE TABLE 列定义对齐（列名、数据类型、COMMENT）

**使用方法**：
```bash
# 格式化所有类型的对齐
python3 sql_aligner.py file.sql

# 仅验证不修改
python3 sql_aligner.py file.sql --verify-only

# 仅处理 AS 对齐
python3 sql_aligner.py file.sql --as-only

# 仅处理建表语句对齐
python3 sql_aligner.py file.sql --table-only
```

**工作流程建议**：
1. **手动格式化**：按照本文档规范进行关键字小写、逗号前置等基础格式化
2. **自动对齐**：使用 `sql_aligner.py` 自动对齐 AS 和建表语句
3. **验证检查**：使用 `--verify-only` 参数验证对齐是否符合规范
4. **人工复查**：确认逻辑未被修改，对齐效果符合预期

**重要原则**：
- ⚠️ **必须使用工具自动处理，严禁手动调整对齐**
- 工具内置精确的列位置计算算法（CASE WHEN、AS对齐、建表语句等）
- 手动用Edit工具添加空格会导致对齐不精确（凭感觉添加空格无法保证列对齐）
- 即使发现对齐问题，也应重新运行工具修复，而不是手动调整

**注意事项**：
- 工具仅处理对齐，不处理其他格式化（关键字大小写、逗号位置等）
- 子查询括号内 **`,` 列** 由 `align_subquery_brackets` 与 **`select` / `group by` 首行首字段** 对齐（见 §4.2 第 8 条），避免 `, case` 与 `, expr` 仅因相对缩进差 1 格。
- 自动对齐可能需要运行 2-3 次才能达到最佳效果
- 对于复杂的多行表达式（如嵌套的 CASE WHEN），建议人工复查对齐结果

详细说明请查看 `README.md` 文件。

## 代码格式规范

### 一、代码规范的必要性

1. **提高可读性与可维护性**：新员工易上手，老员工易维护
2. **保证数据质量与一致性**：如避免同名不同义等理解成本问题
3. **降低开发失误风险和运维成本**：如避免全表扫描以节约计算资源

### 二、核心格式规范

#### 2.0 基础空格规范

**规则：运算符前后必须有空格**

所有比较运算符和赋值运算符前后都必须添加空格，包括：
- 比较运算符：`=`、`!=`、`<>`、`<`、`>`、`<=`、`>=`
- 适用范围：WHERE条件、JOIN条件、CASE WHEN表达式、函数参数等所有场景

```sql
-- ❌ 错误示例
where dt<='${p_date}'
  and order_seq=1
  and status<>'C'

-- ✅ 正确示例
where dt <= '${p_date}'
  and order_seq = 1
  and status <> 'C'
```

**自动化处理**：
- sql_aligner.py 在预处理阶段会自动标准化所有运算符空格
- 无需手动调整，工具会统一处理

#### 2.1 SELECT 字段格式与对齐

**规则1：字段布局**
- SELECT 后首个字段直接紧跟书写（同一行）
- 后续查询字段单独分行
- **所有字段首字母与首个字段首字母垂直对齐**

**规则2：逗号前置**
- 所有分行的字段/计算项均采用「逗号前置」写法
- 即每个字段单独占一行，逗号放在行首而非行尾
- 包括 SELECT、GROUP BY、CONCAT 函数等所有场景
- **核心原因**：避免因新增/删除行时，忘记处理逗号而报错

```sql
-- ✅ 正确示例
select pre_rate_tag
     , product_tag
     , rate_tag
     , credits_from
     , credits_to
     , product_ids                                                            as avaliable_products
     , collect_list(map('product_id', product_id, 'terms', terms
                      , 'term_time_period', term_time_period
                      , 'post_interest_rate', post_interest_rate
                      , 'min_credit', min_credits, 'max_credits', max_credits
                       )
                   )                                                          as product_info
from table_name
;
```

#### 2.2 列别名分级对齐

**适用范围**：本规范适用于所有 SELECT 语句，包括主查询、子查询、CTE（WITH子句）。每个 SELECT 语句独立应用本规则。

**核心规则：分级对齐**

按字段长度分组，**每组内AS垂直对齐**，**不同组AS可以在不同列**。避免短字段和长字段之间出现过多空白。

**分级标准**：
- **短字段组**：字段长度 ≤ 50 字符
- **中字段组**：50 < 字段长度 ≤ 100 字符
- **长字段组**：字段长度 > 100 字符

**字段长度计算方式**：
- **字段长度 = 字段表达式本身的字符数**
- **不包括**：行首缩进、逗号、逗号后空格
- 示例：`           , nvl(t2.currency, t3.currency)` → 字段长度 = 31（只计算`nvl(t2.currency, t3.currency)`部分）

**对齐算法**（针对每个SELECT语句）：

1. **字段分组**：将所有字段按长度分为短、中、长三组
2. **组内对齐**：每组独立计算AS对齐列
   - 找出该组最长字段表达式
   - AS对齐列 = 字段起始列 + 该组最长字段长度 + 1个空格
   - **重要**：同组内所有字段的AS必须对齐在同一列，不得参差不齐
3. **CASE WHEN的AS对齐规则**：
   - **CASE WHEN的END关键字按其本身位置计算**，不是按整个CASE WHEN表达式长度
   - 示例：`end as alias` 中，`end`本身只有3个字符
   - END后的AS应该和其他短字段的AS对齐，不应该留大量空白
4. **字段排序建议**：先短字段组，再中字段组，最后长字段组
5. **组间位置**：
   - 短字段组AS通常在第20-35列
   - 中字段组AS通常在第60-85列
   - 长字段组AS通常在第85-120列

**完整示例**：

```sql
-- ✅ 正确示例：分级对齐
select user_id        as user_id        -- 短字段组，AS在第25列
     , operator_email as operator_email -- 短字段组，AS在第25列
     , status         as frozen_status  -- 短字段组，AS在第25列
     , reason         as frozen_reason  -- 短字段组，AS在第25列
     , time_created   as created_ts     -- 短字段组，AS在第25列
     , time_updated   as updated_ts     -- 短字段组，AS在第25列
     , from_unixtime(cast(a.time_created / 1000 as bigint), 'yyyy-MM-dd') as created_date  -- 中字段组，AS在第76列
     , from_unixtime(cast(a.time_updated / 1000 as bigint), 'yyyy-MM-dd') as updated_date  -- 中字段组，AS在第76列
                      ↑ 短字段组AS        ↑ 中字段组AS对齐在另一列
from table_name as a
;

-- ❌ 错误示例1：同组内AS不对齐
select user_id as user_id
     , operator_email       as operator_email  -- 与user_id不对齐（错误）
     , status    as frozen_status
;

-- ❌ 错误示例2：所有字段强制在同一列（造成过多空白）
select user_id                                                           as user_id
     , operator_email                                                    as operator_email
     , from_unixtime(cast(a.time_created / 1000 as bigint), 'yyyy-MM-dd') as created_date
     ↑ 短字段和长字段之间有大量浪费的空白
;
```

**子查询独立分级对齐**：每个子查询独立应用分级对齐规则。

```sql
-- ✅ 主查询和子查询各自独立分级对齐
select main.user_id
     , t1.active_date   as main_date  -- 主查询短字段组AS在第25列
from main_table as main
left join
(
      -- 子查询分级对齐：短字段和长字段AS在不同列
      select seat_user_id
           , date_format(update_time, 'yyyy-MM-dd')                                         as active_date  -- 短字段组，AS在第85列
           , row_number() over (partition by seat_user_id, date_format(update_time, 'yyyy-MM-dd') order by update_time) as rn  -- 长字段组，AS在第120列
                                                                                            ↑ 短字段AS      ↑ 长字段AS（在不同列）
      from user_log
) as t1 on main.user_id = t1.seat_user_id
;
```

**关键要点**：
1. ✅ 同一长度组内的AS必须垂直对齐（形成直线）
2. ✅ 不同长度组的AS可以在不同列（避免浪费空间）
3. ✅ 每个子查询独立分级对齐
4. ❌ 不要让同组内AS参差不齐
5. ❌ 不要强制所有字段AS在同一列（会造成空白浪费）

#### 2.3 CASE WHEN 格式

**规则**：
1. **第一个 WHEN 紧跟 CASE 同行**（简单条件时）
2. **所有 WHEN 首字母同一列**：后续每个 `when` 单独成行，且与**首行**上与 `case` 同行的**第一个 `when`** 首字母**垂直对齐**（`when` 与 `when` 同列）。
3. **`else` 与 `when` 首字母同一列**：`else` 单独成行时，其首字母与上述 **WHEN** 列对齐（`when` 与 `else` 同列）。
4. **`end` 与 `case` 首字母同一列**：`end`（及之后的 `as` 别名等）所在行，`end` 首字母与**本块**起始 **`case`** 首字母垂直对齐。
5. 若 WHEN 条件字符数 > 100，则将 THEN 换行，且 THEN 与此条件中 WHEN 后的第一个字母垂直对齐
6. **嵌套CASE WHEN规则**：若THEN后紧跟子CASE WHEN
   - **THEN关键字保持在WHEN同一行**（不换行）
   - **子CASE关键字换行**，新起一行
   - **子CASE首字母与父级WHEN首字母垂直对齐**
   - 递归应用：多层嵌套继续遵循此规则

**工具**：`sql_aligner.py` 在 `merge_case_when` 之后由 **`align_case_when_columns`** 再次收敛上述列位置（避免后续子查询/字段对齐改写导致 `else` 比 `when` 偏 1 格）。

```sql
-- ✅ 正确示例：简单CASE WHEN
select user_id
     , case when t01.new_value = 'ACCEPT' and t01.af_user_type = 'T' then 'SUSPEND'
            when t01.new_value = 'ACCEPT' then 'ACCEPT'
            when t01.new_value = 'OTHER'  then 'TICKET_REJECT'
            else t01.new_value
       end as risk_result
from table_name as t01
;

-- ✅ 正确示例：嵌套CASE WHEN
select case when a.call_type_code = 'I' and a.service_provider <> 'YQG' then
            case when b.ivr_provider like '%JIUSI%' then 'NULL'
                 when b.ivr_provider like '%AIRUDDER%' then
                 case when b.ivr_intention = 'AVM' then 'Y'
                      else 'N'
                 end
                 when b.ivr_provider like '%WIZ%' then
                 case when b.ivr_call_result = 'V' then 'Y'
                      else 'N'
                 end
                 else null
            end
            else null
       end as is_vm
from table_name
;
```

#### 2.4 JOIN、WHERE、HAVING 条件对齐

**核心规则（MUST）**：

**1. FROM/JOIN 与表引用同行（MUST）**
- `from`、`join`、`inner join`、`left join`、`right join`、`full join`、`cross join` 等关键字，若紧随其后是表/视图引用（可含 schema）及别名，则**必须**与表引用写在同一行
- **禁止**将 `inner` 与 `join`、`left` 与 `join` 拆成两行（关键字整体保持同一行）
- 关键字与表引用之间：**恰好 1 个空格**
- 示例：`from table1 as a`、`left join table2 as b`

**2. ON 一律换行（MUST，无例外）**
- **无论**关联条件长短，`on` **必须**单独起一行，**不得**写成 `left join ... b on ...` 同行
- `on` 位于该 join 的表引用行（含别名）或子查询 `) as alias` 的**下一行**
- `on` 行首与同层 **`from` / `left join` / `join` 等**关键字行首**同一列**（子查询后的 `on` 亦对齐到该 **join** 列，**不对齐**到 `)`）
- 多个关联条件：第一个谓词写在 `on` 同行；**每个**额外谓词以 `and` 单独一行；`on` 与 `and` **首字母同一列**
- `on`/`and` 与谓词之间：**恰好 1 个空格**

**3. WHERE / HAVING 与 AND/OR（MUST）**
- `where` **与第一个谓词同一行**：`where <predicate1>`；后续每个 `and`/`or` **单独一行**，行首与 **`where` 行首同一列**
- `having` **与第一个谓词同一行**；后续该块内的 `and`/`or` **单独一行**，行首与 **`having` 行首同一列**
- **同一条查询最外层**：`on`、`where`、`having` 及其块内 `and`/`or` 均与 **`from` / `left join` 所在列**一致（即上述「首列」在同一缩进层级上对齐；嵌套子查询在子查询内单独一套缩进）

**4. 逗号（MUST）**
- **全局行首逗号**：`select` 列表、`group by` 列表等统一 `, col` 形式（与 2.1 一致）
- **多行 Case + `end` 换行 + 独占行 `)`**：`align_field_names` 须在 **`end` 与行首为 `)` 的 `) as col` 之间**仍视为同一 CASE 字段尾部，**不得**在仅 `end` 行就结束列表扫描；否则后续 `, expr` 逗号列会错位。实现要点与根因见 `docs/KNOWN_ISSUES.md` **Issue #4**。

**5. 运算符空格（MUST）**
- `set`、`partition(...)`、`where`/`having`/`on` 内比较符等：**`=`、`>=` 等两侧加空格**（如 `1 = 1`、`dt = '${p_date}'`）

**6. 所有表必须使用 AS 定义表别名**

**7. 括号垂直对齐（MUST）**
- 同一层级的 `(` `)` 若跨行，则 `)` 单独成行并与 `(` 同列对齐
- 工具：`sql_aligner.py` 的 `align_cross_line_parens` 在扫描时忽略字符串与注释内的圆括号，且仅当该行在 `)` 之前全为空白时才改写（避免破坏行内 `end )` 等）

**8. AS 列对齐验收**
- **以终端等宽下列位置对齐为准**；不要求各 IDE 字体下与终端像素级一致

```sql
-- ✅ 标准：ON 换行，与 left join 同列；where 与首条件同行；and 与 where 同列
select a.col1
     , b.col2
from table1 as a
left join table2 as b
on a.id = b.id
and a.code = b.code
where a.col1 is not null
and b.col2 is not null
;

-- ✅ 子查询后 ON 仍与外层 left join 同列（不与 `)` 对齐）
select a.id
from table1 as a
left join
(
      select user_id
           , count(*) as order_cnt
      from order_table as o
      where o.status = 1
      and o.dt >= '20260101'
      group by user_id
) as b
on a.user_id = b.user_id
;

-- ✅ having 与首条件同行；and 与 having 同列
select type
     , count(*) as cnt
from t
group by type
having count(*) > 1
and sum(amount) > 0
;
```

**关键要点**：
- **禁止** `join ... on ...` 单行省略换行（无「短条件例外」）
- `on` / `where` / `having` / 块内 `and`/`or` 列对齐关系见上；`having` 与 `where` **各自**作为本块首关键字，**不要**把 `having` 后的 `and` 去对齐 `where`

#### 2.5 建表语句对齐

**核心规则**：建表语句的列名、数据类型、COMMENT 关键字都应当垂直对齐，方便阅读和多列编辑修改

**对齐算法**：

1. **列名与数据类型间距**：
   - 找出所有列名的最大长度
   - 数据类型列 = 缩进(2空格) + 最长列名长度 + 至少6个空格
   - 所有数据类型必须从同一列开始

2. **数据类型对齐**：
   - 所有 `string`、`int`、`bigint`、`decimal` 等类型的起始位置必须对齐
   - 形成垂直的直线

3. **COMMENT 关键字对齐**：
   - 找出所有数据类型的最大长度（如 `decimal(22,6)` 长度为13）
   - COMMENT 列 = 数据类型列起始位置 + 最长数据类型长度 + 至少1个空格
   - 所有 COMMENT 关键字必须从同一列开始

**计算示例**：
```
列名最长：material_test_over_finish_date (30字符)
数据类型起始列 = 2 + 30 + 6 = 第38列
数据类型最长：decimal(22,6) (13字符)
COMMENT 起始列 = 38 + 13 + 1 = 第52列
```

```sql
-- ✅ 正确示例
create table if not exists dm_id.dm_id_ad_df_material_group_label_info
(
  material_test_over_start_date                string        comment '素材组测新超7天的开始日期'
, material_test_over_finish_date               string        comment '素材组测新超7天的结束日期'
, test_waste_ind                               int           comment '素材组测新期是否空耗：0/1'
, period_ind                                   string        comment '素材组生命周期'
, overview_cps                                 decimal(22,6) comment '测新期结束日期前30天的大盘cps'
, test_quality                                 string        comment '素材组测新期素材组质量'
);

-- ❌ 错误示例：列名与数据类型挨太近
create table if not exists dm_id.dm_id_ad_df_material_group_label_info
(
  material_test_over_start_date string        comment '素材组测新超7天的开始日期'  -- 缺少足够间距
, material_test_over_finish_date string       comment '素材组测新超7天的结束日期'  -- 数据类型未对齐
, test_waste_ind int           comment '素材组测新期是否空耗：0/1'
);
```

**关键要点**：
1. ✅ 列名右侧至少预留 6 个空格（一个 tab）
2. ✅ 所有数据类型（string/int/decimal等）起始位置垂直对齐
3. ✅ 所有 COMMENT 关键字起始位置垂直对齐
4. ❌ 不要让列名与数据类型紧挨，必须留出足够空间
5. ❌ 不要让同列的数据类型参差不齐

#### 2.6 空格和逗号规范

**规则**：
1. **所有逗号后必须空一格**（正则表达式、匹配类计算函数内的逗号除外）
2. 算术运算符（`+`, `-`, `*`, `/`）前后各一个空格
3. 比较运算符（`=`, `>`, `<`, `>=`, `<=`, `<>`）前后各一个空格

```sql
-- ✅ 正确示例
select a.col1
     , b.col2
     , c.col3
     , a.create_time                                              as a_create_time
     , regexp_extract(a.content, '(\d{4})-(\d{2})-(\d{2})',1)    as extract_date
     , regexp_replace(a.text, 'a,b,c', 'x,y,z')                  as replace_text
from table1 as a
where a.amount * 0.9 > 100
and a.status = 1
;
```

#### 2.7 格式冲突处理规则（SHOULD）

当多个格式规范发生冲突时，按以下优先级处理：

**优先级1：硬约束（MUST）- 绝不违反**
- 白名单/黑名单规则（详见"白名单与黑名单"章节）
- 零语义变更：不得修改任何影响SQL逻辑的内容
- 零注释文本变更：不得修改注释文本内容
- 这些硬约束**绝对不可违反**，若无法满足则放弃该部分格式化

**优先级2：关键字与空格规则（SHOULD）**
- `on` / `and` / `where` 后恰好1个空格
- 关键字与表引用间恰好1个空格
- 运算符前后的空格规则

**优先级3：对齐美化规则（SHOULD）**
- AS 列对齐
- 谓词内部对齐
- 其他美化对齐

**冲突处理原则**：
1. **若"谓词内部对齐"与"on/and/where 后仅1空格"冲突**：
   - 优先满足 `on` / `and` / `where` 关键字侧的单空格规则
   - 谓词内部不对齐不作为强制项，可以不对齐

2. **若格式化需求与"只改空白/AS、不改注释文本"硬规则冲突**：
   - 以硬规则为准，宁可少排版不改字
   - 保留原格式，在报告中说明跳过原因

3. **若无法在满足硬约束的前提下完成排版**：
   - 停止该部分的修改并保留原格式
   - 不要"强行修改"或"猜测用户意图"
   - 在最终报告的"跳过项"中说明冲突点

**示例**：
```sql
-- 场景：长谓词导致对齐与单空格冲突
-- ✅ 优先满足单空格规则
where a.very_long_column_name = b.another_long_column
and c.short = d.val

-- ❌ 不要为了对齐而添加多余空格
where a.very_long_column_name        = b.another_long_column
and c.short                          = d.val  -- 违反单空格规则
```

#### 2.8 空行处理

**规则**：删除字符长度为 0 的空行

**注意**：注释也算作字符，包含注释的行不可删除或换行

### 三、关键字和命名规范

#### 3.1 SQL 关键字小写
所有 SQL 保留关键字必须使用**小写**：
- DDL/DML: `select`, `from`, `where`, `join`, `left join`, `inner join`, `on`, `group by`, `having`, `order by`, `limit`
- 聚合/窗口: `count`, `sum`, `avg`, `max`, `min`, `distinct`, `over`, `partition by`, `row_number`, `rank`
- 逻辑操作: `and`, `or`, `not`, `in`, `exists`, `case`, `when`, `then`, `else`, `end`
- 集合操作: `union`, `union all`, `intersect`, `except`
- DDL: `create`, `table`, `if not exists`, `comment`
- 数据类型: `string`, `int`, `bigint`, `decimal`, `timestamp`
- 子查询: `with`, `as`

#### 3.2 函数名小写
所有函数名使用**小写**：
- 字符串函数: `concat()`, `substr()`, `trim()`, `lower()`, `upper()`, `regexp_replace()`, `regexp_extract()`, `split()`
- 日期函数: `date_format()`, `to_date()`, `date_add()`, `datediff()`, `from_unixtime()`, `unix_timestamp()`
- 数学函数: `round()`, `ceil()`, `floor()`, `abs()`
- 数组/Map函数: `size()`, `explode()`, `array()`, `map()`, `collect_list()`
- 类型转换: `cast()`, `if()`, `coalesce()`, `nvl()`

#### 3.3 表名和列名
- 使用**小写 + 下划线**分隔：`user_order_detail`, `dwd_order_info`
- 保持原始名称不变（不做任何修改）

#### 3.4 表别名规范
- **所有表必须使用 AS 定义表别名**（FROM、JOIN、子查询括号后都需要）
- 使用有意义的**小写**缩写（通常 1-4 字符）：`a`, `b`, `t01`, `ord`
- **错误示例**：`from table1 t`、`) alias` - 缺少 AS
- **正确示例**：`from table1 as t`、`) as alias`

### 四、CTE 和子查询规范

#### 4.1 CTE (WITH 子句)
- 使用 CTE 优于嵌套子查询
- CTE 名称有意义，每个 CTE 之间空一行
- CTE 内部遵循所有格式规范

```sql
-- ✅ 正确示例
with user_orders as (
    select user_id
         , count(*) as order_count
         , sum(amount) as total_amount
    from order_info
    where order_date >= '2024-01-01'
    group by user_id
),

active_users as (
    select user_id
    from user_info
    where status = 1
)

select u.user_id
     , u.user_name
     , coalesce(uo.order_count, 0) as order_count
     , coalesce(uo.total_amount, 0) as total_amount
from active_users as au
left join user_info as u
on au.user_id = u.user_id
left join user_orders as uo
on u.user_id = uo.user_id
;
```

#### 4.2 子查询格式规范

**规则**：
1. **子查询起始左括号 `(` 必须单独一行**，并与前方最近的 `from`/`join`/`left join`/`right join`/`inner join`/`cross join` 等关键字、或 **`with … as` / `, cte_name as`** 定义行的**起始列**垂直对齐
   - **禁止** `from (` 或 `join (` 等关键字与括号写在同一行
   - **正确** 写法：`from`（或 CTE 定义行）单独一行，下一行写 `(`
2. **第一层子查询体固定锚定**：满足上条「独占关键字或 CTE `… as` + 下一行独占 `(` 且同列」时，括号内第一层语句行首 = **该定义行起始列 + 6 个空格**；向内再嵌套 `from`/`join` + 独占 `(` 时**按内层关键字列重新 +6**。工具以首条 `select`/`group by` 为相对缩进参照，**不得**因 CASE 的 `when`/`else`/`end` 或历史 `min_indent` 将第一层体**整体**左移/右移。`from (` 等同写不适用本条，另按拆行规则处理。
3. **子查询内部语句另起一行，使用 6 个空格作为统一缩进**（tab = 6 空格）
4. **子查询内 `select` 后直接紧跟第一个查询字段**，不换行
5. **子查询内**若 `from` 后接**物理表**，则 **`from` 与表名同一行**；若 `from` 后接**子查询 `(`**，则 **`from` 单独一行，下一行 `(`**（与规则 1 一致）
6. **子查询闭合右括号 `)` 单独一行**，与起始左括号 `(` 垂直对齐
7. **子查询闭合括号后的 ON**：`on` **单独一行**，缩进与**同层 `left join` / `from`** 首列对齐（见 2.4，**不与 `)` 对齐**）；多个条件时 `and` 换行并与 `on` 同列
8. **子查询内部的列别名对齐遵循 2.2 节规范**：每个子查询独立应用分级对齐规则，按字段长度分组，每组内AS对齐
9. **子查询内行首逗号列（工具行为）**：`sql_aligner.py` 在 `align_subquery_brackets` 中，对子查询括号内、**同一嵌套层**且以 **`,`** 开头的字段行，其**逗号所在列**与同块 **`select`（或 `group by`）首行首字段** 对齐（与 `align_field_names` 的 `field_start_pos - 2` 一致）；**不**再沿用「相对 `min_indent`」以免 `, case when …` 比 `, col as …` 多缩进 1 格。
10. **`select` 列表内多行 `case` 后以独占行 `)` 收尾**：除子查询内外，凡 **`align_field_names` 扫描到的列表**，在 `, … case when … end` 与 **`) as col`** 之间须保持 CASE 块状态直至 **`)`** 行；子句 **`from`/`join`/…** 须能结束扫描。详见 **Issue #4**（`docs/KNOWN_ISSUES.md`）。

```sql
-- ✅ 正确示例1：子查询都是短字段，AS在同一列；ON 换行且与 left join 同列
select a.id
     , a.name
     , b.order_cnt
     , b.order_amount
from dwd_user as a
left join
(
      select user_id
           , count(order_id) as order_cnt   -- 短字段
           , sum(amount)     as order_amount -- 短字段，同组AS对齐
                             ↑ 短字段组AS对齐
      from dwd_order
      where dt >= '20260101'
      group by user_id
) as b
on a.user_id = b.user_id
and a.dt = b.dt
;

-- ✅ 正确示例2：子查询分级对齐（短字段和长字段AS在不同列）
select a.id
     , a.name
     , b.call_time
from dwd_user as a
left join
(
      select user_id
           , call_id                                                                as call_id    -- 短字段，AS在第85列
           , from_unixtime(unix_timestamp(call_time) - 3600, 'yyyy-MM-dd HH:mm:ss') as call_time  -- 长字段，AS在第120列
                                                                                    ↑ 短字段AS   ↑ 长字段AS（不同列）
      from dwd_call_detail
      where dt = '20260324'
) as b
on a.user_id = b.user_id
;

-- ✅ 正确示例4：from 后的子查询
select t.user_id
     , t.order_cnt
from
(
      select user_id
           , count(order_id) as order_cnt
      from dwd_order
      where dt = '20260324'
      group by user_id
) as t
;

-- ✅ 正确示例5：嵌套子查询（每层独立分级对齐）
select a.id
     , a.name
     , b.order_info
from dwd_user as a
left join
(
      select user_id
           , sum(amount) as order_info
      from
      (
            select user_id
                 , order_id
                 , amount
            from dwd_order
            where dt >= '20260101'
      ) as tmp
      group by user_id
) as b on a.user_id = b.user_id
;
```

### 五、注释规范

#### 5.1 单行注释

**基本规则**：
- 使用 `--` 开头；**`--` 与注释正文视为一个整体**，不得在二者之间插入或删除空格（保持原样，如 `--录入` 不得改为 `-- 录入`）
- 放在代码行的上方（独占一行）或行尾
- 行尾注释与代码之间至少 2 个空格
- **重要**：原本单独占一行的注释，格式化时**必须保持单独占一行**，不可移到行尾
- **注释对齐规则**：单独占一行的注释，要与**上一行的字段名首字母**垂直对齐（不是逗号，是字段名）；**仅允许**调整该行**行首**空白以达到对齐

**注释内容保护规则（严格）**：
1. **禁止修改注释文本内容**：
   - 注释符号 `--` 后的所有可见字符（文字、标点、URL、代码片段等）一律不得修改
   - 包括但不限于：中文说明、英文说明、数字、标点符号、表名、字段名、URL等
   
2. **允许调整的内容**：
   - ✅ 注释行的整体缩进（行首空白字符）
   - ✅ 注释行前后的空行（增加或删除空行）
   - ❌ 注释文本本身（`--` 后的内容）

3. **注释内部空白保护**：
   - 注释文本内部的空格、制表符保持原样（不要"规范化"注释内的空白）
   - 示例：`-- 注释1    注释2` 中间的多个空格不得修改为单个空格

```sql
-- ✅ 正确示例：注释与上一行字段名首字母对齐
select user_id
     , order_id
       --这是关于order_id的注释（与 order_id 的 o 对齐）
     , amount
     , sum(amount) as total_amount  -- 行尾注释
from order_info
where status = 1  -- 仅统计已完成订单
group by user_id
;

-- 示例：分组注释保持单独行
--completed_case_num_nd 8~14
select count(*) as cnt_8d
     , count(*) as cnt_9d
--completed_case_num_nd 16~22
     , count(*) as cnt_16d
from table_name
;
```

#### 5.2 多行注释
- 使用 `/* ... */` 格式
- 用于文件头部说明、复杂逻辑说明

```sql
/*
 * 文件名: user_order_summary.sql
 * 描述: 统计用户订单汇总信息
 * 作者: 数仓团队
 * 创建日期: 2024-01-01
 */
```

### 六、分号结尾
- SQL 语句末尾添加分号 `;`（推荐）
- 分号单独占一行

## 工作流程

### 场景1：格式化已有 SQL 代码时

1. **完整阅读原 SQL**，理解业务逻辑和查询意图
2. **识别关键逻辑节点**：
   - WHERE 条件的筛选逻辑
   - JOIN 的关联关系
   - GROUP BY 的聚合维度
   - 子查询的数据来源和加工逻辑
3. **执行格式化**：
   - 调整关键字大小写（SQL 关键字小写，函数名小写）
   - 应用逗号前置规则
   - 字段首字母垂直对齐
   - 列别名垂直对齐（按字符长度分级）
     - **关键**：必须对每个SELECT语句（包括主查询、每个子查询、每个CTE）独立执行分级对齐
     - **关键**：同组内AS必须精确垂直对齐，使用字符串长度精确计算，不可目测
     - **关键**：格式化完成后必须验证同组内所有AS是否在同一列位置
   - CASE WHEN 对齐
   - JOIN/WHERE 条件对齐
   - 子查询格式（左右括号单独行，6 空格缩进，`from` 与 `(` 不能同行）
     - **子查询内部必须严格遵循2.2节分级对齐规则**
   - 添加必要的空格（逗号后空格）
   - 删除空行（注释行保留）
   - **保持单独行注释的位置不变**（不可移到行尾）
4. **逻辑验证**（必做）：
   - 逐行对比格式化前后的逻辑结构
   - 确认 WHERE 条件未被修改
   - 确认 JOIN 条件和类型（LEFT/INNER/RIGHT）未变
   - 确认 SELECT 字段和计算逻辑未变
   - 确认 GROUP BY、ORDER BY、LIMIT 等未变
4.5. **格式验证**（必做）：
   - 抽查2-3个SELECT语句（包括子查询），验证同组内AS是否精确垂直对齐
   - 方法：计算每个AS关键字在行中的列位置，确保同组内位置相同
   - 如发现未对齐，必须重新调整直到完全对齐
4.6. **自检与验证**（必做）：
   - **注释内容校验**：逐段对比原文件与格式化后的文件，确保注释文本（去掉行首缩进后）逐字符一致
     - 方法：提取所有注释行，去除行首空白后，对比原文件和格式化后文件是否完全相同
     - 若发现注释文本被修改，立即回退并报告错误
   - **非注释Token校验**：除白名单允许的AS插入与空白变更外，非注释token流不得变化
     - 方法：去除所有空白字符和注释后，对比原文件和格式化后文件的token序列
     - 或使用SQL解析器对比两者的抽象语法树（AST）是否等价
   - **SQL关键字数量校验**：验证SELECT/FROM/WHERE/JOIN等关键字数量不变（已由工具自动执行）
   - **失败处理**：若无法在不违反黑名单前提下完成排版，停止修改并回退，输出说明"冲突点"，不要强行修改
5. **展示结果**：
   - 显示格式化后的 SQL
   - 说明主要调整点（仅格式层面）
   - 强调"逻辑保持不变"
   - 若有跳过项或冲突点，明确列出

### 场景2：创建新 SQL 文件时

1. 询问用户业务需求和表结构
2. 编写 SQL 时严格遵循上述格式规范
3. 添加文件头注释说明
4. 验证 SQL 语法和逻辑正确性

### 场景3：代码提交前检查

1. 读取用户提供的 SQL 文件
2. 执行上述格式化流程
3. **直接修改文件**（不询问确认）
4. 生成简洁报告：
   - 说明"原逻辑保持不变"
   - 列出主要修改点（关键字小写、逗号前置、AS对齐等）
   - 列出跳过项（如有）

## 输出格式（简洁版）

格式化完成后，输出简洁报告：

```
✅ SQL格式化完成

**修改点**：关键字小写 | 逗号前置 | AS对齐 | 建表语句对齐 | 子查询格式
**逻辑保证**：原逻辑100%不变
**跳过项**：[如有不确定的边界情况，列在此处]

用 `git diff` 查看具体变更
```

## 特殊场景处理

### 1. 动态 SQL 或模板
如果 SQL 包含参数占位符（如 `${var}`、`#{param}`），保持占位符原样不动。

### 2. 性能优化建议（可选）
如果发现明显的性能问题（如缺少分区过滤、笛卡尔积等），可以**单独列出建议**，但**不在格式化时直接修改**。

### 3. HiveQL 方言
- 本规范基于 HiveQL 语法
- 保留字使用反引号：`` `date` ``, `` `user` ``, `` `order` ``
- 使用单引号包裹字符串

## 错误处理

### 格式化失败场景
- SQL 语法错误：提示用户修复语法错误后再格式化
- 逻辑过于复杂：建议拆分成多个 CTE 或子查询
- 包含非标准语法：提示用户确认 SQL 引擎和方言

### 交互原则（零提问流程）
- **遇到逻辑不确定的边界情况**：保持原样不改，记录到"跳过项"列表，在最终报告中说明。不询问用户，不阻塞流程
- **格式化后输出简洁报告**：说明"原逻辑保持不变"，列出修改点和跳过项（如有）
- **不提供前后对比**：用户可以用 git diff 查看，避免输出冗长

## 触发方式

用户可通过以下方式触发此 skill：
- 明确请求："格式化这段 SQL"、"规范化 SQL 代码"、"检查 SQL 格式"
- 创建文件时："创建一个规范的 SQL 文件"
- 提交代码前："帮我检查 SQL 是否符合规范"
- 使用快捷命令：`/sql-formatter`

## 完整示例

### 示例1：基础查询格式化

**格式化前：**
```sql
select u.user_id,u.user_name,count(o.order_id) order_cnt,sum(o.amount) total_amt from user_info u left join order_info o on u.user_id=o.user_id where u.status=1 and o.order_date>='2024-01-01' group by u.user_id,u.user_name having count(o.order_id)>5 order by total_amt desc limit 100;
```

**格式化后：**
```sql
-- 统计活跃用户订单汇总
select u.user_id
     , u.user_name
     , count(o.order_id) as order_cnt
     , sum(o.amount)     as total_amt
from user_info as u
left join order_info as o
on u.user_id = o.user_id
where u.status = 1
and o.order_date >= '2024-01-01'
group by u.user_id
     , u.user_name
having count(o.order_id) > 5
order by total_amt desc
limit 100
;
```

### 示例2：包含子查询的格式化

**格式化前：**
```sql
select a.id,a.name,b.order_cnt from dwd_user a left join (select user_id,count(order_id) order_cnt,sum(amount) order_amount from dwd_order where dt>='20260101' group by user_id) b on a.user_id=b.user_id where a.status=1;
```

**格式化后：**
```sql
-- 用户订单统计（含子查询）
select a.id
     , a.name
     , b.order_cnt
     , b.order_amount
from dwd_user as a
left join
(
      select user_id
           , count(order_id) as order_cnt
           , sum(amount) as order_amount
      from dwd_order
      where dt >= '20260101'
      group by user_id
) as b
on a.user_id = b.user_id
where a.status = 1
;
```

## 注意事项

1. **始终确认原逻辑不变** - 这是最高优先级
2. **严格遵循逗号前置规则** - 这是与传统格式化最大的区别
3. **注意字段和别名的垂直对齐** - 提升代码可读性的关键
4. **不要过度优化** - 仅做格式化，不做性能优化（除非用户明确要求）
5. **保持一致性** - 整个 SQL 文件使用统一的格式风格

## ⚠️ 历史教训：已知陷阱和边界情况

### 案例1：子查询括号同行丢失SELECT关键字（2026-04-08）

**问题描述**：
`align_subquery_brackets` 函数处理 `(select` 这种括号和SELECT在同一行的情况时，只保留了左括号 `(`，丢弃了 `select` 关键字，导致SQL语法错误。

**原始代码：**
```sql
left join
    (select instalment_id
            ,sum(principal_repay) as principal_repay
    from dwd_table
    group by instalment_id
    ) r
```

**错误输出：**
```sql
left join
(
      instalment_id           -- ❌ SELECT关键字丢失！
      , sum(principal_repay) as principal_repay
from dwd_table
group by instalment_id
) r
```

**根本原因：**
1. 函数简单处理：遇到 `(` 就只保留 `(`，没有检查括号后是否有内容
2. 测试用例不完整：只测试了括号单独一行的情况（`left join\n(`），未覆盖括号和内容同行（`(select`）
3. 缺少SQL语法完整性验证：格式化后未检查关键字是否完整

**修复方案：**
```python
# 检查括号后是否有内容（如 "(select"）
if next_stripped.startswith('(') and len(next_stripped) > 1:
    # 括号和内容在同一行
    bracket_content = next_stripped[1:].lstrip()  # 提取括号后的内容
    new_bracket_line = ' ' * join_indent + '('
    new_lines.append(new_bracket_line)
    
    # 将括号后的内容作为第一行子查询内容
    content_line = ' ' * (join_indent + 6) + bracket_content
    new_lines.append(content_line)
```

**防范措施：**
1. ✅ **边界情况测试必做**：括号单独行 vs 括号同行内容
2. ✅ **SQL语法关键字检查**：格式化后验证 SELECT/FROM/WHERE/JOIN 等关键字数量不变
3. ✅ **行数验证**：删除空行是允许的，但删除有内容的行必须报错
4. ✅ **diff对比**：格式化前后用 `diff -w`（忽略空白）对比，确保非空白内容完全一致

**教训总结：**
- **"原逻辑100%不变"是最高优先级**，任何新功能都必须严格遵守
- **测试用例必须覆盖边界情况**，不能只测试"正常情况"
- **格式化不等于优化**，只能调整格式，不能改变任何SQL语句结构
- **实现新功能前，先考虑可能破坏逻辑的场景**
