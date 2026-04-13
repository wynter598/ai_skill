# SQL 代码格式规范化工具集

本工具集用于自动化 SQL 代码格式规范检查和对齐。

## v3.1 规范摘要（与 `skill.md` 同步）

- **ON**：一律单独成行，与同层 `from` / `left join` / `join` 等**首列对齐**；子查询 `) as alias` 后的 `on` 亦对齐到该 **join** 列（不与 `)` 对齐）；无「条件短则与 join 同行」例外。
- **WHERE / HAVING**：各自与**第一个谓词同一行**；该块内后续 **`and` / `or`** 单独成行，且与同块的 **`where` 或 `having`** 首列对齐。
- **逗号**：**全局行首逗号**（`select`、`group by` 等列表风格一致）；**子查询括号内**以 `,` 开头的行，**逗号列**与同块 **`select` / `group by` 首行首字段** 对齐（`align_subquery_brackets`，避免 `, case` 与 `, col` 差 1 格）；**多行 `case … end` 后独占行 `) as col`** 时，`align_field_names` 须把 `end` 与 `)` 视为同一字段尾部，否则后续行首逗号会错位（见 `docs/KNOWN_ISSUES.md` **Issue #4**）。
- **关键字**：**禁止**将 `inner join`、`left join`、`group by` 等拆成两行。
- **运算符空格**：`set`、`partition(...)`、条件中的 `=`、`>=` 等由工具预处理为两侧加空格（与规范一致）。
- **注释**：**`--` 与注释正文视为一个整体**，不得在 `--` 与正文之间插入或删除空格；仅允许调整**行首缩进**及注释前后空行。
- **CASE**：`case` 与 `end` 首字母同列；所有 `when` 与 `else` 首字母同列（工具 `align_case_when_columns`，在字段/子查询对齐之后执行）。
- **跨行圆括号**：`align_cross_line_parens` 在预处理中执行；跨行匹配的 `)` 与对应 `(` 同列，扫描时忽略引号/反引号/注释内的括号，且仅当该行 `)` 前全为空白时才改写。
- **验收口径**：`sql_aligner.py` **默认不加参数**，**以终端等宽字体下的 `as` 竖线对齐为准**；与 IDE 视觉差异见下一节。

## 中文（CJK）与多 IDE 中的列别名缩进

当某一行内出现**中文字符**（例如中文注释、中文字符串字面量、或字段表达式里含中文）时，工具会按 `unicodedata` 东亚宽度规则计算**显示宽度**（默认宽字符约 **2 个 ASCII 列宽**），再据此插入空格，使 **`as` 与别名列对齐**。

**现象**：同一文件在**终端**里往往竖线对齐，但在 **PyCharm、VS Code、Cursor** 等不同 IDE 中，由于**字体 metrics、CJK 是否等宽、缩放比例**等差异，同一行里中文的**实际占位**可能与工具采用的宽度**不一致**，于是会出现：**终端里列别名对齐，在 IDE 里看起来略偏左或略偏右**。这不表示 SQL 被改坏，而是**不同环境下的「列」定义不同**（显示宽度 vs 像素宽度）。

**可选处理**：

1. **团队约定**：以 **终端 / CI 日志** 下的对齐为验收标准（当前默认）。
2. **本地 IDE 更接近终端**：可尝试 `--cjk-width 1.5` 或 `1.33` 等（见版本历史 v2.1 与 `docs/KNOWN_ISSUES.md` Issue #1）。
3. **不按显示宽度、按字符个数对齐**：使用 `--char-mode`（每个字符占 1 列），IDE 与终端观感可能更接近，但与「宽字符占 2 列」的终端规则不一致，需团队统一。

## 工具文件说明

### 核心工具

#### `sql_aligner.py` ⭐ 推荐使用
**统一的 SQL 对齐工具**，整合了所有对齐功能：
- ✅ AS 关键字分级对齐（SELECT 语句）
- ✅ CREATE TABLE 列定义对齐（列名、数据类型、COMMENT）
- ✅ 跨行圆括号列对齐（`align_cross_line_parens`，忽略字符串与注释内括号）

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

# 组合使用：仅验证 AS 对齐
python3 sql_aligner.py file.sql --as-only --verify-only
```

## 对齐规则说明

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
# 1. 先运行完整格式化（包含关键字小写、逗号前置等）
python3 sql_aligner.py new_file.sql

# 2. 验证结果
python3 sql_aligner.py new_file.sql --verify-only
```

### 场景 2：仅修复 AS 对齐
```bash
# 如果建表语句已经对齐，只需要修复 AS
python3 sql_aligner.py file.sql --as-only
```

### 场景 3：仅修复建表语句
```bash
# 如果 AS 已经对齐，只需要修复建表语句
python3 sql_aligner.py file.sql --table-only
```

### 场景 4：代码审查/提交前检查
```bash
# 验证所有对齐是否符合规范
python3 sql_aligner.py file.sql --verify-only
```

## 技术细节

### AS 对齐算法

1. **字段检测**：自动检测所有 SELECT 块
2. **整块闸门**：`select_block_unify_as_by_head_char_span` — 极差 ≤ 50 则整块单列 `as`
3. **字段分组**（否则）：按 `tier_len`（闸门同源 ref→`as` 前显示宽）分短/中/长；无闸门宽度时回退 `field_len`（`analyze_select_block`）
4. **字段起始与表达式**：`parse_select_field` + `align_fields_in_place` 的 `prefix`/`field_expr` 仍用于改写行内空格；**目标列**用 `max(gate_abs_end)+AS_SPACING`（`calculate_target_as_column`）
5. **对齐执行**：调整空格使同组内 AS 精确垂直对齐
6. **验证检查**：
   - 整块统一时验全块 `as` 一列；分档时验组内一致及短/中/长相对位置

### 建表语句对齐算法

1. **表检测**：自动检测所有 CREATE TABLE 语句
2. **列分析**：提取列名、数据类型、COMMENT
3. **目标计算**：
   - 数据类型列 = 2 + 2 + max(列名长度) + 6
   - COMMENT 列 = 数据类型列 + max(数据类型长度) + 1
4. **对齐执行**：调整空格使列定义精确对齐
5. **验证检查**：
   - 数据类型位置一致性
   - COMMENT 位置一致性
   - 列名与数据类型间隔 ≥ 6 空格

## 常见问题

### Q: 为什么同一SELECT块中某些字段的AS没有对齐？

**A**: 这是v1.0之前版本的已知漏洞，已在v1.1中修复。

**问题原因**：旧算法使用 `缩进 + 2` 来估算字段起始位置，但实际上：
- SELECT 行的字段前面是 `select `（7个字符）
- 逗号前置行的字段前面是 `, `（2个字符）

当缩进不同但字段起始位置相同时，旧算法会错误计算AS目标列。

**解决方法**：使用v1.1或更高版本的 `sql_aligner.py`，该版本精确计算每个字段的实际起始位置。

### Q: 为什么验证显示"仍有问题"但看起来已经对齐？

**A**: 可能的原因：
1. 包含特殊的多行函数调用（如 array() 函数）
2. 有隐藏的制表符或特殊空格字符
3. 使用的是旧版本工具（请升级到v1.1+）

**解决方法**：
```bash
# 重新运行格式化
python3 sql_aligner.py file.sql

# 如果还有问题，检查具体行号的内容
```

### Q: 如何处理包含复杂 CASE WHEN 的字段？

**A**: 分档用 **`tier_len`**（含 `as` 的那一行上，从闸门 **ref** 到列别名 `as` 前的显示宽度），不是简单手数「整条表达式 stripped 长度」。`tier_len` 很大时入长档；**跨行且 `as` 在续行**时按续行闸门宽度分档（见 `skill.md` §2.2）。整块极差 ≤50 时不分档。

### Q: 子查询的对齐规则是什么？

**A**: 每个 SELECT 语句（包括主查询、子查询、CTE）都独立应用分级对齐规则。嵌套的子查询会被分别检测和对齐。子查询内行首逗号与同块 `select`（或 `group by`）首字段列对齐，含 `, case when …` 与 `, cast(x as type)` 等行，避免与上一简单字段行错位。若上一字段为 **`end` 换行后再单独一行 `) as alias`**，工具对 `in_case_block` 与列表结束的判断见 **Issue #4**。

## 版本历史

- **v3.1** (2026-04-11) 🔧
  - 📌 与 `skill.md` 定稿对齐：**ON 一律换行**；**WHERE / HAVING** 与 **AND/OR** 列规则；**全局行首逗号**；注释 **`--` 与正文整体**等（见上文「v3.1 规范摘要」）。
  - 🐛 **工具**：`add_missing_as_keywords` 跳过含 `CASE` / `WHEN…THEN` 的行，避免误插 `then as col`；`parse_select_field` 跳过 `cast(` 未闭合内的 `as`，避免破坏 `cast(x as type)`；**HAVING** 参与 AND/OR 缩进；子查询后 **ON 与 JOIN 同列**（不再与 `)` 对齐）；**`align_cross_line_parens`** 接入流水线（闭行前全空白、`cc==0`、行尾 `--` 无换行等边界修复）。
  - 📐 **AS**：选列闸门极差 ≤50 时整块单列 `as`；否则分档用 **`tier_len`**（与闸门同源），组内目标列用 **`gate_abs_end`**（`analyze_select_block` / `calculate_target_as_column`）；`skill.md` §2.2 与 README 本节已同步。
  - 📄 **文档**：`docs/KNOWN_ISSUES.md` 含 Issue #2、**#4**（多行 case + 独占 `)` 后行首逗号错位）；README **v3.1 摘要**与 **CJK / 多 IDE 列别名视觉差异**说明。

- **v2.5** (2026-04-01) 🔧
  - 🔧 固化对齐计算逻辑到代码中，避免依赖AI理解偏差
  - 问题：parse_select_field()中else分支使用len()计算字符数，应该用get_width()计算显示宽度
  - 示例：`       end as alias` 中，行首7个空格应按显示宽度计算，而非字符数
  - 解决：修改else分支，使用get_width(indent)计算行首缩进显示宽度
  - 效果：END行、短字段、长字段的AS位置自动按算法精确对齐，不依赖AI判断

- **v2.4** (2026-04-01) 🐛
  - 🐛 修复round()应用，避免CJK 1.5倍宽度产生的小数截断问题
  - 在align_fields_in_place()中使用round(spaces_needed)代替int(spaces_needed)

- **v2.3** (2026-04-01) 🐛
  - 🐛 修复多重嵌套AS关键字识别bug
  - 问题：工具使用 `re.search()` 匹配第一个AS，导致包含cast类型转换等多个AS的字段被错误截断
  - 示例：`cast(hash(user_id) % cast('x' as bigint) as bigint) as bucket_id` 被截断为 `cast(hash(user_id) % cast('x'`
  - 解决：改用 `re.finditer()` 找到所有AS，取最后一个作为真正的别名关键字
  - 效果：正确处理包含嵌套cast/类型转换的复杂字段表达式

- **v2.2** (2026-04-01) 🐛
  - 🐛 修复float类型空格计算bug
  - 问题：`spaces_needed` 是float类型，无法直接用于 `' ' * spaces_needed` 字符串乘法
  - 解决：在 `align_fields_in_place()` 中使用 `int(spaces_needed)` 转换为整数
  - 澄清：**字段长度 = 字段表达式本身字符数，不包括行首缩进、逗号、空格**
  - 效果：修复 `TypeError: can't multiply sequence by non-int of type 'float'` 错误

- **v2.1** (2026-04-01) 🔧
  - ✨ 新增 `--cjk-width` 参数，支持自定义中文字符宽度比例
  - 问题：PyCharm部分字体渲染中文字符为1.5倍宽度（而非标准2倍），导致视觉对齐偏移
  - 解决方案：允许用户指定CJK字符宽度比例
    - `python3 sql_aligner.py file.sql --cjk-width 1.5`（PyCharm）
    - `python3 sql_aligner.py file.sql`（终端，默认2.0）
  - 使用场景：
    - **终端查看**：不加参数（默认2.0）
    - **PyCharm中AS向左偏移**：使用 `--cjk-width 1.5`
    - **完全不支持CJK宽度**：使用 `--char-mode`（等同于1.0）

- **v2.0** (2026-04-01) ⭐
  - ✨ 新增字符位置对齐模式（`--char-mode`）
  - 问题：不同编辑器对CJK字符宽度渲染不同，导致视觉对齐不一致
  - 解决方案：提供两种对齐模式
    - **默认模式（推荐）**：按显示宽度对齐，中文字符占2宽度，适合终端和正确配置CJK的编辑器
    - **兼容模式（--char-mode）**：按字符位置对齐，不考虑字符宽度，适合不支持CJK字符宽度的编辑器（如某些 IDE 配置）
  - 使用场景：
    - 在终端查看：不使用 `--char-mode`（默认）
    - 在 PyCharm/VS Code 等编辑器查看：根据实际渲染效果选择参数

- **v1.4** (2026-03-31)
  - 🐛 修复AS位置计算漏洞，在`parse_select_field()`中使用`get_width()`计算AS位置
  - 问题：AS的字符位置和显示宽度位置计算不一致
  - 解决：统一使用显示宽度计算所有位置
  - 效果：中文字符AS对齐在正确的显示宽度列

- **v1.3** (2026-03-31)
  - 🐛 添加`display_width()`函数，在`analyze_select_block()`中使用显示宽度计算字段长度
  - 问题：`len()`只返回字符数，中文字符占2显示宽度但`len()`返回1
  - 解决：使用`unicodedata.east_asian_width()`检测全角字符
  - 效果：正确计算包含中文字符的字段长度

- **v1.2** (2026-03-31)
  - 🐛 修复CREATE TABLE验证函数bug：精确定位数据类型和COMMENT位置
  - 问题：验证函数使用 `match.start() + 1` 定位数据类型，实际定位到的是前导空格位置
  - 解决：在 `verify_create_table_alignment()` 中直接匹配数据类型本身，使用 `match.start()` 获取精确位置
  - 效果：验证结果现在与实际对齐状态一致

- **v1.1** (2026-03-31)
  - 🐛 修复AS对齐计算漏洞：精确计算字段实际起始位置
  - 问题：旧算法使用 `缩进 + 2` 估算导致对齐错误
  - 解决：在 `parse_select_field()` 中精确识别字段起始位置
  - 效果：正确处理SELECT行和逗号前置行缩进不同的情况

- **v1.0** (2026-03-31)
  - 整合 AS 对齐和建表语句对齐功能
  - 支持选择性对齐（--as-only, --table-only）
  - 改进验证逻辑，检查组间相对位置
  - 统一输出格式和错误处理

## 相关文档

- `skill.md` - 完整的 SQL 格式规范文档
- `docs/KNOWN_ISSUES.md` - 已知问题和解决方案（如 PyCharm 中文对齐 Issue #1、cast/CASE Issue #2/#3、**多行 case + `)` 后逗号 Issue #4**）
- `docs/pycharm_font_fix.md` - PyCharm字体配置指南
- 格式规范参考：HiveQL 标准

## 故障排查

遇到对齐问题？查看 `docs/KNOWN_ISSUES.md`

## 许可

内部工具，仅供团队使用。
