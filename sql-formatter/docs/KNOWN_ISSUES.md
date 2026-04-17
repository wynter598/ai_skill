# SQL对齐工具已知问题和解决方案

## Issue #7: UNION 容器子查询内 `from`/`select`/逗号行缩进被降级到外层（v3.1.3 修复）

### 现象
1. 包含 `UNION ALL` 链的大子查询（如 CTE 内 `from (...union all...union all...)`），第二/三分支的 `from`、`select`、逗号字段行缩进被降到外层 indent（如 indent=6 应为 12；子查询内 `select` indent=12 应为 18）。
2. 嵌套层 `) as alias` 与对应 `(` 不在同一列。

### 根因
`_align_subquery_brackets_pass` 的重写循环中，`bracket_depth` 仅通过 `^\s*\(` / `^\s*\)` 行首模式追踪，忽略了行内表达式级括号（如 `nvl(lead(...), cast(...)) as end_time` 中的 `)` 出现在行首）。这导致：
1. 表达式级 `)` 被误判为子查询闭合，`bracket_depth` 提前降为 0 甚至负数。
2. 本应在 `bracket_depth > 0`（嵌套层保持不变）的行被错误地在 `bracket_depth == 0`（第一层关键字调整）中处理，使用了错误的 `relative_indent` 基准。
3. 嵌套层的 `from + (` 子查询中，`(` 和 `select` 的缩进基于递归层旧的 `base_indent`，未被外层重写循环纠正。

### 解决方案
1. **行内括号深度追踪**：在重写循环中，对非 `^\s*\(` / `^\s*\)` 的行处理完后，用 `_paren_delta_ignore_strings_sq` 计算行内括号变化量并更新 `bracket_depth` 和 `paren_col_stack`，确保嵌套深度追踪准确。
2. **嵌套层 `(` 跟随 `from` 对齐**：`bracket_depth > 0` 时，若 `(` 独占一行且前一行（`new_lines[-1]`）是已调整的独占 `from`/`join`，则 `(` 缩进与 `from` 同列，而非保留递归层旧值。
3. **嵌套层 `select` 从 `new_lines` 取 `(` 缩进**：`(` 后 `select` 的 `_opc` 从 `new_lines[-1]` 取（已调整值），而非 `processed_subquery[idx-1]`（旧值）。
4. **关键字 `_al_fix` 兜底 `_ci_kw`**：嵌套层 `from`/`union`/`select` 等关键字的缩进值（`_al_fix`）若 < `_ci_kw`（当前层基准），强制使用 `_ci_kw`，避免递归层旧值泄露。
5. **逗号字段行偏移纠正**：嵌套层中缩进 < `_ci_kw` 的逗号行，通过 `new_lines` 中最近 `select` 与 `processed_subquery` 中对应 `select` 的缩进差（`_shift`）来纠正。
6. **主扫描 `from`/`join` 纠正**（辅助）：`_from_join_only` 分支在递归层中从 `new_lines` 回溯找 `select` 缩进作为 `base_indent` 纠正参照。

### 影响范围
- 所有包含 `UNION ALL` 链的嵌套子查询
- 多层嵌套的 `from (select ... from (select ... ) as a) as b` 结构
- CTE 内的复杂子查询缩进

---

## Issue #6: `) alias where condition` 同行时别名未加 AS 且 WHERE 未换行 + 缩进级联错误（v3.1.2 修复）

### 现象
1. 子查询闭合括号、别名、WHERE 条件在同一行时（如 `) a where rn = 1`），别名未补 `as`，`where` 未拆行。
2. 包含 `) alias where/on condition` 模式的 `from (...)` 子查询，内部内容未正确缩进 +6，`left join` 等关键字被推到错误的缩进层级。

### 根因
1. `_try_split_join_on_one_line` 仅处理 `on` 关键字（Pattern 1/1.5/2），不处理 `where`。
2. `add_table_alias_as_keyword` 要求别名在行尾（`\)\s*(\w+)\s*$`），`) alias where ...` 不匹配。
3. `split_inline_join_on_lines`（步骤 5.8）在 `align_subquery_brackets`（步骤 3）**之后**执行，导致 `align_subquery_brackets` 处理时子查询闭合行仍含 `where/on` 条件，干扰了括号配对和内容缩进。缩进被后续 `align_union_branch_keyword_column` 覆盖，`_lead_join_on_after_close_alias` 基于扭曲的上下文将 `left join` 推到了外层缩进。

### 解决方案
1. 在 `_try_split_join_on_one_line` 新增 Pattern 1.6（`) as alias where cond`）和 Pattern 1.7（`) alias where cond`），拆为 `) as alias` + `where cond`。
2. 在 pipeline 中 `align_subquery_brackets` **之前**增加一次 `split_inline_join_on_lines` 预拆分调用（步骤 3.03），确保子查询闭合行干净后再做括号对齐。

### 影响范围
- 所有 `) alias where condition` 模式的子查询闭合行
- 包含此类模式的嵌套子查询的缩进级联

---

## Issue #5: `) alias on condition` 同行时别名未加 AS 且 ON 未换行（v3.1.1 修复）

### 现象
- 子查询闭合括号、别名、ON 条件在同一行时（如 `) pd on nvl(...)`），别名未补 `as`，`on` 未拆行。
- `left join table alias on condition` 拆行后，别名也未补 `as`（如 `left join jv_data_pre j`）。

### 根因
- `_try_split_join_on_one_line` Pattern 1 的正则 `\)\s+as\s+\S+` **要求 `as` 已存在**，所以 `) alias on ...` 不匹配。
- `add_table_alias_as_keyword` Pattern 2 的正则 `\)(\s*)(\w+)\s*$` **要求行尾就是别名**，所以 `) alias on ...` 也不匹配。
- Pipeline 顺序：`add_table_alias_as_keyword`（步骤 1.5）在 `split_inline_join_on_lines`（步骤 5.8）之前执行，两步互相踏空。

### 处理（v3.1.1）
- 在 `_try_split_join_on_one_line` 中新增 **Pattern 1.5**：匹配 `^\s*\)\s+(\w+)\s+on\s+(.+)$`（无 `as` 的 `) alias on cond`），拆分时同时补上 `as`，输出 `) as alias` + `on cond`。
- 对 Pattern 2（`join table alias on`）拆分后的 left 部分，检测缺失 `as` 并补充。
- 通过 SQL 关键字黑名单 `_CLOSE_PAREN_ALIAS_ON_SQL_KW` 避免将 `end`、`where` 等误判为别名。

---

## Issue #4: 多行 `sum(case … end ) as col` 之后行首逗号与上一字段不齐（v3.1+ 修复）

### 现象
- `select` 列表中上一字段为多行写法，例如：
  - `, sum(case when … then … when … then … else null end` 换行后单独一行 `) as col`
- 紧接着下一行 `, other_col`（以及后续行首逗号字段）与前面 `, sum(case…` **逗号列差 1 格或多格**，未与块内其它 `, field` 对齐。

### 根因
- `align_field_names` 用 `in_case_block` 区分「CASE 多行中间行」与「列表结束」。
- 曾在 **`end` 单独成行** 时就把 `in_case_block = False`；下一行是 **`) as alias`** 时：不以逗号开头、也不匹配 `when`/`else`/`end` 例外，被误判为 **SELECT 列表已结束** 而 **`break`** 出内层循环。
- 其后的行首逗号字段 **不再执行**「逗号列 = `field_start_pos - 2`」的统一缩进，保留 `convert_to_leading_comma` 等步骤留下的缩进，造成错位。

### 处理（v3.1+）
- **`end` 行不再清除 `in_case_block`**；在 **行首为 `)`** 的闭包行（如 `) as col`）写入输出后，再 **`in_case_block = False`**，使 `) as …` 与 `when`/`else`/`end` 一样仍处在「当前字段」上下文中。
- 在内层循环开头对 **`from` / `where` / `group by` / `having` / `order by` / `limit` / `union` / `join` 等** 做子句识别：一旦出现即 **`break`**，避免 `in_case_block` 仍为 `true` 时把 **`from`** 等误读进字段列表。

---

## Issue #3: 子查询内 `, case` 与 `, col` 行首逗号差 1 格（v3.1 修复）

### 现象
- 子查询里上一行是 `, col as alias`，下一行是 `, case when …`，**逗号列**多缩进 1 格；`group by` 中含 `cast(x as type)` 的行与其它维度行不齐。

### 根因
- `align_subquery_brackets` 曾用 `target_indent + (current_indent - min_indent)` 保留相对缩进，合并 CASE 后 `, case` 行历史上前导空格多 1，被固化下来。
- `align_field_names` 曾用「行内出现 `as` 即跳过」误判 `cast(... as type)`，未统一逗号列。

### 处理（v3.1）
- 子查询 depth-0 且行首为 `,` 的行：改为与同块 **select/group by 首行** 计算的 **逗号列**（`field_start_pos - 2`）一致。
- 行首逗号统一逻辑不再因 `cast(… as …)` 内 `as` 跳过整行。

---

## Issue #2: CASE/then 行误补 as、cast 内 as 被当作列别名（v3.1 修复）

### 现象
- 含 `case when ... then col` 的逗号前置行被补成 `then as col`，SQL 非法。
- `cast(x as double) as alias` 单行对齐时，取「最后一个 as」误命中类型转换的 `as double`，导致括号丢失。

### 处理（v3.1）
- `add_missing_as_keywords`：对含 `case` 或 `when...then` 的行跳过补 as。
- `parse_select_field`：从右向左选取 ` as ` 匹配，跳过位于未闭合 `cast(` 内的 `as`。

---

## Issue #1: PyCharm中文对齐偏移

### 现象
终端中AS垂直对齐，但PyCharm中包含中文字符的行AS不对齐（偏左约2个空格）。

### 根本原因
- **PyCharm字体对CJK字符宽度渲染为1.33倍**（不是标准的2倍）
- 终端和大多数编辑器：中文字符占2倍ASCII宽度
- PyCharm某些字体配置：中文字符占1.33倍ASCII宽度

### 诊断方法
```bash
# 在终端查看对齐
sed -n '199,201p' file.sql

# 如果终端对齐但PyCharm不对齐 → PyCharm字体问题
```

### 解决方案

#### 方案1：修改PyCharm字体（推荐）
1. `Preferences` → `Editor` → `Font`
2. 更换为支持CJK等宽的字体：
   - JetBrains Mono
   - Consolas
   - Source Code Pro
3. 确保勾选 "Anti-aliasing"

#### 方案2：使用自定义宽度比例对齐
```python
# 在sql_aligner.py中添加参数 --cjk-ratio
python3 sql_aligner.py file.sql --cjk-ratio 1.33
```

#### 方案3：手动微调（临时方案）
```python
# 使用专用修复脚本
python3 << 'EOF'
import re, unicodedata

CJK_WIDTH_RATIO = 1.33  # PyCharm实际比例

def get_pycharm_width(s):
    width = 0
    for char in s:
        if unicodedata.east_asian_width(char) in ('F', 'W'):
            width += CJK_WIDTH_RATIO
        else:
            width += 1
    return width

# 修复逻辑（见完整脚本）
EOF
```

### 预防措施

更新skill.md自动化决策表：
| 场景 | 默认行为 | 异常情况处理 |
|------|---------|-------------|
| 格式化含中文SQL | 使用默认模式（CJK宽度2倍） | 如果用户反馈"不对齐"，诊断PyCharm字体，提供1.33倍修复脚本 |

### 影响范围
- PyCharm 2020.x - 2024.x（部分字体配置）
- 受影响字段：包含中文字符串的字段表达式
- 不受影响：纯英文字段、数字、符号

### 相关Issue
- v2.0引入显示宽度对齐后出现
- v3.0添加PyCharm兼容模式修复

### 技术细节
- 终端使用`wcwidth`库计算，CJK字符严格2倍
- PyCharm依赖字体的`glyph metrics`，不同字体表现不同
- 解决方案需要运行时检测或用户指定比例
