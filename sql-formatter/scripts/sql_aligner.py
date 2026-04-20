#!/usr/bin/env python3
"""
SQL 代码对齐工具 v3.1.1
统一处理 SQL 代码中的各类对齐问题（含跨行圆括号 ``align_cross_line_parens``）：

【安全约束】除显式规则（如缺失 ``as`` 补全）外，**不得删除或改写 SQL 语义字符**（标识符、字面量、运算符、括号、逗号等）；
仅调整空白与换行；``merge_from_table`` 等合并行亦不删减非空白字符。

【SQL 格式规范（须完全遵守；由各处理函数分步收敛，未覆盖处须人工复核）】

请严格按照以下 SQL 格式规范进行检查、修正或生成代码，**必须完全遵守**，**不得自行改变风格**，不得修改业务逻辑。

**一、CASE WHEN 规则**

1. 同一层级内，``CASE`` 与其对应的 ``END`` 必须左对齐，即起始列相同。
2. 同一层级内，所有 ``WHEN`` 与 ``ELSE`` 必须垂直对齐，即起始列相同。
3. **嵌套 ``CASE`` 列锚（优先级高于 ``THEN`` 后首非空、AS 对齐、子查询体缩进）**：
   * **首行锚**：父块**物理首行**中与 ``case`` 同行的**第一个 ``when``** 关键字首字母 ``W`` 所在列（``when_col``，与 ``merge_case_when`` 中 ``case `` 后接 ``when`` 的列一致）。
   * **``THEN`` 独占行尾且下一行以 ``case when`` 起首**：子 ``case`` 的 ``C`` 与上述 **``when_col``** 同列（``align_case_when_columns`` 用栈顶 ``when_col``，**不**再追逐 ``THEN`` 后首非空）。
   * **``then case when`` 同行（紧凑写法）**：允许不拆行；**不要求**为对齐强行把 ``then`` 改成独占行尾。若已同行，子 ``case`` 列由该行内结构决定，后续换行子 ``case`` 仍优先 **``when_col``**（若栈已入）。
   * **其它** ``then``/``else`` 行尾形态：仍可用 ``_col_child_case_after_parent_then`` / ``_col_child_case_after_parent_else`` 作回退。
4. 所有嵌套 ``CASE`` 块都必须递归遵守以上规则（实现：``merge_case_when`` / ``align_case_when_columns`` 等）。

   **补充（实现要点）**

   * ``case`` 后非 ``when``：换行 ``when``/``else`` 与 ``case`` 后首非空同列；``end`` 与 ``case`` 同列（``align_case_when_columns`` 分支）。
   * 单行/多行判定：``_case_when_fully_closed_on_line``；多行块用 ``(case_col, when_col)`` 栈配对 ``end``，``else case when`` 未闭 ``end`` 时压栈。
   * ``THEN``/``ELSE`` 后子 ``CASE``：见上条 **3.**；``_col_child_case_after_parent_then`` / ``_col_child_case_after_parent_else`` 仅作**未命中** ``when_col`` 分支时的回退。
   * ``WHEN``/``ELSE`` 列由栈顶同层 ``when_col`` 决定；首行幂等：``_replace_leading_indent_first_line``。
   * ``group by grouping sets``：``align_grouping_sets_layout``。

**二、SELECT 字段列表规则**

6. ``SELECT`` 后的第一个字段必须与 ``SELECT`` 写在同一行（``merge_first_field_to_select``、``normalize_select_keyword_spacing``）。
7. 从第二个字段开始，使用「句首逗号」风格，即每行以逗号开头，逗号后必须保留 1 个空格（``convert_to_leading_comma``、``add_space_after_commas``）。
8. 所有后续字段行中，逗号后的第一个非空字符，必须与 ``SELECT`` 后第一个字段的非空格首字符垂直对齐（``align_field_names``）。

**三、子查询与查询块缩进规则**

9. 对于子查询，包裹子查询的左括号 ``(`` 和右括号 ``)`` 必须各自单独占一行。
10. 包裹子查询的括号所在列，必须与其对应的 ``from``、``join``、``left join``、``right join``、``inner join``、``cross join`` 等关键字垂直对齐（``align_subquery_brackets``、``align_join_after_subquery_close`` 等）。
11. 子查询内部的第一层查询体：当 **独占一行的** ``from`` / ``join`` / … **或** ``with … as`` / ``, … as`` **且** 下一行仅为 ``(`` 并与该关键字/定义行起始列相同时，行首基准列**唯一**为「该关键字或 CTE 定义行起始列 + ``SUBQUERY_INDENT``（6）」；第一层内保留**相对**缩进时以**首条** ``select``/``group by`` 行行首为参照，**不得**因 CASE 的 ``when``/``else``/``end`` 等拉低 ``min`` 而导致整块相对「+6」再整体偏移（``align_subquery_brackets``）。
12. 若子查询中继续嵌套子查询，则相同规则递归生效，即新一层子查询内部继续相对其外层括号缩进 6 个空格。

**三（续）、同一查询块内主子句关键字列（目标规范；与 §2.4 / CASE 协同）**

* **查询块**：同一嵌套层级、由同一套 ``select … from …``（及 ``where``/``group by``/``having``/``order by``/``limit``/``lateral view``/各类 ``join``/``union`` 等延续子句）构成的连续结构；外层与内层（子查询括号内）**各自**一套列锚。
* **主子句竖线**：同一块内 ``select``、``from``、``where``、``group by``、``having``、``order by``、``lateral view``、``join``/``left join``/…、``union``/``union all``、``limit`` 等**行首关键字**宜与同块 ``from``/``join`` 所在**主句列**一致（与 skill §2.4 一致；嵌套块内单独一套）。
* **括号块**：从左 ``(`` 的下一行到匹配 ``)`` 之前，相对该 ``(`` 所在列整体右移 ``SUBQUERY_INDENT``（6）；再嵌套则相对内层开括号再 +6；闭括号 ``)`` 与开括号 ``(`` 同列。
* **优先级**：与本文件 **一、CASE WHEN** 列锚冲突时，**CASE 列锚优先**，不得为迁就主子句列而平移子 ``case``/``when`` 锚点。
* **实现注**：原预处理中连续多次 ``align_subquery_brackets`` / ``UNION`` 后 ``align_field_names`` / ``align_where`` 后 ``align_case_when_columns`` 的因果，已分别收进 ``align_subquery_brackets``、``align_union_branch_keyword_column``、``align_where_and_clauses`` 的**单次对外调用**内部迭代至稳定（递归子块仍用单遍 ``_align_subquery_brackets_pass``，避免重复套叠）。

**四、通用要求**

13. 必须完整遵守全部对齐和缩进规则，不允许部分对齐、混合风格或随意缩进。
14. 仅允许调整格式、缩进和对齐，不允许修改字段名、表名、别名、条件、函数、表达式、返回值和任何业务逻辑。

**实现边界（不另编号，与 1–14 不冲突）**：忽略注释和字符串常量中的 SQL 关键字、仅处理真实语法结构时，**完整词法级过滤**为长期目标，当前行级启发式遇字面量内关键字时需人工复核；工具输出应为符合 1–14 的最终 SQL。

**规则总结：**

* 同层级 ``CASE`` 与 ``END`` 左对齐
* 同层级 ``WHEN`` 与 ``ELSE`` 垂直对齐
* 子级 ``CASE`` 列锚：优先与父块首行第一个 ``when``（``when_col``）同列；``THEN`` 独占行尾 + 下行 ``case when`` 时必用 ``when_col``；否则回退 ``THEN``/``ELSE`` 后首非空
* ``SELECT`` 后第一个字段与 ``SELECT`` 同行
* 后续字段采用句首逗号，逗号后空 1 格
* 后续字段逗号后的首字符与第一个字段首字母对齐
* 子查询括号单独占行
* 子查询内容相对括号缩进 6 个空格
* 函数参数折行：续行句首为逗号时，逗号对齐到函数名最后一个字符列；不以逗号或 ``)`` 开头时，对齐到 ``(`` 后第一个非空字符列
* 同一查询块内主子句关键字列、括号层级 +6 与 **三（续）** 一致；与 CASE 列锚冲突时 CASE 优先
* ``align_subquery_brackets`` / ``align_field_names`` / ``align_union_branch_keyword_column`` / ``align_where_and_clauses`` 对外单次调用内部迭代至稳定，替代原预处理中连续多轮同名调用
* 所有规则递归生效

**其他能力（不改变上述硬规范优先级）**：标准化运算符空格；修复 ``select as field``；缺失 ``AS`` 补全（跳过含 ``CASE``/``WHEN``/``THEN`` 行）；``WHERE``/``HAVING``/``AND``/``OR``/``ON`` 对齐；``split_inline_join_on_lines``；跨行圆括号 ``align_cross_line_parens``；``grouping sets`` / ``union`` 链布局；删除空行；SELECT 块 ``AS`` 对齐：选列区（不含整行 ``--``）按**句首逗号列（1-based）垂直续行**逐行量字符长（有列别名 ``as`` 时右端为 ``as`` 前最后非空），极差 ≤ ``SELECT_AS_UNIFY_HEAD_CHAR_SPAN_MAX``（默认 50）时整块单列 ``as``，否则短/中/长分级（**分档长度 ``tier_len`` 与闸门同源 ref→``as`` 前显示宽**，避免跨行续行片段误归短档）；右端目标列用 ``gate_abs_end``；``CREATE TABLE`` 列定义对齐。

使用方法：
  python sql_aligner.py <input_file> [选项]

选项：
  --verify-only         仅验证不修改
  --as-only             仅处理 AS 对齐
  --table-only          仅处理建表语句对齐
  --char-mode           使用字符位置对齐（兼容模式）
  --cjk-width <ratio>   设置CJK字符宽度比例（默认2.0，PyCharm部分字体用1.5）
"""

import math
import re
import sys
import unicodedata
from typing import List, Tuple, Dict, Set, Optional
from collections import defaultdict

USE_CHAR_MODE = True
CJK_WIDTH_RATIO = 2.0

SHORT_FIELD_MAX = 50
MEDIUM_FIELD_MAX = 100
AS_SPACING = 1
# 选列区（整行 ``--`` 除外）按句首逗号列 1-based 垂直续行逐行量字符长（含 ``as`` 行以列别名 ``as`` 前最后非空为右端）；极差 ≤ 此值时整块 ``as`` 单列对齐，否则仍走短/中/长分级。
SELECT_AS_UNIFY_HEAD_CHAR_SPAN_MAX = 50
SUBQUERY_INDENT = 6
# 对外 ``align_subquery_brackets`` 内部迭代至稳定之上限（合并原流水线中连续多轮同类调用）。
_ALIGN_SUBQUERY_BRACKETS_MAX_STABLE = 10
# ``align_field_names`` 内部迭代至稳定之上限（含 UNION 链后逗号列重算等）。
_ALIGN_FIELD_NAMES_MAX_STABLE = 10
# ``with … as`` / ``, … as`` 独占行且下一行仅 ``(`` 并与定义行同列：第一层体锚定为**定义行首列 + SUBQUERY_INDENT**（与 ``from/join`` + 独占 ``(`` 一致）。
_CTE_AS_OPEN_HEAD_RE = re.compile(
    r"^(\s*)(?:(?:,\s*.+)|(?:\bwith\s+.+))\s+as\s*$",
    re.IGNORECASE,
)
# 独立 ``on`` 行条件体至少多长才按顶层 `` and `` 折行（避免短句误拆）
LONG_ON_PREDICATE_MIN_LEN = 48


def get_width(s: str) -> float:
    """计算字符串显示宽度"""
    if USE_CHAR_MODE:
        return len(s)

    width = 0.0
    for char in s:
        if unicodedata.east_asian_width(char) in ('F', 'W'):
            width += CJK_WIDTH_RATIO
        else:
            width += 1
    return width


def _try_insert_as_keyword(line: str, prefix: str, sql_keywords: set) -> Optional[str]:
    """尝试在字段行中补充缺失的 AS 关键字，返回新行或 None（无需修改）。"""
    if re.search(r'(?i)\bcase\b', line) or re.search(r'(?i)\bwhen\b.+\bthen\b', line):
        return None

    code_part = line
    comment_part = ''
    cm = re.search(r'\s+--|(?<=\w)--', line)
    if cm:
        code_part = line[:cm.start()]
        comment_part = line[cm.start():]
    if comment_part.endswith('\n'):
        comment_part = comment_part[:-1]
    code_stripped = code_part.rstrip()

    if re.search(r'\s+as\s+\w+\s*$', code_stripped, re.IGNORECASE):
        return None

    match = re.match(r'^(' + re.escape(prefix) + r')(.*?)(\s+)(\w+)$', code_stripped)
    if not match:
        return None
    field_expr = match.group(2)
    spaces = match.group(3)
    alias = match.group(4)
    if not field_expr.strip():
        return None
    if alias.lower() in sql_keywords or alias.isdigit():
        return None
    if field_expr.strip() == alias:
        return None

    has_newline = line.endswith('\n')
    new_line = f"{match.group(1)}{field_expr}{spaces}as {alias}{comment_part}"
    if has_newline:
        new_line += '\n'
    return new_line


def add_missing_as_keywords(lines: List[str]) -> List[str]:
    """自动补充SELECT字段中缺失的AS关键字"""
    new_lines = []
    sql_keywords = {'from', 'where', 'group', 'having', 'order', 'limit', 'union', 'join', 'on', 'and', 'or'}
    in_select_block = False

    for line in lines:
        stripped = line.strip().lower()

        if not stripped or stripped.startswith('--') or stripped.startswith('/*'):
            new_lines.append(line)
            continue

        # 检测SELECT块的开始——同时对 select 首行做 AS 补充
        select_match = re.match(r'^(\s*select\s+)', line, re.IGNORECASE)
        if select_match:
            in_select_block = True
            result = _try_insert_as_keyword(line, select_match.group(1), sql_keywords)
            new_lines.append(result if result else line)
            continue

        # 检测SELECT块的结束（遇到FROM, WHERE等关键字）
        if any(re.match(r'^\s*' + keyword + r'\s', line, re.IGNORECASE) for keyword in sql_keywords):
            in_select_block = False
            new_lines.append(line)
            continue

        # 检测是否是SELECT字段行
        is_comma_field = stripped.startswith(',')

        # 只处理SELECT块内的逗号开头字段
        if is_comma_field and in_select_block:
            comma_prefix_match = re.match(r'^(\s*,\s*)', line)
            prefix = comma_prefix_match.group(1) if comma_prefix_match else ''
            result = _try_insert_as_keyword(line, prefix, sql_keywords)
            new_lines.append(result if result else line)
        else:
            new_lines.append(line)

    return new_lines


def add_space_after_commas(lines: List[str]) -> List[str]:
    """在逗号后添加空格（如果没有的话）"""
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('--') or stripped.startswith('/*'):
            new_lines.append(line)
            continue

        # 匹配逗号后没有空格的情况，但不包括函数调用、字符串内的逗号
        result = re.sub(r',(?! )(?=[^\'"]*(?:["\'][^"\'"]*["\'][^\'"]*)*$)', ', ', line)
        new_lines.append(result)

    return new_lines


def _nearest_select_indent_before(lines: List[str], idx: int) -> Optional[int]:
    """自 ``idx-1`` 行起向上扫：圆括号深度 0 时遇到 ``select`` 行，返回该行关键字前缩进（与同层 select 左对齐用）。"""
    depth = 0
    for j in range(idx - 1, -1, -1):
        raw = lines[j].split("\n", 1)[0]
        st = raw.strip()
        if depth == 0 and re.match(r"^select\b", st, re.IGNORECASE):
            return len(raw) - len(raw.lstrip())
        for ch in reversed(raw):
            if ch == ")":
                depth += 1
            elif ch == "(":
                if depth > 0:
                    depth -= 1
        if depth < 0:
            depth = 0
    return None


def align_where_and_clauses(lines: List[str]) -> List[str]:
    """对齐 WHERE/HAVING/JOIN 及其 ON/AND/OR 子句；返回前对全文再跑一次 ``align_case_when_columns`` 以修复本步对 CASE 内续行的影响。

    规则：
    1. ON 与同层 from / left join 等首列对齐（由 JOIN 行缩进代表）
    2. WHERE、HAVING 各自为首列；同一块内 AND/OR 与**同层 select** 行首同列（若无法则退回 where/having 列）
    3. JOIN 条件下 ON 与后续 AND/OR 与 JOIN 首列对齐
    """
    new_lines = []
    base_indent = None  # 记录最近的 WHERE、HAVING 或 JOIN 的缩进
    base_keyword = None  # 记录是 WHERE、HAVING 还是 JOIN
    select_clause_indent: Optional[int] = None  # WHERE/HAVING 对应 select 行首缩进

    for idx, line in enumerate(lines):
        stripped = line.strip()

        # 检测 WHERE 关键字
        where_match = re.match(r'^(\s*)where\s+', line, re.IGNORECASE)
        if where_match:
            base_indent = len(where_match.group(1))
            base_keyword = 'WHERE'
            select_clause_indent = _nearest_select_indent_before(lines, idx)
            new_lines.append(line)
            continue

        # 检测 HAVING 关键字（与 WHERE 独立成块；后续 AND/OR 对齐到 having 列）
        having_match = re.match(r'^(\s*)having\s+', line, re.IGNORECASE)
        if having_match:
            base_indent = len(having_match.group(1))
            base_keyword = 'HAVING'
            select_clause_indent = _nearest_select_indent_before(lines, idx)
            new_lines.append(line)
            continue

        # 检测 JOIN 关键字（含 outer/full/cross 等变体）
        join_match = _JOIN_LINE_START_RE.match(line)
        if join_match:
            cur_indent = len(join_match.group(1))
            use_indent = cur_indent
            # ``align_subquery_brackets`` 可能把 ``) as b`` 之后的 ``on`` 已拉回同层，但下一行仅 ``left join`` 仍多一档缩进；与上一行 ``on`` 对齐
            rest_after_kw = line[join_match.end() :].strip()
            if not rest_after_kw and new_lines:
                pm_prev = re.match(r"^(\s*)on\s+", new_lines[-1], re.IGNORECASE)
                if pm_prev:
                    on_ind = len(pm_prev.group(1))
                    if cur_indent > on_ind:
                        use_indent = on_ind
            # ``and …`` 链后下一行 ``left join`` 偶发多 1 格：与向上最近同层 JOIN 行首对齐（仅修正 peer→cur 差 1 且 cur≤2 的顶格附近）
            if new_lines and rest_after_kw:
                peer_j = _find_nearest_join_indent(new_lines, len(new_lines) - 1)
                if peer_j >= 0 and cur_indent == peer_j + 1 and cur_indent <= 2:
                    use_indent = peer_j
            base_indent = use_indent
            base_keyword = 'JOIN'
            select_clause_indent = None
            if use_indent != cur_indent:
                has_nl = line.endswith("\n")
                new_line = " " * use_indent + line.lstrip()
                if has_nl and not new_line.endswith("\n"):
                    new_line += "\n"
                new_lines.append(new_line)
            else:
                new_lines.append(line)
            continue

        # 检测 ON：上一行为 ``) as alias`` 时，中间可能夹内层 ``where``，base_keyword 已非 JOIN，仍须按子查询外层的 join 列对齐
        on_match = re.match(r'^(\s*)on\s+(.*)$', line, re.IGNORECASE)
        if on_match:
            rest = on_match.group(2)
            prev_line = new_lines[-1] if new_lines else ''
            prev_body = prev_line.rstrip('\n').rstrip()
            m_close_prev = re.match(r"(?i)^(\s*\)\s+as\s+\S+)$", prev_body)
            if m_close_prev:
                ji = _join_indent_for_close_alias_on(lines, idx, m_close_prev.group(1))
                if ji < 0:
                    ji = len(m_close_prev.group(1)) - len(m_close_prev.group(1).lstrip())
                has_newline = line.endswith("\n")
                new_line = " " * ji + "on " + rest.strip()
                if has_newline and not new_line.endswith("\n"):
                    new_line += "\n"
                new_lines.append(new_line)
                base_indent = ji
                base_keyword = "JOIN"
                select_clause_indent = None
                continue

            if base_keyword == 'JOIN':
                current_indent = len(on_match.group(1))
                # 如果缩进不匹配 JOIN，调整之
                if current_indent != base_indent:
                    has_newline = line.endswith("\n")
                    new_line = " " * base_indent + "on " + rest.strip()
                    if has_newline and not new_line.endswith("\n"):
                        new_line += "\n"
                    new_lines.append(new_line)
                else:
                    new_lines.append(line)
                continue

        # 检测 AND/OR 关键字（JOIN/ON 块：与 JOIN/ON 同列；WHERE/HAVING：与同层 select 同列）
        and_or_match = re.match(r'^(\s*)(and|or)\s+(.*)$', line, re.IGNORECASE)
        if and_or_match and base_indent is not None:
            current_indent = len(and_or_match.group(1))
            keyword = and_or_match.group(2)
            rest = and_or_match.group(3)

            if base_keyword in ("WHERE", "HAVING") and select_clause_indent is not None:
                use_indent = select_clause_indent
            else:
                use_indent = base_indent

            # 如果缩进不匹配基准，调整之
            if current_indent != use_indent:
                has_newline = line.endswith("\n")
                new_line = " " * use_indent + keyword + " " + rest
                if has_newline and not new_line.endswith("\n"):
                    new_line += "\n"
                new_lines.append(new_line)
            else:
                new_lines.append(line)
            continue

        # 遇到其他 SQL 子句起始，重置 base_indent（having 单独在上面处理，不在此重置）
        # 注意：不得用子查询内的 ``select`` 重置，否则 ``) as alias`` 下一行的 ``on`` 会丢失 JOIN 基准或被误对齐
        if re.match(r'^\s*(from|group\s+by|order\s+by|limit|union)\b', line, re.IGNORECASE):
            base_indent = None
            base_keyword = None
            select_clause_indent = None

        new_lines.append(line)

    # ``align_where_and_clauses`` 可能把 SELECT 内多行 ``when`` 续行的 ``and``/``or`` 误按 WHERE 缩进；
    # 因果收进本函数末尾一次 ``align_case_when_columns``（替代预处理中紧随其后的第二轮 CASE 对齐）。
    return align_case_when_columns(new_lines)


def remove_empty_lines(lines: List[str]) -> List[str]:
    """删除空行（完全空白的行）"""
    return [line for line in lines if line.strip() != '']


_CLOSE_PAREN_AS_ALIAS_LINE_RE = re.compile(
    r'^(\s*\))\s+as\s+(\S+)(\s*(?:--.*)?)$',
    re.IGNORECASE,
)


def compact_close_paren_as_alias_lines(lines: List[str]) -> List[str]:
    """子查询闭合行 ``… )      as alias``：``)`` 与 ``as`` 之间仅保留一个空格，别名紧跟 ``as`` 后一个空格。

    与 SELECT 选列 ``expr      as col`` 的列对齐垫空不同；此类行不应在 ``)`` 与 ``as`` 之间插入对齐空格。
    """
    out: List[str] = []
    for line in lines:
        raw = line.rstrip('\n')
        m = _CLOSE_PAREN_AS_ALIAS_LINE_RE.match(raw)
        if m:
            tail = m.group(3) or ''
            new_raw = (f"{m.group(1)} as {m.group(2)}{tail}").rstrip()
            has_nl = line.endswith('\n')
            out.append(new_raw + ('\n' if has_nl else ''))
        else:
            out.append(line)
    return out


_NON_FUNC_KEYWORDS = frozenset({
    'in', 'not', 'exists', 'any', 'all', 'some',
    'and', 'or', 'on', 'when', 'then', 'else',
    'where', 'from', 'select', 'as', 'by', 'between',
    'like', 'is', 'case', 'end', 'into', 'set',
    'having', 'order', 'group', 'limit', 'union',
    'values', 'insert', 'update', 'delete', 'create',
    'alter', 'drop', 'table', 'join', 'left', 'right',
    'inner', 'outer', 'cross', 'full', 'with', 'over',
})


def align_function_arg_continuations(lines: List[str]) -> List[str]:
    """函数参数折行对齐。

    当函数调用的参数跨多行时，续行按如下规则对齐：

    * 续行句首为逗号 ``,``：逗号对齐到**函数名最后一个字符**所在列。
    * 续行句首不是逗号也不是 ``)``：对齐到函数名后第一个 ``(`` 之后的**第一个非空字符**所在列。
    * 续行句首为 ``)``：不处理，交给 ``align_cross_line_parens`` 现有逻辑。

    仅作用于「函数调用」括号（``identifier(``），不作用于子查询 / ``IN`` / ``EXISTS`` 等非函数括号。
    """
    if not lines:
        return lines

    _CASE_WHEN_KW_RE = re.compile(r'^(case|and|or|then|when|else|end)\b', re.I)

    out: List[str] = []
    bracket_stack: List[dict] = []
    case_depth = 0

    for line in lines:
        has_nl = line.endswith('\n')
        raw = line.rstrip('\n')
        stripped = raw.strip()

        realigned = raw
        if bracket_stack and stripped and not stripped.startswith('--') and not stripped.startswith(')'):
            top = bracket_stack[-1]
            if top['type'] == 'func':
                # CASE WHEN 内部的 and/or/then/when/else/end 不作为函数参数续行重对齐
                _skip_for_case = case_depth > 0 and bool(_CASE_WHEN_KW_RE.match(stripped))
                if not _skip_for_case:
                    if stripped.startswith(','):
                        target_col = top['func_last_col']
                    else:
                        target_col = top['first_arg_col']
                    cur_indent = len(raw) - len(raw.lstrip())
                    if cur_indent != target_col:
                        realigned = ' ' * target_col + stripped

        out.append(realigned + ('\n' if has_nl else ''))

        parse = realigned
        in_sq = False
        i = 0
        while i < len(parse):
            ch = parse[i]
            if ch == "'" and not in_sq:
                in_sq = True
                i += 1
                continue
            if ch == "'" and in_sq:
                if i + 1 < len(parse) and parse[i + 1] == "'":
                    i += 2
                    continue
                in_sq = False
                i += 1
                continue
            if in_sq:
                i += 1
                continue
            if ch == '-' and i + 1 < len(parse) and parse[i + 1] == '-':
                break

            if ch == '(':
                is_func = False
                if i > 0 and (parse[i - 1].isalnum() or parse[i - 1] == '_'):
                    j = i - 1
                    while j > 0 and (parse[j - 1].isalnum() or parse[j - 1] == '_'):
                        j -= 1
                    func_name = parse[j:i].lower()
                    if func_name not in _NON_FUNC_KEYWORDS:
                        is_func = True

                if is_func:
                    func_last_col = i - 1
                    fa = i + 1
                    while fa < len(parse) and parse[fa] == ' ':
                        fa += 1
                    if fa >= len(parse) or parse[fa] in (')', '-'):
                        first_arg_col = i + 1
                    else:
                        first_arg_col = fa
                    bracket_stack.append({
                        'type': 'func',
                        'func_last_col': func_last_col,
                        'first_arg_col': first_arg_col,
                    })
                else:
                    bracket_stack.append({
                        'type': 'other',
                        'func_last_col': 0,
                        'first_arg_col': 0,
                    })

            elif ch == ')':
                if bracket_stack:
                    bracket_stack.pop()

            i += 1

        # 维护 CASE WHEN 深度
        _lower = realigned.lower()
        case_depth += len(re.findall(r'\bcase\s+when\b', _lower))
        case_depth -= len(re.findall(r'\bend\b', _lower))
        if case_depth < 0:
            case_depth = 0

    return out


def _first_meaningful_char_col(line: str) -> int:
    """整行 ``--`` 注释对齐用参考列（0-based）。

    行首空白后：若恰好为 ``, `` + 单空格 + 非空白``，则返回该非空白字符列；否则返回行首第一个非空白字符列。
    """
    s = line.split("\n", 1)[0]
    i = 0
    n = len(s)
    while i < n and s[i] in " \t":
        i += 1
    if i + 2 < n and s[i] == "," and s[i + 1] == " " and s[i + 2] not in " \t":
        return i + 2
    return i


def align_comments(lines: List[str]) -> List[str]:
    """对齐单独占一行的 ``--`` 注释。

    规则：自当前行向下跳过空行与整行 ``--``（``strip().startswith('--')``）后取首条参考行；
    若参考行仅为 ``(`` / ``)`` 则不改写；否则 ``--`` 起始列与 ``_first_meaningful_char_col`` 一致
    （优先 ``, `` + 单空格后的首字符列，否则为参考行首非空白字符列）。可与 ``from`` 的 ``f`` 同列。
    """
    new_lines: List[str] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("--"):
            new_lines.append(line)
            continue

        j = _next_meaningful_line_index(lines, i + 1)
        if j is None:
            new_lines.append(line)
            continue

        ref_line = lines[j]
        ref_stripped = ref_line.strip()
        if ref_stripped in ("(", ")"):
            new_lines.append(line)
            continue

        target_col = _first_meaningful_char_col(ref_line)

        has_newline = line.endswith("\n")
        new_comment_line = " " * target_col + stripped
        if has_newline and not new_comment_line.endswith("\n"):
            new_comment_line += "\n"
        elif not has_newline and new_comment_line.endswith("\n"):
            new_comment_line = new_comment_line.rstrip("\n")
        new_lines.append(new_comment_line)

    return new_lines


def align_join_after_subquery_close(lines: List[str]) -> List[str]:
    """上一行仅为 ``) as alias`` 且本行仅为 join 时：与同层 ``from``/``join``（开括号上一行）同列；无法解析时退回与 ``)`` 同列。

    ``on`` 行在 ``align_subquery_brackets`` 内单独处理（常带条件，不能按「仅 join」行匹配）。
    """
    if not lines:
        return lines
    out: List[str] = []
    for i, line in enumerate(lines):
        if out:
            prev = out[-1].rstrip("\n")
            pm = re.match(r"^(\s*)\)\s+as\s+\S+\s*$", prev)
            body = line.rstrip("\n")
            jm = re.match(
                r"^(\s*)((?:(?:left|right|inner|full)(?:\s+outer)?|cross)\s+join|join)\s*$",
                body,
                re.IGNORECASE,
            )
            if pm and jm:
                has_nl = line.endswith("\n")
                full = out + [line]
                idx = len(out)
                _peer = _lead_join_on_after_close_alias(full, idx)
                ind_alias = len(pm.group(1))
                ind_use = _peer if _peer is not None else ind_alias
                kw = jm.group(2)
                new_line = " " * ind_use + kw + ("\n" if has_nl else "")
                out.append(new_line)
                continue
        out.append(line)
    return out


def add_table_alias_as_keyword(lines: List[str]) -> List[str]:
    """为表别名补充 AS 关键字

    规则：
    1. FROM 后的表名和别名之间加 AS
    2. JOIN 后的表名和别名之间加 AS
    3. 子查询闭合括号后的别名前加 AS

    示例：
        from table1 t1  →  from table1 as t1
        ) alias  →  ) as alias
    """
    new_lines = []

    for line in lines:
        stripped = line.strip()

        # 情况1: FROM/JOIN 后面的表名和别名
        # 匹配: from table_name alias 或 join table_name alias（不带AS）
        from_join_match = re.match(
            r'^(\s*)(from|left\s+join|right\s+join|inner\s+join|cross\s+join|full\s+outer\s+join|full\s+join|join)\s+(\S+)\s+(\w+)\s*$',
            line,
            re.IGNORECASE
        )
        _table_alias_sql_kw = {'select', 'case', 'when', 'then', 'else', 'end',
                               'where', 'and', 'or', 'on', 'set', 'into', 'values',
                               'group', 'order', 'having', 'limit', 'union', 'lateral'}
        if from_join_match:
            indent = from_join_match.group(1)
            keyword = from_join_match.group(2)
            table_name = from_join_match.group(3)
            alias = from_join_match.group(4)

            if table_name.startswith('(') or alias.lower() in _table_alias_sql_kw:
                new_lines.append(line)
                continue

            # 检查是否已经有 AS
            if not re.search(r'\bas\b', line, re.IGNORECASE):
                has_newline = line.endswith('\n')
                new_line = f"{indent}{keyword} {table_name} as {alias}"
                if has_newline:
                    new_line += '\n'
                new_lines.append(new_line)
                continue

        # 情况2: 子查询闭合括号后的别名
        # 匹配: ) alias 或 )alias（不带AS）
        bracket_alias_match = re.match(r'^(\s*)\)(\s*)(\w+)\s*$', line)
        if bracket_alias_match:
            indent = bracket_alias_match.group(1)
            spaces = bracket_alias_match.group(2)
            alias = bracket_alias_match.group(3)

            # 检查是否已经有 AS
            if not re.search(r'\bas\b', line, re.IGNORECASE):
                has_newline = line.endswith('\n')
                # 括号后至少一个空格，然后是 as 别名
                new_line = f"{indent}) as {alias}"
                if has_newline:
                    new_line += '\n'
                new_lines.append(new_line)
                continue

        new_lines.append(line)

    return new_lines


def verify_sql_keywords(original_lines: List[str], formatted_lines: List[str]) -> bool:
    """验证格式化后SQL关键字数量不变（防止丢失SELECT/FROM等关键字）

    Returns:
        True if all keywords count match, False otherwise

    历史教训：2026-04-08 align_subquery_brackets 曾丢失 SELECT 关键字
    """
    keywords = ['select', 'from', 'where', 'join', 'left join', 'right join',
                'inner join', 'group by', 'order by', 'having', 'union']

    for keyword in keywords:
        pattern = re.compile(r'\b' + keyword.replace(' ', r'\s+') + r'\b', re.IGNORECASE)
        original_count = sum(1 for line in original_lines if pattern.search(line))
        formatted_count = sum(1 for line in formatted_lines if pattern.search(line))

        if original_count != formatted_count:
            print(f"⚠️  警告：关键字 '{keyword}' 数量不匹配！原始={original_count}, 格式化后={formatted_count}")
            return False

    return True


def verify_comments_content(original_lines: List[str], formatted_lines: List[str]) -> bool:
    """验证格式化后注释文本内容不变（仅允许调整注释行首缩进）

    Returns:
        True if all comment contents match, False otherwise

    硬约束：注释内容（去除行首空白后）必须逐字符一致
    """
    # 提取原始文件中的所有注释内容（去除行首空白）
    original_comments = []
    for line in original_lines:
        stripped = line.strip()
        if stripped.startswith('--'):
            original_comments.append(stripped)
        elif '/*' in stripped or '*/' in stripped:
            # 块注释也需要检查（简化处理：只检查包含 /* 或 */ 的行）
            original_comments.append(stripped)

    # 提取格式化后文件中的所有注释内容（去除行首空白）
    formatted_comments = []
    for line in formatted_lines:
        stripped = line.strip()
        if stripped.startswith('--'):
            formatted_comments.append(stripped)
        elif '/*' in stripped or '*/' in stripped:
            formatted_comments.append(stripped)

    # 比对注释数量
    if len(original_comments) != len(formatted_comments):
        print(f"⚠️  警告：注释数量不匹配！原始={len(original_comments)}, 格式化后={len(formatted_comments)}")
        return False

    # 逐行比对注释内容
    for i, (orig, fmt) in enumerate(zip(original_comments, formatted_comments)):
        if orig != fmt:
            print(f"⚠️  警告：第 {i+1} 个注释内容被修改！")
            print(f"    原始: {orig[:80]}")
            print(f"    格式化后: {fmt[:80]}")
            return False

    return True


def merge_first_field_to_select(lines: List[str]) -> List[str]:
    """将 SELECT 后第一个字段合并到同一行，后续字段首字母与第一个字段首字母对齐

    规范：SELECT 后首个字段直接紧跟书写（同一行）

    示例转换：
        select
            field1
            , field2

        转换为：
        select field1
             , field2
    """
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 检测 GROUP BY / ORDER BY 关键字（单独一行，后面无字段）
        gb_match = re.match(r'^(\s*)(group\s+by|order\s+by)\s*$', line, re.IGNORECASE)
        if gb_match:
            kw_indent = len(gb_match.group(1))
            kw_line = line.rstrip('\n')
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                next_stripped = next_line.strip()
                if next_stripped and not next_stripped.startswith('--'):
                    has_newline = next_line.endswith('\n')
                    merged_line = kw_line + ' ' + next_stripped
                    if has_newline:
                        merged_line += '\n'
                    new_lines.append(merged_line)
                    i += 2
                    continue
            new_lines.append(line)
            i += 1
            continue

        # 检测 SELECT 关键字（单独一行）
        if re.match(r'^\s*select\s*$', line, re.IGNORECASE):
            select_indent = len(line) - len(line.lstrip())
            select_line = line.rstrip('\n')

            # 检查下一行是否是第一个字段
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                next_stripped = next_line.strip()

                # 第一个字段不应以逗号开头
                if next_stripped and not next_stripped.startswith(',') and not next_stripped.startswith('--'):
                    # 合并到 SELECT 行
                    has_newline = next_line.endswith('\n')
                    merged_line = select_line + ' ' + next_stripped
                    if has_newline:
                        merged_line += '\n'
                    new_lines.append(merged_line)

                    # 计算第一个字段首字母的位置（用于后续字段对齐）
                    first_field_start = len(select_line) + 1  # select + 空格

                    # 跳过已合并的字段行
                    i += 2

                    # 处理后续字段，确保首字母与第一个字段首字母对齐
                    while i < len(lines):
                        field_line = lines[i]
                        field_stripped = field_line.strip()

                        # 遇到下一个SQL子句（FROM/WHERE等），停止
                        if re.match(r'^\s*(from|where|group\s+by|having|order\s+by|limit|union|left\s+join|right\s+join|inner\s+join|cross\s+join|full\s+outer\s+join|full\s+join|join)\b', field_line, re.IGNORECASE):
                            break

                        # 空行或注释行保持原样
                        if not field_stripped or field_stripped.startswith('--'):
                            new_lines.append(field_line)
                            i += 1
                            continue

                        # 字段行（以逗号开头）
                        if field_stripped.startswith(','):
                            # 调整缩进：逗号前有 (first_field_start - 2) 个空格，字段首字母在 first_field_start 位置
                            has_newline = field_line.endswith('\n')
                            new_field_line = ' ' * (first_field_start - 2) + field_stripped
                            if has_newline:
                                new_field_line += '\n'
                            new_lines.append(new_field_line)
                        else:
                            # 非逗号开头的行（可能是多行表达式的一部分），保持原样
                            new_lines.append(field_line)

                        i += 1
                    continue
                else:
                    # 下一行是逗号开头或注释，保持原样
                    new_lines.append(line)
                    i += 1
            else:
                new_lines.append(line)
                i += 1
        else:
            new_lines.append(line)
            i += 1

    return new_lines


def _leading_indent_nearest_preceding_select(
    processed_subquery: List[str], idx: int
) -> Optional[int]:
    """自 ``idx-1`` 向上找最近一行以 ``select`` 开头的行首缩进；跳过空行、``--``、以及中间的 ``union`` 行（多段 union 链）。"""
    j = idx - 1
    while j >= 0:
        raw = processed_subquery[j]
        st = raw.strip()
        if not st:
            j -= 1
            continue
        if st.startswith("--"):
            j -= 1
            continue
        if re.match(r"^union\b", st, re.IGNORECASE):
            j -= 1
            continue
        if re.match(r"^select\b", st, re.IGNORECASE):
            return len(raw) - len(raw.lstrip())
        j -= 1
    return None


def _leading_indent_enclosing_select_before(
    processed_subquery: List[str], idx: int
) -> Optional[int]:
    """自 ``idx`` 行起向上，用反向括号平衡找到「与当前 ``where``/``group by`` 同语句块」的 ``select`` 行首缩进。

    自 ``idx-1`` 起向下标递减：在每行行首若 ``depth==0`` 且该行以 ``select`` 开头则命中；再自右向左扫该行字符，
    遇 ``)`` 则 ``depth+=1``、遇 ``(`` 则 ``depth-=1``（与从当前行向上走出子括号的语义一致）。
    不解析字符串/注释内括号，与现有子查询启发式一致。
    """
    depth = 0
    j = idx - 1
    while j >= 0:
        raw = processed_subquery[j].split("\n", 1)[0]
        st = raw.strip()
        if depth == 0 and re.match(r"^select\b", st, re.IGNORECASE):
            return len(raw) - len(raw.lstrip())
        for k in range(len(raw) - 1, -1, -1):
            ch = raw[k]
            if ch == ")":
                depth += 1
            elif ch == "(":
                depth -= 1
        j -= 1
    return None


def _leading_indent_first_select_before_index(
    processed_subquery: List[str], end_idx: int
) -> Optional[int]:
    """自片段第 0 行起前向扫到 ``end_idx``（不含），左→右累计 ``()`` 深度；在行首 ``depth==0`` 时取第一条 ``select`` 行首缩进。

    用于 ``union``/``union all`` 与同一条 ``( select … union all select … )`` 链上**首节** ``select`` 对齐，
    避免 ``_leading_indent_nearest_preceding_select`` 向上命中 ``join (`` 内层 ``select`` 而多缩进一档。
    """
    depth = 0
    for j in range(0, max(0, end_idx)):
        raw = processed_subquery[j].split("\n", 1)[0]
        st = raw.strip()
        if depth == 0 and re.match(r"^select\b", st, re.IGNORECASE):
            return len(raw) - len(raw.lstrip())
        for ch in raw:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
        if depth < 0:
            depth = 0
    return None


def _leading_indent_union_above_select_through_comments(
    processed_subquery: List[str], idx: int
) -> Optional[int]:
    """自 ``idx-1`` 向上跳过空行与 ``--`` 后，若首条非注释语句为 ``union``，返回该行首缩进（用于 union 链各段 ``select`` 与 ``union`` 左对齐）。"""
    j = idx - 1
    while j >= 0:
        raw = processed_subquery[j]
        st = raw.strip()
        if not st:
            j -= 1
            continue
        if st.startswith("--"):
            j -= 1
            continue
        if re.match(r"^union\b", st, re.IGNORECASE):
            return len(raw) - len(raw.lstrip())
        return None
    return None


def _next_meaningful_line_index(lines: List[str], start: int) -> Optional[int]:
    """自 ``start`` 起向下找首条非空且非整行 ``--`` 注释的行索引。"""
    n = len(lines)
    for j in range(start, n):
        st = lines[j].strip()
        if not st:
            continue
        if st.startswith("--"):
            continue
        return j
    return None


_JOIN_ONLY_LINE_RE = re.compile(
    r"^((?:(?:left|right|inner|full)(?:\s+outer)?|cross)\s+)?join\s*$",
    re.IGNORECASE,
)


def _matching_open_paren_line_index(lines: List[str], close_idx: int) -> Optional[int]:
    """自 ``lines[close_idx]`` 起向上做字符级 ``)``/``(`` 配对，返回与当前块最外闭合配对的、含 ``(`` 的行下标。

    不解析字符串字面量，与 ``_leading_indent_nearest_preceding_from_for_where`` 等启发式一致。
    """
    depth = 0
    for j in range(close_idx, -1, -1):
        raw = lines[j].split("\n", 1)[0]
        for ch in reversed(raw):
            if ch == ")":
                depth += 1
            elif ch == "(":
                if depth > 0:
                    depth -= 1
                    if depth == 0:
                        return j
                else:
                    return None
    return None


def _lead_join_on_after_close_alias(lines: List[str], idx: int) -> Optional[int]:
    """``) as alias`` 下一行的 ``join``/``left join``/``on`` 与同层 ``from``/``join`` 首列对齐。

    即：与开括号 ``(`` 的上一行（``from``、``from 表``、独占的 ``left join`` 等）行首同列；若上一行也是
    ``) as`` 后的 join，则沿链递归到真正的 ``from``/首段 join。
    """
    if idx < 1:
        return None
    prev = lines[idx - 1]
    if not re.match(r"^\s*\)\s+as\s+\S", prev, re.IGNORECASE):
        return None
    cur = lines[idx].strip()
    if not (_JOIN_ONLY_LINE_RE.match(cur) or re.match(r"^on\b", cur, re.IGNORECASE)):
        return None
    oi = _matching_open_paren_line_index(lines, idx - 1)
    if oi is None or oi < 1:
        return None
    pi = oi - 1
    anchor = lines[pi]
    ast = anchor.strip().lower()
    if ast == "from" or re.match(r"^from\s+\S", ast, re.IGNORECASE):
        return len(anchor) - len(anchor.lstrip())
    if _JOIN_ONLY_LINE_RE.match(ast):
        if pi >= 1 and re.match(r"^\s*\)\s+as\s+\S", lines[pi - 1], re.IGNORECASE):
            rec = _lead_join_on_after_close_alias(lines, pi)
            if rec is not None:
                return rec
        return len(anchor) - len(anchor.lstrip())
    return len(anchor) - len(anchor.lstrip())


def normalize_select_keyword_spacing(lines: List[str]) -> List[str]:
    """将 ``select`` 与首字段/关键字之间的 **多个** 空白压成 **单个** 空格（如 ``select  col`` → ``select col``）。"""
    out: List[str] = []
    for line in lines:
        st = line.lstrip()
        if st.startswith("--") or st.startswith("/*"):
            out.append(line)
            continue
        raw = line.rstrip("\n")
        m = re.match(r"^(\s*select)(\s{2,})(.*)$", raw, re.IGNORECASE)
        if not m:
            out.append(line)
            continue
        tail = m.group(3)
        merged = m.group(1) + " " + tail
        if line.endswith("\n") and not merged.endswith("\n"):
            merged += "\n"
        elif not line.endswith("\n") and merged.endswith("\n"):
            merged = merged.rstrip("\n")
        out.append(merged)
    return out


def _case_when_fully_closed_on_line(lb: str, outer_case_col: int) -> bool:
    """自 ``outer_case_col`` 起的 ``case when`` 是否在同一物理行内与其配对的 ``end`` 完全闭合（规则 9–10、13）。

    忽略 ``--`` 行尾注释、``/* */``、单/双引号、反引号内文本；仅统计语法级 ``case when`` / ``end`` 配对深度。
    """
    lb = lb.split("\n", 1)[0]
    n = len(lb)
    if outer_case_col < 0 or outer_case_col >= n:
        return False
    if not re.match(r"(?i)case\s+when\b", lb[outer_case_col:]):
        return False

    depth = 0
    j = outer_case_col
    mode = "code"

    while j < n:
        ch = lb[j]

        if mode == "code":
            if ch == "-" and j + 1 < n and lb[j + 1] == "-":
                j += 2
                while j < n:
                    if lb[j] == "\n":
                        break
                    j += 1
                continue
            if ch == "/" and j + 1 < n and lb[j + 1] == "*":
                mode = "block_comment"
                j += 2
                continue
            if ch == "'":
                mode = "sq"
                j += 1
                continue
            if ch == '"':
                mode = "dq"
                j += 1
                continue
            if ch == "`":
                mode = "bt"
                j += 1
                continue

            m_cw = re.match(r"(?i)case\s+when\b", lb[j:])
            if m_cw:
                depth += 1
                j += m_cw.end()
                continue
            m_end = re.match(r"(?i)end\b", lb[j:])
            if m_end:
                depth -= 1
                j += m_end.end()
                if depth < 0:
                    return False
                if depth == 0:
                    return True
                continue
            j += 1
            continue

        if mode == "block_comment":
            if ch == "*" and j + 1 < n and lb[j + 1] == "/":
                mode = "code"
                j += 2
            else:
                j += 1
            continue

        if mode == "sq":
            if ch == "'":
                if j + 1 < n and lb[j + 1] == "'":
                    j += 2
                else:
                    mode = "code"
                    j += 1
            else:
                j += 1
            continue

        if mode == "dq":
            if ch == '"':
                if j + 1 < n and lb[j + 1] == '"':
                    j += 2
                else:
                    mode = "code"
                    j += 1
            else:
                j += 1
            continue

        if mode == "bt":
            if ch == "`":
                if j + 1 < n and lb[j + 1] == "`":
                    j += 2
                else:
                    mode = "code"
                    j += 1
            else:
                j += 1
            continue

        j += 1

    return False


def _case_when_keyword_columns(line: str) -> Optional[Tuple[int, int]]:
    """返回 ``(case`` 起始列, ``when`` 起始列) 的字符下标；用于 ``else`` 与 ``when`` 对齐、``end`` 与 ``case`` 对齐。"""
    case_m = re.search(r"(?i)\bcase\b", line)
    if not case_m:
        return None
    when_m = re.search(r"(?i)\bcase\s+(when\b)", line)
    if not when_m:
        return None
    return (case_m.start(), when_m.start(1))


def _replace_leading_indent_first_line(raw: str, target_spaces: int) -> str:
    """仅替换首物理行行首空白；若已是 ``target_spaces`` 则原样返回（幂等，规则 19–21）。

    若 ``raw`` 内含换行（多物理行合一字符串），不做改写以免破坏结构。
    """
    ends_nl = raw.endswith("\n")
    body = raw[:-1] if ends_nl else raw
    if "\n" in body:
        return raw
    lb = body
    st = lb.lstrip(" \t")
    cur = len(lb) - len(lb.lstrip(" \t"))
    if cur == target_spaces:
        return raw
    out = " " * target_spaces + st
    if ends_nl:
        out += "\n"
    return out


def _is_allowed_between_select_and_from_clause(st: str) -> bool:
    """判断 ``select`` 与同层 ``from`` / ``from (`` 之间是否仍为「选列续行」而非新子句。

    含 ``case/when/else/end`` 折行、``) as col`` 等，以便 ``from`` 与 ``select`` 关键字同列对齐。
    """
    if not st or st.startswith("--"):
        return True
    if st.startswith(","):
        return True
    if re.match(r"^union\b", st, re.IGNORECASE):
        return True
    if re.match(r"^(when|else|end|case|then)\b", st, re.IGNORECASE):
        return True
    if st.startswith(")"):
        return True
    return False


def _clause_indent_from_prior_select_only_list(
    processed_subquery: List[str], idx: int, floor_indent: int
) -> Optional[int]:
    """若 ``processed_subquery[idx]`` 为 ``from 表`` 或 ``from`` 独占一行且下一行为 ``(``，且自上一 ``select`` 起仅有逗号/注释/空行，则返回该 ``select`` 行首缩进列；否则 ``None``。

    ``floor_indent`` 保留参数供调用方统一签名，本函数成功路径不与其取 max，以免注释对齐的窄 ``select`` 后 ``from`` 被拉到过大 ``target_indent``。
    """
    _ = floor_indent
    st = processed_subquery[idx].strip()
    from_with_table = bool(re.match(r"^from\s+\S", st, re.IGNORECASE))
    from_then_open_paren = (
        bool(re.match(r"^from\b", st, re.IGNORECASE))
        and not from_with_table
        and idx + 1 < len(processed_subquery)
        and processed_subquery[idx + 1].strip() == "("
    )
    if not (from_with_table or from_then_open_paren):
        return None
    _sel_lead: Optional[int] = None
    _last_sel_i: Optional[int] = None
    for _bk in range(idx):
        _ps = processed_subquery[_bk].strip()
        if not _ps or _ps.startswith("--"):
            continue
        if re.match(r"^select\b", _ps, re.IGNORECASE):
            _ln = processed_subquery[_bk]
            _sel_lead = len(_ln) - len(_ln.lstrip())
            _last_sel_i = _bk
    if _last_sel_i is None or _sel_lead is None:
        return None
    for _j in range(_last_sel_i + 1, idx):
        _st2 = processed_subquery[_j].strip()
        if _is_allowed_between_select_and_from_clause(_st2):
            continue
        return None
    return _sel_lead


def _leading_indent_nearest_preceding_from(
    processed_subquery: List[str], idx: int
) -> Optional[int]:
    """从 ``idx-1`` 向上找与当前行同层的 ``from 表…`` 行首缩进；跳过空行、``--``、``lateral view`` 续行及闭合子查询内的 ``from``。"""
    unc = 0
    j = idx - 1
    while j >= 0:
        raw = processed_subquery[j]
        st = raw.strip()
        if not st:
            j -= 1
            continue
        if st.startswith("--"):
            j -= 1
            continue
        for ch in reversed(raw):
            if ch == ")":
                unc += 1
            elif ch == "(":
                if unc > 0:
                    unc -= 1
        if re.match(r"^lateral\s+view\b", st, re.IGNORECASE):
            j -= 1
            continue
        if re.match(r"^from\b", st, re.IGNORECASE) and unc == 0:
            return len(raw) - len(raw.lstrip())
        j -= 1
    return None


def _leading_indent_nearest_preceding_from_for_where(
    processed_subquery: List[str], idx: int
) -> Optional[int]:
    """为 ``where`` 找「与当前 where 同属一层 SELECT」的 ``from 表`` 行首缩进。

    自 ``idx-1`` 向上逐行、每行自右向左扫圆括号，维护未匹配的 ``)`` 数 ``unc``；仅当 ``unc==0`` 时
    才接受 ``from\s+\S``，从而跳过 ``join (`` 子查询内的 ``from``（避免 where 被对齐到内层 from）。
    不解析字符串/注释内括号，与现有启发式一致。
    """
    unc = 0
    j = idx - 1
    while j >= 0:
        raw = processed_subquery[j]
        st = raw.strip()
        if not st:
            j -= 1
            continue
        if st.startswith("--"):
            j -= 1
            continue
        for ch in reversed(raw):
            if ch == ")":
                unc += 1
            elif ch == "(":
                if unc > 0:
                    unc -= 1
        if re.match(r"^lateral\s+view\b", st, re.IGNORECASE):
            j -= 1
            continue
        if re.match(r"^from\s+\S", st, re.IGNORECASE) and unc == 0:
            return len(raw) - len(raw.lstrip())
        j -= 1
    return None


def fix_open_paren_indent_after_lone_from(lines: List[str]) -> List[str]:
    """若 ``from`` / 独占 ``join`` 的下一行仅为 ``(``，将 ``(`` 与上一关键字行首同列。

    同时将 ``(`` 到配对 ``)`` 之间的子查询体整体偏移相同列差，并对齐 ``)``。
    """
    if not lines:
        return lines
    out = list(lines)
    i = 1
    while i < len(out):
        line = out[i]
        if line.strip() != "(":
            i += 1
            continue
        prev = out[i - 1]
        pst = prev.strip()
        pst_l = pst.lower()
        if not (pst_l == "from" or _JOIN_ONLY_LINE_RE.match(pst)):
            i += 1
            continue
        kw_lead = len(prev) - len(prev.lstrip())
        old_lead = len(line) - len(line.lstrip())
        delta = kw_lead - old_lead
        if delta != 0:
            nl = line.endswith("\n")
            out[i] = " " * kw_lead + "(" + ("\n" if nl else "")
        depth = 1
        j = i + 1
        while j < len(out) and depth > 0:
            sj = out[j].strip()
            pd = _paren_delta_ignore_strings_sq(out[j])
            depth += pd
            if depth <= 0 and re.match(r"^\)", sj):
                old_j = len(out[j]) - len(out[j].lstrip())
                if old_j != kw_lead or delta != 0:
                    nlj = out[j].endswith("\n")
                    out[j] = " " * kw_lead + sj + ("\n" if nlj else "")
                break
            if delta != 0:
                old_j = len(out[j]) - len(out[j].lstrip())
                new_j = max(0, old_j + delta)
                nlj = out[j].endswith("\n")
                out[j] = " " * new_j + sj + ("\n" if nlj else "")
            j += 1
        if delta != 0:
            i = j + 1
        else:
            i += 1
    return out


def align_subquery_brackets(lines: List[str]) -> List[str]:
    """对齐子查询括号：括号与 FROM/JOIN 或 CTE（``with … as`` / ``, … as``）对齐，第一层体行首=定义行首列+6。

    第一层内相对缩进以首条 ``select``/``group by`` 行行首为参照，避免 ``when``/``else``/``end`` 参与 min 拉低整块。

    递归处理嵌套的子查询（递归体为单遍 ``_align_subquery_brackets_pass``）。

    **单次对外调用内部**重复单遍处理直至不再变化，以合并原预处理中连续多轮 ``align_subquery_brackets`` 的收敛因果。

    ⚠️ 重要：必须保证SQL语法完整性，不能删除任何关键字
    边界情况：
    - 括号单独一行：left join\n(\n    select... → 正常处理
    - 括号和内容同行：left join\n(select... → 必须保留select！（2026-04-08 修复）
    - FROM 子查询：from\n(\n    select... → 同样处理
    - FROM/JOIN和括号同行：from (\n    select... → 先拆分成两行再处理
    """
    if not lines:
        return lines
    out = lines
    for _ in range(_ALIGN_SUBQUERY_BRACKETS_MAX_STABLE):
        nxt = _align_subquery_brackets_pass(out)
        if nxt == out:
            return nxt
        out = nxt
    return out


def split_from_join_open_paren(lines: List[str]) -> List[str]:
    """将 ``from (`` / ``join (`` / ``from (select ...`` / 独立 ``(select ...`` 等拆为独立行。"""
    result: List[str] = []
    for line in lines:
        m1 = re.match(
            r"^(\s*)(from|left\s+join|right\s+join|inner\s+join|cross\s+join|full\s+outer\s+join|full\s+join|join)\s*\(\s*$",
            line, re.IGNORECASE,
        )
        if m1:
            indent, kw = m1.group(1), m1.group(2)
            suf = '\n' if line.endswith('\n') else ''
            result.append(indent + kw + suf)
            result.append(indent + '(' + suf)
            continue
        m2 = re.match(
            r"^(\s*)(from|left\s+join|right\s+join|inner\s+join|cross\s+join|full\s+outer\s+join|full\s+join|join)\s*\((.+)$",
            line, re.IGNORECASE,
        )
        if m2:
            indent, kw, content = m2.group(1), m2.group(2), m2.group(3)
            has_nl = line.endswith('\n')
            if has_nl and content.endswith('\n'):
                content = content[:-1]
            suf = '\n' if has_nl else ''
            result.append(indent + kw + suf)
            result.append(indent + '(' + suf)
            result.append(' ' * (len(indent) + SUBQUERY_INDENT) + content.lstrip() + suf)
            continue
        m3 = re.match(
            r"^(\s*)\((\s*select\b.+)$",
            line, re.IGNORECASE,
        )
        if m3:
            indent, content = m3.group(1), m3.group(2)
            has_nl = line.endswith('\n')
            if has_nl and content.endswith('\n'):
                content = content[:-1]
            suf = '\n' if has_nl else ''
            result.append(indent + '(' + suf)
            result.append(indent + ' ' * SUBQUERY_INDENT + content.lstrip() + suf)
            continue
        result.append(line)
    return result


def _align_subquery_brackets_pass(lines: List[str]) -> List[str]:
    """单遍子查询括号对齐；由 ``align_subquery_brackets`` 迭代至稳定调用。"""
    # 第一步：预处理 - 将 FROM/JOIN 后的括号拆分到新行
    preprocessed_lines = split_from_join_open_paren(lines)

    def _indent_inner_body_after_prev_lone_paren(
        subq: List[str], end_idx: int
    ) -> Optional[int]:
        """自 ``end_idx-1`` 起向上：遇 ``) as`` 即停（勿跨已闭合子查询）；命中独占 ``(`` 则 ``(`` 列 + ``SUBQUERY_INDENT``。"""
        j = end_idx - 1
        while j >= 0:
            raw0 = subq[j].split("\n", 1)[0]
            st = raw0.strip()
            if not st or st.startswith("--"):
                j -= 1
                continue
            if re.match(r"^\)\s+as\b", st, re.I):
                return None
            if st == "(":
                return len(subq[j]) - len(subq[j].lstrip(" \t")) + SUBQUERY_INDENT
            j -= 1
        return None

    # 第二步：正常处理子查询括号
    new_lines = []
    i = 0

    while i < len(preprocessed_lines):
        line = preprocessed_lines[i]
        stripped = line.strip().lower()

        # 检测 FROM/JOIN 独占行，或 ``with … as`` / ``, … as`` 独占行（CTE 与括号对齐规则同 from/join）
        _from_join_only = re.match(
            r"^\s*(from|left\s+join|right\s+join|inner\s+join|cross\s+join|full\s+outer\s+join|full\s+join|join)\s*$",
            line,
            re.IGNORECASE,
        )
        # 补充 CTE 匹配：逗号独占一行 + 可能有注释 + ``cte_name as`` 独占一行
        _cte_match = _CTE_AS_OPEN_HEAD_RE.match(line)
        if not _cte_match and not _from_join_only and re.match(
            r"^\s*\w+\s+as\s*$", line, re.IGNORECASE
        ):
            for _bk_cte in range(len(new_lines) - 1, -1, -1):
                _bk_cte_s = new_lines[_bk_cte].strip()
                if not _bk_cte_s or _bk_cte_s.startswith("--"):
                    continue
                if _bk_cte_s == ",":
                    _cte_match = True
                break
        if _from_join_only or _cte_match:
            base_indent = len(line) - len(line.lstrip())
            # 递归层中 from/join 原始缩进可能过浅（如 UNION 分支内的 from 未被上层调整）。
            # 从 new_lines 中取最近同层 select 行首缩进作为纠正参照。
            # 但若上一非空行已是 ``on …``，说明本 join 与上一子查询同级外链，不得误用上一子查询体内的 ``select`` 列（否则 ``(`` 会多 ``SUBQUERY_INDENT``）。
            if _from_join_only and new_lines:
                _prev_nonempty_st: Optional[str] = None
                for _bk in range(len(new_lines) - 1, -1, -1):
                    _bks = new_lines[_bk].strip()
                    if not _bks or _bks.startswith("--"):
                        continue
                    _prev_nonempty_st = _bks
                    break
                _skip_sel_bump = bool(
                    _prev_nonempty_st and re.match(r"^on\b", _prev_nonempty_st, re.IGNORECASE)
                )
                _sel_ind_ref: Optional[int] = None
                if not _skip_sel_bump:
                    for _bk in range(len(new_lines) - 1, -1, -1):
                        _bks = new_lines[_bk].strip().lower()
                        if not _bks or _bks.startswith("--"):
                            continue
                        if _bks.startswith("select"):
                            _sel_ind_ref = len(new_lines[_bk]) - len(new_lines[_bk].lstrip())
                            break
                        if re.match(r"^(union|from|\(|\))", _bks):
                            break
                if (
                    not _skip_sel_bump
                    and _sel_ind_ref is not None
                    and _sel_ind_ref > base_indent
                ):
                    has_nl = line.endswith("\n")
                    line = " " * _sel_ind_ref + line.strip() + ("\n" if has_nl else "")
                    base_indent = _sel_ind_ref
            new_lines.append(line)
            i += 1

            # 检查下一行是否是左括号
            if i < len(preprocessed_lines):
                next_line = preprocessed_lines[i]
                next_stripped = next_line.strip()

                if next_stripped == '(' or next_stripped.startswith('('):
                    # 调整左括号缩进，与FROM/JOIN对齐
                    has_newline = next_line.endswith('\n')

                    # 检查括号后是否有内容（如 "(select"）
                    if next_stripped.startswith('(') and len(next_stripped) > 1:
                        # 括号和内容在同一行，如 "(select"
                        bracket_content = next_stripped[1:].lstrip()  # 提取括号后的内容
                        new_bracket_line = ' ' * base_indent + '('
                        if has_newline:
                            new_bracket_line += '\n'
                        new_lines.append(new_bracket_line)

                        # 将括号后的内容作为第一行子查询内容
                        content_line = ' ' * (base_indent + 6) + bracket_content
                        if has_newline:
                            content_line += '\n'
                        new_lines.append(content_line)
                    else:
                        # 括号单独一行
                        new_bracket_line = ' ' * base_indent + '('
                        if has_newline:
                            new_bracket_line += '\n'
                        new_lines.append(new_bracket_line)

                    i += 1

                    # 收集子查询内的所有行
                    target_indent = base_indent + 6  # 括号缩进 + 标准6空格
                    bracket_depth = 1
                    subquery_lines = []
                    closing_bracket_line = None

                    while i < len(preprocessed_lines) and bracket_depth > 0:
                        inner_line = preprocessed_lines[i]
                        inner_stripped = inner_line.strip()

                        # 检测右括号（可能带表别名）
                        if re.match(r'^\s*\)\s*\w*', inner_line):
                            _line_open = inner_stripped.count('(')
                            _line_close = inner_stripped.count(')')
                            bracket_depth += _line_open - _line_close
                            if bracket_depth <= 0:
                                closing_bracket_line = inner_line
                                bracket_depth = max(bracket_depth, 0)
                                i += 1
                                break
                            subquery_lines.append(inner_line)
                            i += 1
                            continue

                        # 检测内嵌的左括号
                        _depth_before = bracket_depth
                        if '(' in inner_stripped:
                            bracket_depth += inner_stripped.count('(')
                        if ')' in inner_stripped:
                            bracket_depth -= inner_stripped.count(')')

                        if bracket_depth <= 0 and _depth_before > 0:
                            _sd = _depth_before
                            _in_sq = False
                            _split_pos = -1
                            _raw = inner_line.rstrip('\n')
                            _ci = 0
                            while _ci < len(_raw):
                                _ch = _raw[_ci]
                                if _in_sq:
                                    if _ch == "'" and _ci + 1 < len(_raw) and _raw[_ci + 1] == "'":
                                        _ci += 2
                                        continue
                                    if _ch == "'":
                                        _in_sq = False
                                    _ci += 1
                                    continue
                                if _ch == "'":
                                    _in_sq = True
                                    _ci += 1
                                    continue
                                if _ch == '(':
                                    _sd += 1
                                elif _ch == ')':
                                    _sd -= 1
                                    if _sd == 0:
                                        _split_pos = _ci
                                        break
                                _ci += 1
                            if _split_pos >= 0:
                                has_nl = inner_line.endswith('\n')
                                content_part = inner_line[:_split_pos].rstrip()
                                closing_part = inner_line[_split_pos:].rstrip('\n').strip()
                                if content_part.strip():
                                    subquery_lines.append(content_part + ('\n' if has_nl else ''))
                                closing_bracket_line = closing_part + ('\n' if has_nl else '')
                                i += 1
                                break
                            else:
                                subquery_lines.append(inner_line)
                                i += 1
                        else:
                            # 收集子查询行
                            subquery_lines.append(inner_line)
                            i += 1

                    # 递归处理子查询中的嵌套JOIN（单遍，避免与外层「迭代至稳定」重复套叠）
                    processed_subquery = _align_subquery_brackets_pass(subquery_lines)

                    # 调整子查询的基础缩进（保留相对缩进）
                    if processed_subquery:
                        # 与同块 select/group by 首字段对齐的「逗号列」（与 align_field_names 一致），
                        # 避免 `, case` 行因 min_indent 相对缩进比 `, col as` 多 1 格。
                        comma_prefix_spaces = None
                        _bd_scan = 0
                        for _sl in processed_subquery:
                            if re.match(r'^\s*\(', _sl):
                                _bd_scan += 1
                                continue
                            if re.match(r'^\s*\)', _sl):
                                _bd_scan -= 1
                                continue
                            if _bd_scan != 0:
                                continue
                            _st = _sl.strip()
                            if re.match(r'^(select|group\s+by)\s+\S', _st, re.IGNORECASE):
                                _sm = re.match(
                                    r'^(\s*)(select|group\s+by)\s+(\S+)', _sl, re.IGNORECASE
                                )
                                if _sm:
                                    _ind = _sm.group(1)
                                    _kw = _sm.group(2)
                                    _ke = len(_ind) + len(_kw)
                                    _af = _sl[_ke:]
                                    _spa = len(_af) - len(_af.lstrip())
                                    _fsp = _ke + _spa
                                    comma_prefix_spaces = max(0, _fsp - 2)
                                break

                        # 【2026-04-11 修复】只计算第一层（括号深度=0）的非关键字行的最小缩进
                        # 避免嵌套子查询的行影响 min_indent 计算
                        min_indent = float('inf')
                        bracket_depth = 0
                        for subline in processed_subquery:
                            stripped = subline.strip()

                            # 更新括号深度
                            if re.match(r'^\s*\(', subline):
                                bracket_depth += 1
                                continue
                            elif re.match(r'^\s*\)', subline):
                                bracket_depth -= 1
                                continue

                            # 只考虑括号深度为0的行（不在嵌套子查询中）
                            if bracket_depth == 0 and stripped:
                                # 注释行参与 min_indent，避免 ``--`` 与下一行 ``select`` 差 1 格时相对缩进把 ``select`` 多推一格
                                if stripped.startswith('--'):
                                    current_indent = len(subline) - len(subline.lstrip())
                                    min_indent = min(min_indent, current_indent)
                                elif not re.match(
                                    r'^(from|where|group\s+by|having|order\s+by|limit|union|left\s+join|right\s+join|inner\s+join|cross\s+join|full\s+outer\s+join|full\s+join|join|on|and|or|when|else|end)\b',
                                    stripped,
                                    re.IGNORECASE,
                                ):
                                    current_indent = len(subline) - len(subline.lstrip())
                                    min_indent = min(min_indent, current_indent)

                        if min_indent == float('inf'):
                            min_indent = 0

                        # 第一层相对缩进：以首条 ``select``/``group by`` 行行首为参照（fallback 为 min_indent），
                        # 避免 ``when``/``else``/``end`` 等参与 min 拉低导致整块偏离「关键字列 + 6」。
                        _ref_sel_lead: Optional[int] = None
                        _bd_rf = 0
                        for _sl in processed_subquery:
                            if re.match(r"^\s*\(", _sl):
                                _bd_rf += 1
                                continue
                            if re.match(r"^\s*\)", _sl):
                                _bd_rf -= 1
                                continue
                            if _bd_rf != 0:
                                continue
                            _st = _sl.strip()
                            if not _st or _st.startswith("--"):
                                continue
                            if re.match(r"^(select|group\s+by)\b", _st, re.IGNORECASE):
                                _ref_sel_lead = len(_sl) - len(_sl.lstrip(" \t"))
                                break
                        _rel_base = (
                            _ref_sel_lead if _ref_sel_lead is not None else min_indent
                        )

                        # 【2026-04-11 修复】调整缩进时也要跟踪括号深度
                        # 只调整第一层的行，嵌套子查询的行保持不变（已被递归处理）
                        _first_body_idx = None
                        for _fi, _fl in enumerate(processed_subquery):
                            _fs = _fl.strip()
                            if not _fs or _fs.startswith("--"):
                                continue
                            _first_body_idx = _fi
                            break
                        bracket_depth = 0
                        paren_col_stack: List[int] = []
                        for idx, subline in enumerate(processed_subquery):
                            subline_stripped = subline.strip()

                            # 检测并调整括号行
                            if re.match(r'^\s*\(', subline):
                                has_newline = subline.endswith('\n')
                                # 左括号：保持当前层级的缩进
                                # bracket_depth == 0 表示这是第一层的左括号，应该使用 target_indent
                                # bracket_depth > 0 表示这是嵌套的左括号，保持原样
                                if bracket_depth == 0:
                                    _paren_lead = target_indent
                                    # ``from`` / 独占 ``join`` 后的 ``(``：与上一关键字行首同列
                                    if idx > 0 and subline_stripped == "(":
                                        _prev_ln = processed_subquery[idx - 1]
                                        _pst = _prev_ln.strip()
                                        if _pst.lower() == "from":
                                            # 从 ``new_lines`` 取刚写入的 ``from`` 已调整后缩进，
                                            # 避免从递归未调整的 ``processed_subquery`` 查 select 得到陈旧值。
                                            _from_in_new = None
                                            for _bk in range(len(new_lines) - 1, -1, -1):
                                                _bs = new_lines[_bk].strip().lower()
                                                if not _bs or _bs.startswith("--"):
                                                    continue
                                                if _bs == "from":
                                                    _from_in_new = len(new_lines[_bk]) - len(new_lines[_bk].lstrip())
                                                break
                                            if _from_in_new is not None:
                                                _paren_lead = _from_in_new
                                            else:
                                                _fi = idx - 1
                                                _al_paren = (
                                                    _clause_indent_from_prior_select_only_list(
                                                        processed_subquery, _fi, target_indent
                                                    )
                                                )
                                                if _al_paren is not None:
                                                    _paren_lead = _al_paren
                                        elif _JOIN_ONLY_LINE_RE.match(_pst):
                                            _paren_lead = len(_prev_ln) - len(
                                                _prev_ln.lstrip()
                                            )
                                    new_inner_line = (
                                        " " * _paren_lead + subline_stripped
                                    )
                                else:
                                    # 嵌套层 (：如果前一行 new_lines 中的 from/join 已被调整到更大缩进，
                                    # ( 应与之同列而非保留旧缩进
                                    _nest_paren_ind = None
                                    if subline_stripped == "(" and new_lines:
                                        _prev_nls = new_lines[-1].strip().lower()
                                        if _prev_nls == "from" or _JOIN_ONLY_LINE_RE.match(new_lines[-1].strip()):
                                            _nest_paren_ind = len(new_lines[-1]) - len(new_lines[-1].lstrip())
                                    if _nest_paren_ind is not None:
                                        new_inner_line = " " * _nest_paren_ind + subline_stripped
                                    else:
                                        new_inner_line = subline.rstrip('\n')
                                if has_newline:
                                    new_inner_line += '\n'
                                new_lines.append(new_inner_line)
                                _pw = new_inner_line.rstrip("\n")
                                paren_col_stack.append(
                                    len(_pw) - len(_pw.lstrip())
                                )
                                bracket_depth += 1
                                continue
                            elif re.match(r'^\s*\)[^)]*$', subline):
                                _popped_col = paren_col_stack.pop() if paren_col_stack else base_indent
                                bracket_depth -= 1
                                has_newline = subline.endswith('\n')
                                if bracket_depth == 0:
                                    new_inner_line = ' ' * _popped_col + subline_stripped
                                else:
                                    new_inner_line = subline.rstrip('\n')
                                if has_newline:
                                    new_inner_line += '\n'
                                new_lines.append(new_inner_line)
                                continue

                            if subline_stripped and not subline_stripped.startswith('--'):
                                has_newline = subline.endswith('\n')

                                # 【关键】只调整第一层（bracket_depth == 0）的行
                                # 嵌套子查询中的行（bracket_depth > 0）保持不变
                                if bracket_depth == 0:
                                    # SQL关键字行（FROM/WHERE等）直接使用target_indent
                                    is_sql_keyword = re.match(r'^(from|where|group\s+by|having|order\s+by|limit|union|left\s+join|right\s+join|inner\s+join|cross\s+join|full\s+outer\s+join|full\s+join|join|on|and|or)\b', subline_stripped, re.IGNORECASE)
                                    # ``) as alias`` 下一行的 **独占** ``join``/``on``：与同层 ``from``/``join`` 同列；否则与 ``)`` 同列
                                    # 注意：仅匹配独占一行的 join 关键字，避免 ``left join table as b`` 被误推到外层缩进
                                    if (
                                        idx > 0
                                        and is_sql_keyword
                                        and re.match(
                                            r"^\s*\)\s+as\s+\S",
                                            processed_subquery[idx - 1],
                                            re.IGNORECASE,
                                        )
                                        and (
                                            _JOIN_ONLY_LINE_RE.match(
                                                subline_stripped
                                            )
                                            or re.match(
                                                r"^on\b",
                                                subline_stripped,
                                                re.IGNORECASE,
                                            )
                                        )
                                    ):
                                        _lja = _lead_join_on_after_close_alias(
                                            processed_subquery, idx
                                        )
                                        # _lja 基于 processed_subquery（旧缩进），
                                        # 外层 rewrite 可能已将 from 调整到 target_indent；兜底确保 join 不低于 target_indent
                                        if _lja is not None and _lja < target_indent:
                                            _lja = target_indent
                                        if _lja is not None:
                                            new_inner_line = (
                                                " " * _lja + subline_stripped
                                            )
                                        else:
                                            _cj_join = len(
                                                processed_subquery[idx - 1]
                                            ) - len(
                                                processed_subquery[idx - 1].lstrip()
                                            )
                                            if _cj_join < target_indent:
                                                _cj_join = target_indent
                                            new_inner_line = (
                                                " " * _cj_join + subline_stripped
                                            )
                                    # 须先于「select 且上一行为注释」分支：否则子查询内 ``--`` 下一行 ``select`` 会误用注释列宽，少一层 ``target_indent``
                                    elif (
                                        _first_body_idx is not None
                                        and idx == _first_body_idx
                                        and re.match(
                                            r'^select\b', subline_stripped, re.IGNORECASE
                                        )
                                    ):
                                        # ``from/join`` 后子查询体不含单独 ``(`` 行时，首条非注释常为 ``select``（前可有空行），须与块内 ``from``/``where`` 同用 target_indent
                                        new_inner_line = (
                                            ' ' * target_indent + subline_stripped
                                        )
                                    elif re.match(
                                        r"^select\b", subline_stripped, re.IGNORECASE
                                    ):
                                        _uq_sel = (
                                            _leading_indent_union_above_select_through_comments(
                                                processed_subquery, idx
                                            )
                                        )
                                        if _uq_sel is not None:
                                            new_inner_line = (
                                                " " * _uq_sel + subline_stripped
                                            )
                                        elif (
                                            idx > 0
                                            and processed_subquery[idx - 1]
                                            .strip()
                                            .startswith("--")
                                        ):
                                            new_inner_line = (
                                                " " * target_indent + subline_stripped
                                            )
                                        else:
                                            _cur_id = len(subline) - len(subline.lstrip())
                                            _rel_id = _cur_id - _rel_base
                                            new_inner_line = (
                                                " "
                                                * (target_indent + _rel_id)
                                                + subline_stripped
                                            )
                                    elif is_sql_keyword:
                                        # ``union``/``union all``：与同链路上一段的 ``select`` 行首同列（勿用固定 ``target_indent``，否则与相对缩进的 ``select`` 差一档）
                                        if re.match(r"^union\b", subline_stripped, re.IGNORECASE):
                                            _u_il = _leading_indent_first_select_before_index(
                                                processed_subquery, idx
                                            )
                                            if _u_il is None:
                                                _u_il = (
                                                    _leading_indent_nearest_preceding_select(
                                                        processed_subquery, idx
                                                    )
                                                )
                                            if _u_il is not None:
                                                new_inner_line = (
                                                    " " * _u_il + subline_stripped
                                                )
                                            else:
                                                new_inner_line = (
                                                    " " * target_indent + subline_stripped
                                                )
                                        # ``from 表`` / ``from`` 下一行 ``(``：与上一 ``select`` 间若仅有逗号/注释/空行，则与 ``select`` 行首同列
                                        elif re.match(
                                            r"^from\b", subline_stripped, re.IGNORECASE
                                        ):
                                            _al0 = (
                                                _clause_indent_from_prior_select_only_list(
                                                    processed_subquery, idx, target_indent
                                                )
                                            )
                                            if _al0 is not None and _al0 >= target_indent:
                                                new_inner_line = (
                                                    " " * _al0 + subline_stripped
                                                )
                                            else:
                                                new_inner_line = (
                                                    " " * target_indent + subline_stripped
                                                )
                                        elif (
                                            re.match(r'^where\b', subline_stripped, re.I)
                                            and idx > 0
                                        ):
                                            _wsel = _leading_indent_enclosing_select_before(
                                                processed_subquery, idx
                                            )
                                            if _wsel is not None and _wsel >= target_indent:
                                                new_inner_line = (
                                                    " " * _wsel + subline_stripped
                                                )
                                            else:
                                                new_inner_line = (
                                                    " " * target_indent + subline_stripped
                                                )
                                        elif re.match(
                                            r"^group\s+by\b",
                                            subline_stripped,
                                            re.IGNORECASE,
                                        ):
                                            _g0 = _leading_indent_enclosing_select_before(
                                                processed_subquery, idx
                                            )
                                            if _g0 is not None and _g0 >= target_indent:
                                                new_inner_line = (
                                                    " " * _g0 + subline_stripped
                                                )
                                            else:
                                                new_inner_line = (
                                                    " " * target_indent + subline_stripped
                                                )
                                        elif re.match(
                                            r"^(having|order\s+by)\b",
                                            subline_stripped,
                                            re.IGNORECASE,
                                        ):
                                            _g0 = _leading_indent_nearest_preceding_select(
                                                processed_subquery, idx
                                            )
                                            if _g0 is not None:
                                                new_inner_line = (
                                                    " " * _g0 + subline_stripped
                                                )
                                            else:
                                                new_inner_line = (
                                                    " " * target_indent + subline_stripped
                                                )
                                        else:
                                            _ej = _leading_indent_enclosing_select_before(
                                                processed_subquery, idx
                                            )
                                            if _ej is not None and _ej >= target_indent:
                                                new_inner_line = (
                                                    " " * _ej + subline_stripped
                                                )
                                            else:
                                                new_inner_line = (
                                                    ' ' * target_indent + subline_stripped
                                                )
                                    elif (
                                        comma_prefix_spaces is not None
                                        and subline_stripped.startswith(',')
                                    ):
                                        _rest = subline_stripped[1:].lstrip()
                                        new_inner_line = (
                                            ' ' * comma_prefix_spaces + ', ' + _rest
                                        )
                                    else:
                                        # ``from … as a`` 下一行的 ``lateral view``：与上一 ``from`` 同列，勿用 min_indent 相对缩进拉成满行空格
                                        if re.match(
                                            r"^lateral\s+view\b",
                                            subline_stripped,
                                            re.IGNORECASE,
                                        ):
                                            _lat_from = (
                                                _leading_indent_nearest_preceding_from(
                                                    processed_subquery, idx
                                                )
                                            )
                                            if _lat_from is not None:
                                                new_inner_line = (
                                                    " " * _lat_from + subline_stripped
                                                )
                                            else:
                                                current_indent = len(subline) - len(
                                                    subline.lstrip()
                                                )
                                                relative_indent = (
                                                    current_indent - _rel_base
                                                )
                                                new_inner_line = (
                                                    " "
                                                    * (target_indent + relative_indent)
                                                    + subline_stripped
                                                )
                                        elif (
                                            re.match(
                                                r"^case\s+when",
                                                subline_stripped,
                                                re.IGNORECASE,
                                            )
                                            and idx > 0
                                        ):
                                            _par0 = processed_subquery[idx - 1].rstrip()
                                            if _par0.endswith("("):
                                                _pln0 = processed_subquery[idx - 1]
                                                _bi0 = len(_pln0) - len(_pln0.lstrip())
                                                new_inner_line = (
                                                    " " * (_bi0 + 4) + subline_stripped
                                                )
                                            else:
                                                current_indent = len(subline) - len(
                                                    subline.lstrip()
                                                )
                                                relative_indent = (
                                                    current_indent - _rel_base
                                                )
                                                new_inner_line = (
                                                    " "
                                                    * (target_indent + relative_indent)
                                                    + subline_stripped
                                                )
                                        elif (
                                            re.match(
                                                r"^(else|end)\b",
                                                subline_stripped,
                                                re.IGNORECASE,
                                            )
                                            and idx > 0
                                        ):
                                            _pjx = idx - 1
                                            _kw_cols: Optional[Tuple[int, int]] = None
                                            while _pjx >= 0:
                                                _sx = processed_subquery[_pjx].strip()
                                                if not _sx or _sx.startswith("--"):
                                                    _pjx -= 1
                                                    continue
                                                if re.search(
                                                    r"(?i)\bcase\s+when\s+",
                                                    _sx,
                                                ):
                                                    _rx = processed_subquery[_pjx]
                                                    _kw_cols = _case_when_keyword_columns(
                                                        _rx
                                                    )
                                                    break
                                                if re.match(
                                                    r"^(from|where)\b",
                                                    _sx,
                                                    re.IGNORECASE,
                                                ):
                                                    break
                                                _pjx -= 1
                                            if _kw_cols is not None:
                                                _cc, _wc = _kw_cols
                                                if re.match(
                                                    r"^else\b",
                                                    subline_stripped,
                                                    re.IGNORECASE,
                                                ):
                                                    new_inner_line = (
                                                        " " * _wc + subline_stripped
                                                    )
                                                else:
                                                    new_inner_line = (
                                                        " " * _cc + subline_stripped
                                                    )
                                            else:
                                                current_indent = len(subline) - len(
                                                    subline.lstrip()
                                                )
                                                relative_indent = (
                                                    current_indent - _rel_base
                                                )
                                                new_inner_line = (
                                                    " "
                                                    * (target_indent + relative_indent)
                                                    + subline_stripped
                                                )
                                        else:
                                            # 非关键字行（SELECT和字段）保留相对缩进
                                            current_indent = len(subline) - len(
                                                subline.lstrip()
                                            )
                                            relative_indent = current_indent - _rel_base
                                            new_inner_line = (
                                                " "
                                                * (target_indent + relative_indent)
                                                + subline_stripped
                                            )
                                else:
                                    # 嵌套层内：``from``/``where``/``on`` 等与「紧接在 ``(`` 或注释后的 ``select``」同列
                                    # 以当前未闭合的 ``(`` 行首为基准 + 一档，避免 ``target_indent`` 与 ``from`` 后 ``(`` 已左对齐时再叠一档
                                    _ci_kw = (
                                        paren_col_stack[-1] + SUBQUERY_INDENT
                                        if paren_col_stack
                                        else target_indent
                                        + max(0, bracket_depth - 1) * SUBQUERY_INDENT
                                    )
                                    _prev_open_paren = False
                                    if idx > 0:
                                        _pj = idx - 1
                                        while _pj >= 0:
                                            _pst = processed_subquery[_pj].strip()
                                            if not _pst:
                                                _pj -= 1
                                                continue
                                            if _pst.startswith("--"):
                                                _pj -= 1
                                                continue
                                            _prev_open_paren = _pst == "("
                                            break
                                    _is_sel = re.match(
                                        r"^select\b", subline_stripped, re.IGNORECASE
                                    )
                                    _kwm = re.match(
                                        r'^(from|where|group\s+by|having|order\s+by|limit|union|left\s+join|right\s+join|inner\s+join|cross\s+join|full\s+outer\s+join|full\s+join|join|on|and|or)\b',
                                        subline_stripped,
                                        re.IGNORECASE,
                                    )
                                    _cur_lead = len(subline) - len(subline.lstrip())
                                    # 嵌套 ``(`` 后 ``max(`` 换行的内联 ``case when`` / ``else`` / ``end``（bracket_depth>0 时不进 depth==0 分支）
                                    if (
                                        re.match(
                                            r"^case\s+when",
                                            subline_stripped,
                                            re.IGNORECASE,
                                        )
                                        and idx > 0
                                        and processed_subquery[idx - 1]
                                        .rstrip()
                                        .endswith("(")
                                    ):
                                        _plnx = processed_subquery[idx - 1]
                                        _bix = len(_plnx) - len(_plnx.lstrip())
                                        new_inner_line = (
                                            " " * (_bix + 4) + subline_stripped
                                        )
                                    elif (
                                        re.match(
                                            r"^(else|end)\b",
                                            subline_stripped,
                                            re.IGNORECASE,
                                        )
                                        and idx > 0
                                    ):
                                        _pjx2 = idx - 1
                                        _kw_cols2: Optional[Tuple[int, int]] = None
                                        while _pjx2 >= 0:
                                            _sx2 = processed_subquery[_pjx2].strip()
                                            if not _sx2 or _sx2.startswith("--"):
                                                _pjx2 -= 1
                                                continue
                                            if re.search(
                                                r"(?i)\bcase\s+when\s+",
                                                _sx2,
                                            ):
                                                _rx2 = processed_subquery[_pjx2]
                                                _kw_cols2 = _case_when_keyword_columns(
                                                    _rx2
                                                )
                                                break
                                            if re.match(
                                                r"^(from|where)\b",
                                                _sx2,
                                                re.IGNORECASE,
                                            ):
                                                break
                                            _pjx2 -= 1
                                        if _kw_cols2 is not None:
                                            _cc2, _wc2 = _kw_cols2
                                            if re.match(
                                                r"^else\b",
                                                subline_stripped,
                                                re.IGNORECASE,
                                            ):
                                                new_inner_line = (
                                                    " " * _wc2 + subline_stripped
                                                )
                                            else:
                                                new_inner_line = (
                                                    " " * _cc2 + subline_stripped
                                                )
                                        else:
                                            new_inner_line = subline.rstrip("\n")
                                    elif _is_sel:
                                        _uq_n = (
                                            _leading_indent_union_above_select_through_comments(
                                                processed_subquery, idx
                                            )
                                        )
                                        if _uq_n is not None:
                                            # 递归结果中 union 的旧缩进可能 < 当前层基准，用 _ci_kw 兜底
                                            if _uq_n < _ci_kw:
                                                _uq_n = _ci_kw
                                            new_inner_line = (
                                                " " * _uq_n + subline_stripped
                                            )
                                        elif (
                                            idx > 0
                                            and processed_subquery[idx - 1]
                                            .split("\n", 1)[0]
                                            .strip()
                                            == "("
                                        ):
                                            # 独占 ``(`` 下一行首条 ``select``：``(`` 列 + 6
                                            # 从 new_lines 取已调整后的 ( 缩进（嵌套层 ( 可能已被纠正）
                                            _opc = len(new_lines[-1]) - len(
                                                new_lines[-1].lstrip(" \t")
                                            ) if new_lines and new_lines[-1].strip() == "(" else (
                                                len(processed_subquery[idx - 1]) - len(
                                                    processed_subquery[idx - 1].lstrip(" \t")
                                                )
                                            )
                                            new_inner_line = (
                                                " " * (_opc + SUBQUERY_INDENT)
                                                + subline_stripped
                                            )
                                        elif _prev_open_paren:
                                            # 已由更内层 ``join (`` 块对齐到更大缩进时，外层勿用较小 ``_ci_kw`` 回写（如 tmp2 的 from 被 6 格覆盖）
                                            if _cur_lead < _ci_kw:
                                                new_inner_line = (
                                                    " " * _ci_kw + subline_stripped
                                                )
                                            else:
                                                new_inner_line = subline.rstrip("\n")
                                        else:
                                            new_inner_line = subline.rstrip("\n")
                                    elif _kwm:
                                        # 嵌套层内 ``union``/``from``/``where`` 等与上一 ``select`` 或 ``from`` 行对齐
                                        _ljn_peer = None
                                        if (
                                            idx > 0
                                            and re.match(
                                                r"^\s*\)\s+as\s+\S",
                                                processed_subquery[idx - 1],
                                                re.IGNORECASE,
                                            )
                                            and (
                                                re.search(
                                                    r"\bjoin\b",
                                                    subline_stripped,
                                                    re.IGNORECASE,
                                                )
                                                or re.match(
                                                    r"^on\b",
                                                    subline_stripped,
                                                    re.IGNORECASE,
                                                )
                                            )
                                        ):
                                            _ljn_peer = _lead_join_on_after_close_alias(
                                                processed_subquery, idx
                                            )
                                        # 旧缩进可能低于当前嵌套层基准，兜底到 _ci_kw
                                        if _ljn_peer is not None and _ljn_peer < _ci_kw:
                                            _ljn_peer = _ci_kw
                                        if _ljn_peer is not None:
                                            new_inner_line = (
                                                " " * _ljn_peer + subline_stripped
                                            )
                                        else:
                                            _al_fix = None
                                            _ipa_kw = None
                                            if paren_col_stack:
                                                _ipa_kw = _indent_inner_body_after_prev_lone_paren(
                                                    processed_subquery, idx
                                                )
                                            if re.match(
                                                r"^union\b",
                                                subline_stripped,
                                                re.IGNORECASE,
                                            ):
                                                _al_fix = (
                                                    _leading_indent_first_select_before_index(
                                                        processed_subquery, idx
                                                    )
                                                )
                                                if _al_fix is None:
                                                    _al_fix = _leading_indent_nearest_preceding_select(
                                                        processed_subquery, idx
                                                    )
                                            elif re.match(
                                                r"^from\b",
                                                subline_stripped,
                                                re.IGNORECASE,
                                            ):
                                                if _ipa_kw is not None and re.match(
                                                    r"^from\s+\S",
                                                    subline_stripped,
                                                    re.IGNORECASE,
                                                ):
                                                    _al_fix = _ipa_kw
                                                else:
                                                    _al_fix = (
                                                        _clause_indent_from_prior_select_only_list(
                                                            processed_subquery,
                                                            idx,
                                                            target_indent,
                                                        )
                                                    )
                                                    # 递归结果中的旧缩进可能 < 当前层基准（UNION 分支的 from 用了旧 indent），
                                                    # 用 _ci_kw 兜底确保不低于当前嵌套层的正确缩进
                                                    if _al_fix is not None and _al_fix < _ci_kw:
                                                        _al_fix = _ci_kw
                                            elif (
                                                re.match(
                                                    r"^where\b",
                                                    subline_stripped,
                                                    re.IGNORECASE,
                                                )
                                                and idx > 0
                                            ):
                                                if _ipa_kw is not None:
                                                    _al_fix = _ipa_kw
                                                else:
                                                    _w2 = _leading_indent_enclosing_select_before(
                                                        processed_subquery, idx
                                                    )
                                                    if _w2 is not None:
                                                        _al_fix = _w2
                                            elif re.match(
                                                r"^group\s+by\b",
                                                subline_stripped,
                                                re.IGNORECASE,
                                            ):
                                                if _ipa_kw is not None:
                                                    _al_fix = _ipa_kw
                                                else:
                                                    _gx = _leading_indent_enclosing_select_before(
                                                        processed_subquery, idx
                                                    )
                                                    if _gx is not None:
                                                        _al_fix = _gx
                                            elif re.match(
                                                r"^(having|order\s+by)\b",
                                                subline_stripped,
                                                re.IGNORECASE,
                                            ):
                                                _gx = (
                                                    _leading_indent_nearest_preceding_select(
                                                        processed_subquery, idx
                                                    )
                                                )
                                                if _gx is not None:
                                                    _al_fix = _gx
                                            if _al_fix is not None:
                                                # 递归结果中的旧缩进可能 < 当前层基准，统一兜底
                                                if _al_fix < _ci_kw:
                                                    _al_fix = _ci_kw
                                                new_inner_line = (
                                                    " " * _al_fix + subline_stripped
                                                )
                                            elif _cur_lead < _ci_kw:
                                                new_inner_line = (
                                                    " " * _ci_kw + subline_stripped
                                                )
                                            else:
                                                new_inner_line = subline.rstrip("\n")
                                    elif re.match(
                                        r"^lateral\s+view\b",
                                        subline_stripped,
                                        re.IGNORECASE,
                                    ):
                                        _lat2 = _leading_indent_nearest_preceding_from(
                                            processed_subquery, idx
                                        )
                                        if _lat2 is not None:
                                            new_inner_line = (
                                                " " * _lat2 + subline_stripped
                                            )
                                        else:
                                            new_inner_line = subline.rstrip("\n")
                                    else:
                                        # 嵌套层非关键字行：如果缩进明显低于当前层基准（递归层旧值），
                                        # 通过 new_lines 中最近 select 的缩进偏移来纠正
                                        if _cur_lead < _ci_kw and subline_stripped.startswith(","):
                                            _ref_new_sel = None
                                            _ref_old_sel = None
                                            for _bk in range(len(new_lines) - 1, -1, -1):
                                                _bks = new_lines[_bk].strip().lower()
                                                if not _bks or _bks.startswith("--") or _bks.startswith(","):
                                                    continue
                                                if _bks.startswith("select"):
                                                    _ref_new_sel = len(new_lines[_bk]) - len(new_lines[_bk].lstrip())
                                                    break
                                                break
                                            if _ref_new_sel is not None:
                                                for _bk2 in range(idx - 1, -1, -1):
                                                    _bk2s = processed_subquery[_bk2].strip().lower()
                                                    if not _bk2s or _bk2s.startswith("--") or _bk2s.startswith(","):
                                                        continue
                                                    if _bk2s.startswith("select"):
                                                        _ref_old_sel = len(processed_subquery[_bk2]) - len(processed_subquery[_bk2].lstrip())
                                                        break
                                                    break
                                            if _ref_new_sel is not None and _ref_old_sel is not None and _ref_new_sel > _ref_old_sel:
                                                _shift = _ref_new_sel - _ref_old_sel
                                                new_inner_line = " " * (_cur_lead + _shift) + subline_stripped
                                            else:
                                                new_inner_line = subline.rstrip("\n")
                                        else:
                                            new_inner_line = subline.rstrip("\n")

                                if has_newline:
                                    new_inner_line += '\n'
                                new_lines.append(new_inner_line)
                                # 行内括号可能改变深度（如 `) as end_time`），追踪修正
                                _inline_delta = _paren_delta_ignore_strings_sq(subline)
                                if _inline_delta != 0:
                                    bracket_depth += _inline_delta
                                    if _inline_delta > 0:
                                        _cur_ind = len(new_inner_line.rstrip("\n")) - len(new_inner_line.rstrip("\n").lstrip())
                                        for _ in range(_inline_delta):
                                            paren_col_stack.append(_cur_ind)
                                    elif _inline_delta < 0:
                                        for _ in range(-_inline_delta):
                                            if paren_col_stack:
                                                paren_col_stack.pop()
                            else:
                                has_nl2 = subline.endswith("\n")
                                if subline_stripped.startswith("--"):
                                    _ci2 = (
                                        paren_col_stack[-1] + SUBQUERY_INDENT
                                        if paren_col_stack
                                        else target_indent
                                        + max(0, bracket_depth - 1) * SUBQUERY_INDENT
                                    )
                                    _nl2 = " " * _ci2 + subline_stripped
                                    if has_nl2 and not _nl2.endswith("\n"):
                                        _nl2 += "\n"
                                    elif not has_nl2 and _nl2.endswith("\n"):
                                        _nl2 = _nl2.rstrip("\n")
                                    new_lines.append(_nl2)
                                else:
                                    new_lines.append(subline)
                                # 注释/空行也可能含括号（罕见），统一追踪
                                _inline_delta2 = _paren_delta_ignore_strings_sq(subline)
                                if _inline_delta2 != 0:
                                    bracket_depth += _inline_delta2
                                    if _inline_delta2 > 0:
                                        for _ in range(_inline_delta2):
                                            paren_col_stack.append(target_indent)
                                    elif _inline_delta2 < 0:
                                        for _ in range(-_inline_delta2):
                                            if paren_col_stack:
                                                paren_col_stack.pop()

                    # 最后添加右括号
                    if closing_bracket_line:
                        bracket_part = closing_bracket_line.strip()
                        has_newline = closing_bracket_line.endswith('\n')
                        new_bracket_line = ' ' * base_indent + bracket_part
                        if has_newline:
                            new_bracket_line += '\n'
                        new_lines.append(new_bracket_line)
                else:
                    new_lines.append(next_line)
                    i += 1
        else:
            new_lines.append(line)
            i += 1

    return new_lines


def merge_aggregate_open_paren_case_when_same_line(lines: List[str]) -> List[str]:
    """若一行以 ``max(`` / ``min(`` / ``sum(`` 等聚合函数末位 ``(`` 结尾，且下一行以 ``case when`` 开头，则并入本行。

    满足「计算函数与首参数同一行」的规范；须在 ``merge_case_when`` 之前执行。
    """
    if not lines:
        return lines
    out: List[str] = []
    agg_tail = re.compile(
        r"^(?P<head>.+)\b(?P<fn>max|min|sum|avg|count)\s*\(\s*$",
        re.IGNORECASE,
    )
    i = 0
    while i < len(lines):
        line = lines[i]
        raw = line.rstrip("\n")
        m = agg_tail.match(raw)
        if m and i + 1 < len(lines):
            nxt = lines[i + 1]
            nst = nxt.strip()
            if re.match(r"^case\s+when\b", nst, re.IGNORECASE):
                body = nxt.lstrip()
                merged = raw + body
                if line.endswith("\n") or nxt.endswith("\n"):
                    merged += "\n"
                out.append(merged)
                i += 2
                continue
        out.append(line)
        i += 1
    return out


def merge_case_when(lines: List[str]) -> List[str]:
    """合并 CASE WHEN 行结构（拆/并换行），为 ``align_case_when_columns`` 提供可扫的多行形态。

    目标与模块文档 **【CASE WHEN 排版规范】** 一致：首条 ``when`` 可与 ``case`` 同行；后续 ``when``/``else``/``end`` 独立成行；
    ``end`` 与对应层 ``case`` 左对齐（由后续对齐步骤落实列号）。不改变条件与返回值，仅调整换行与空白。

    示例转换：
        case
            when condition1 then value1
            when condition2 then value2
        end
    转换为：
        case when condition1 then value1
             when condition2 then value2
        end
    """
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 检测 CASE 关键字（两种情况）
        # 情况1: case 单独一行
        case_match = re.match(r'^(\s*)(.*?)\s*case\s*$', line, re.IGNORECASE)
        # 情况2: case when 已在同一行
        case_when_match = re.match(r'^(\s*)(.*?)\s*case\s+when\s+(.*)$', line, re.IGNORECASE)

        if case_match:
            prefix_indent = len(case_match.group(1))
            prefix_text = case_match.group(2)  # case 前的内容（如逗号）
            # 直接在原行中定位case关键字的实际位置
            case_pos = re.search(r'\bcase\b', line, re.IGNORECASE)
            case_indent = case_pos.start() if case_pos else (prefix_indent + len(prefix_text))

            # 检查下一行是否是 WHEN
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                when_match = re.match(r'^\s*when\s+(.*)$', next_line, re.IGNORECASE)

                if when_match:
                    # 第一个 WHEN 合并到 CASE 同行
                    when_content = when_match.group(1).rstrip('\n')
                    has_newline = line.endswith('\n')
                    # 使用rstrip()去掉case后的所有空白字符（包括空格和换行符）
                    merged_line = line.rstrip() + ' when ' + when_content
                    if has_newline:
                        merged_line += '\n'
                    new_lines.append(merged_line)

                    # 第一个 WHEN 的位置（用于后续 WHEN 对齐）
                    first_when_col = case_indent + len('case ')

                    i += 2  # 跳过 CASE 和第一个 WHEN 行

                    # 处理后续行（WHEN/ELSE/END）
                    while i < len(lines):
                        curr_line = lines[i]
                        curr_stripped = curr_line.strip()

                        # 后续 WHEN：与第一个 WHEN 对齐
                        if re.match(r'^when\s+', curr_stripped, re.IGNORECASE):
                            has_newline = curr_line.endswith('\n')
                            new_when_line = ' ' * first_when_col + curr_stripped
                            if has_newline:
                                new_when_line += '\n'
                            new_lines.append(new_when_line)
                            i += 1
                        # ELSE：与 WHEN 对齐，且ELSE和值在同一行，END单独换行
                        elif re.match(r'^else\s+', curr_stripped, re.IGNORECASE):
                            # 检查ELSE后是否有END（例如：else '其他' end）
                            else_match = re.match(r'^else\s+(.*?)\s+end\b(.*)$', curr_stripped, re.IGNORECASE)
                            if else_match:
                                # ELSE和值在一行，END单独换行
                                else_value = else_match.group(1)
                                after_end = else_match.group(2).strip()

                                has_newline = curr_line.endswith('\n')
                                new_else_line = ' ' * first_when_col + 'else ' + else_value
                                if has_newline:
                                    new_else_line += '\n'
                                new_lines.append(new_else_line)

                                # END单独一行，与CASE对齐
                                new_end_line = ' ' * case_indent + 'end'
                                if after_end:
                                    new_end_line += ' ' + after_end
                                if has_newline:
                                    new_end_line += '\n'
                                new_lines.append(new_end_line)
                                i += 1
                                break  # END 后退出 CASE WHEN 块
                            else:
                                # ELSE单独一行（没有END）
                                has_newline = curr_line.endswith('\n')
                                new_else_line = ' ' * first_when_col + curr_stripped
                                if has_newline:
                                    new_else_line += '\n'
                                new_lines.append(new_else_line)
                                i += 1
                        # END：与 CASE 首字母对齐
                        elif re.match(r'^end\b', curr_stripped, re.IGNORECASE):
                            # 检查 end 后是否有 as 别名
                            end_match = re.match(r'^(end)(\s+.*)$', curr_stripped, re.IGNORECASE)
                            if end_match:
                                end_keyword = end_match.group(1)
                                after_end = end_match.group(2)
                                has_newline = curr_line.endswith('\n')
                                new_end_line = ' ' * case_indent + end_keyword + after_end
                                if has_newline:
                                    new_end_line += '\n'
                                new_lines.append(new_end_line)
                            else:
                                has_newline = curr_line.endswith('\n')
                                new_end_line = ' ' * case_indent + curr_stripped
                                if has_newline:
                                    new_end_line += '\n'
                                new_lines.append(new_end_line)
                            i += 1
                            break  # END 后退出 CASE WHEN 块
                        else:
                            # 其他行（如多行表达式），保持原样
                            new_lines.append(curr_line)
                            i += 1
                    continue
                else:
                    # 下一行不是 WHEN，保持原样
                    new_lines.append(line)
                    i += 1
            else:
                new_lines.append(line)
                i += 1
        elif case_when_match:
            # ``max(`` 等上一行以 ``(`` 结尾，或本行 ``case when`` 前有 ``max(`` 等同行开括号时，为表达式内联，勿吞 ``else``/``end``
            _pfx2 = case_when_match.group(2)
            if (i > 0 and lines[i - 1].rstrip().endswith("(")) or _pfx2.rstrip().endswith(
                "("
            ):
                new_lines.append(line)
                i += 1
                continue
            # 情况2: case when 已在同一行（原文件或已格式化过的）
            # 需要处理后续的 WHEN/ELSE/END 行，确保 END 与 case 对齐
            prefix_indent = len(case_when_match.group(1))
            prefix_text = case_when_match.group(2)
            first_when_content = case_when_match.group(3)

            # 定位 case 的实际位置
            case_pos = re.search(r'\bcase\b', line, re.IGNORECASE)
            case_indent = case_pos.start() if case_pos else (prefix_indent + len(prefix_text))

            # 第一个 WHEN 的位置
            first_when_col = case_indent + len('case ')

            # 保留当前行（case when 已在同一行）
            new_lines.append(line)
            i += 1

            # 处理后续行（WHEN/ELSE/END）
            while i < len(lines):
                curr_line = lines[i]
                curr_stripped = curr_line.strip()

                # 后续 WHEN：与第一个 WHEN 对齐
                if re.match(r'^when\s+', curr_stripped, re.IGNORECASE):
                    has_newline = curr_line.endswith('\n')
                    new_when_line = ' ' * first_when_col + curr_stripped
                    if has_newline:
                        new_when_line += '\n'
                    new_lines.append(new_when_line)
                    i += 1
                # ELSE：与 WHEN 对齐
                elif re.match(r'^else\s+', curr_stripped, re.IGNORECASE):
                    # 检查ELSE后是否有END
                    else_match = re.match(r'^else\s+(.*?)\s+end\b(.*)$', curr_stripped, re.IGNORECASE)
                    if else_match:
                        # ELSE和值在一行，END单独换行
                        else_value = else_match.group(1)
                        after_end = else_match.group(2).strip()

                        has_newline = curr_line.endswith('\n')
                        new_else_line = ' ' * first_when_col + 'else ' + else_value
                        if has_newline:
                            new_else_line += '\n'
                        new_lines.append(new_else_line)

                        # END单独一行，与CASE对齐
                        new_end_line = ' ' * case_indent + 'end'
                        if after_end:
                            new_end_line += ' ' + after_end
                        if has_newline:
                            new_end_line += '\n'
                        new_lines.append(new_end_line)
                        i += 1
                        break
                    else:
                        # ELSE单独一行
                        has_newline = curr_line.endswith('\n')
                        new_else_line = ' ' * first_when_col + curr_stripped
                        if has_newline:
                            new_else_line += '\n'
                        new_lines.append(new_else_line)
                        i += 1
                # END：与 CASE 首字母对齐
                elif re.match(r'^end\b', curr_stripped, re.IGNORECASE):
                    end_match = re.match(r'^(end)(\s+.*)$', curr_stripped, re.IGNORECASE)
                    if end_match:
                        end_keyword = end_match.group(1)
                        after_end = end_match.group(2)
                        has_newline = curr_line.endswith('\n')
                        new_end_line = ' ' * case_indent + end_keyword + after_end
                        if has_newline:
                            new_end_line += '\n'
                        new_lines.append(new_end_line)
                    else:
                        has_newline = curr_line.endswith('\n')
                        new_end_line = ' ' * case_indent + curr_stripped
                        if has_newline:
                            new_end_line += '\n'
                        new_lines.append(new_end_line)
                    i += 1
                    break
                else:
                    # 其他行（如多行表达式），保持原样
                    new_lines.append(curr_line)
                    i += 1
        else:
            new_lines.append(line)
            i += 1

    return new_lines


def _col_first_nonspace_after_first_when_on_line(line: str) -> Optional[int]:
    """行内**首个** ``when`` 谓词：``when`` 后第一个非空白字符的 0-based 列号。"""
    raw = line.split("\n", 1)[0]
    m = re.search(r"(?i)\bwhen\s+", raw)
    if not m:
        return None
    pos = m.end()
    while pos < len(raw) and raw[pos] in " \t":
        pos += 1
    return pos if pos < len(raw) else None


def _continuation_col_after_when_above(lines: List[str], idx: int) -> Optional[int]:
    """向上找最近含 ``when`` 的代码行，返回该行「首个 when 后首非空」列（CASE 内 ``and``/``or`` 续行）。

    跳过独占行的 ``then …``，否则会误把 ``then`` 当前行当成含 ``when`` 的锚点，或错跳到更深层
    ``case when`` 行上取 ``when`` 后首非空列，导致 ``then``/``else`` 与块首 ``when`` 多缩进。
    """
    j = idx - 1
    while j >= 0:
        prev = lines[j]
        st = prev.strip()
        if not st or st.startswith("--"):
            j -= 1
            continue
        if re.match(r"(?i)^then\b", st):
            j -= 1
            continue
        c = _col_first_nonspace_after_first_when_on_line(prev)
        if c is not None:
            return c
        if re.match(
            r"^(select|from|where|group\s+by|having|order\s+by|limit|union)\b",
            st,
            re.I,
        ):
            break
        j -= 1
    return None


def _col_child_case_after_parent_then(prev_line: str, cur_line: str) -> Optional[int]:
    """回退列：父行以 ``then`` 结尾且未走 ``when_col`` 分支时，子 ``case`` 与父行 ``then`` 后首非空同列；无同行内容则与子行 ``case`` 列一致。优先规则见文件头 CASE 第 3 条（``when_col``）。"""
    pre = prev_line.split("\n", 1)[0].rstrip("\n")
    cur0 = cur_line.split("\n", 1)[0]
    m_case = re.search(r"(?i)\bcase\b", cur0)
    if not m_case:
        return None
    case_rel = m_case.start()
    m_then = re.search(r"(?i)\bthen\b", pre)
    if not m_then:
        return None
    pos = m_then.end()
    while pos < len(pre) and pre[pos] in " \t":
        pos += 1
    if pos < len(pre):
        return pos
    row0 = cur_line.split("\n", 1)[0]
    return len(row0) - len(row0.lstrip(" \t")) + case_rel


def _col_child_case_after_parent_else(prev_line: str, cur_line: str) -> Optional[int]:
    """规范第4条：父行以 ``else`` 结尾时，子 ``case`` 换行后与父行首个 ``else`` 后首非空同列；否则与子行 ``case`` 关键字列一致。"""
    pre = prev_line.split("\n", 1)[0].rstrip("\n")
    cur0 = cur_line.split("\n", 1)[0]
    m_case = re.search(r"(?i)\bcase\b", cur0)
    if not m_case:
        return None
    case_rel = m_case.start()
    m_else = re.search(r"(?i)\belse\b", pre)
    if not m_else:
        return None
    pos = m_else.end()
    while pos < len(pre) and pre[pos] in " \t":
        pos += 1
    if pos < len(pre):
        return pos
    row0 = cur_line.split("\n", 1)[0]
    return len(row0) - len(row0.lstrip(" \t")) + case_rel


def _col_first_nonblank_after_case_keyword(line: str) -> Optional[int]:
    """``case`` 后并非 ``when`` 时（如 ``case grouping_id(…``、``case expr``），返回 ``case`` 之后第一个非空字符的列号。

    换行 ``when``/``else`` 与之左对齐；无后继非空则 ``None``。
    """
    lb = line.split("\n", 1)[0].rstrip("\n")
    m = re.search(r"(?i)\bcase\b", lb)
    if not m:
        return None
    pos = m.end()
    while pos < len(lb) and lb[pos] in " \t":
        pos += 1
    return pos if pos < len(lb) else None


def _grouping_sets_comma_continuation_and_close_cols(first_line: str) -> Tuple[Optional[int], Optional[int]]:
    """首组与 ``grouping sets((…`` 同行时：``(逗号续行左填充列, 闭行 ) 与 grouping sets( 的左括号列)``。

    逗号续行：``,`` 后按「逗号 + 1 空格 + ``(``」共 3 个字符后，首组**首个非空**与续行**首个非空**同列。
    """
    raw = first_line.split("\n", 1)[0].rstrip("\n")
    open_m = re.search(r"(?i)grouping\s+sets\s*\(", raw)
    if not open_m:
        return None, None
    pos = open_m.end()
    while pos < len(raw) and raw[pos] in " \t(":
        pos += 1
    if pos >= len(raw):
        return None, None
    anchor = pos
    lead = max(0, anchor - len(", ("))
    close_col = open_m.end() - 1
    return lead, close_col


def _union_chain_anchor_select_index(lines: List[str], union_idx: int) -> Optional[int]:
    """``union``/``union all`` 行向上找本链第一节 ``select`` 行下标。

    与 ``_nearest_select_indent_before`` 相同的圆括号深度（反向扫行内字符），
    使 ``group by … union``、``) as tmp`` 等不会误截断，从而命中正确层级的 ``select``。
    """
    depth = 0
    j = union_idx - 1
    steps = 0
    while j >= 0 and steps < 500:
        steps += 1
        raw = lines[j].split("\n", 1)[0]
        st = raw.strip()
        if not st or st.startswith("--"):
            j -= 1
            continue
        if depth == 0 and re.match(r"^select\b", st, re.I):
            return j
        if depth == 0 and re.match(r"^union\b", st, re.I):
            return None
        for ch in reversed(raw):
            if ch == ")":
                depth += 1
            elif ch == "(":
                if depth > 0:
                    depth -= 1
        if depth < 0:
            depth = 0
        j -= 1
    return None


def _wrap_paren_indent_union_outer_select(lines: List[str], open_paren_line: int, anc: int) -> Optional[int]:
    """独占 ``(`` 上一非空行为 ``from``、``anc`` 为 ``(`` 后首部 ``select``（中间仅空/注释）时：外链 ``(``/``) as`` 与外层 ``select`` 同列 = 内层 ``select`` 缩进 ``- SUBQUERY_INDENT``。"""
    if open_paren_line < 0 or anc <= open_paren_line:
        return None
    j = open_paren_line - 1
    while j >= 0:
        ps = lines[j].split("\n", 1)[0].strip()
        if not ps or ps.startswith("--"):
            j -= 1
            continue
        if not re.match(r"^(?:from|(?:(?:left|right|inner|full)(?:\s+outer)?\s+)?(?:cross\s+)?join)\b", ps, re.I):
            return None
        break
    fir = open_paren_line + 1
    while fir < len(lines) and fir <= anc:
        st = lines[fir].split("\n", 1)[0].strip()
        if not st or st.startswith("--"):
            fir += 1
            continue
        break
    if fir != anc:
        return None
    inner_ind = len(lines[anc]) - len(lines[anc].lstrip())
    return max(0, inner_ind - SUBQUERY_INDENT)


def _paren_delta_ignore_strings_sq(line: str) -> int:
    """单行内圆括号深度变化（忽略单引号字符串内括号）。"""
    d = 0
    mode = "code"
    i = 0
    s = line.split("\n", 1)[0]
    n = len(s)
    while i < n:
        ch = s[i]
        if mode == "code":
            if ch == "'":
                mode = "sq"
                i += 1
                continue
            if ch == "(":
                d += 1
            elif ch == ")":
                d -= 1
            i += 1
            continue
        if ch == "'" and i + 1 < n and s[i + 1] == "'":
            i += 2
            continue
        if ch == "'":
            mode = "code"
        i += 1
    return d


def _find_union_subquery_close_as(lines: List[str], open_paren_line: int, max_scan: int = 220) -> Optional[int]:
    """自独占 ``(`` 行 ``open_paren_line`` 起累计括号深度，深度首次回到 0 且为 ``) as`` 时返回该行（避免命中内层 ``) as tmp``）。"""
    if open_paren_line < 0 or open_paren_line >= len(lines):
        return None
    depth = 0
    lim = min(len(lines), open_paren_line + max_scan)
    for k in range(open_paren_line, lim):
        raw = lines[k].split("\n", 1)[0]
        depth += _paren_delta_ignore_strings_sq(raw)
        if depth == 0 and k > open_paren_line:
            st = raw.strip()
            if re.match(r"^\)\s+as\b", st, re.I):
                return k
        if depth < 0:
            depth = 0
    return None


def align_grouping_sets_layout(lines: List[str]) -> List[str]:
    """``group by grouping sets``：

    * 三行块：首组已在 ``sets((…`` 同行；续行 ``, …`` 逗号后首非空与首组首非空同列；末行 ``)`` 与 ``grouping sets(`` 左括号同列。
    * 四行常见块：首组并到 ``sets (`` 后；``, (`` 与首组 ``(`` 同列；``)`` 与 ``grouping sets (`` 的配对左括号同列。

    仅改写空白；不增删标识符、括号、逗号等语义字符。
    """
    if not lines:
        return lines
    out = list(lines)
    n = len(out)
    i = 0
    while i <= n - 3:
        raw0 = out[i].split("\n", 1)[0].rstrip("\n")
        mfr = re.match(
            r"^(\s*group\s+by\s+grouping\s+sets)(\(\(([^)]+)\))\s*$",
            raw0,
            re.I,
        )
        if not mfr:
            i += 1
            continue
        raw1 = out[i + 1].split("\n", 1)[0].rstrip("\n")
        raw2 = out[i + 2].split("\n", 1)[0].rstrip("\n")
        st1 = raw1.lstrip()
        if not st1.startswith(","):
            i += 1
            continue
        st2 = raw2.strip()
        if not re.match(r"^\)+\s*$", st2):
            i += 1
            continue
        lead, close_col = _grouping_sets_comma_continuation_and_close_cols(raw0)
        if lead is None or close_col is None:
            i += 1
            continue
        nl1 = out[i + 1].endswith("\n")
        nl2 = out[i + 2].endswith("\n")
        out[i + 1] = " " * lead + st1 + ("\n" if nl1 else "")
        out[i + 2] = " " * close_col + st2 + ("\n" if nl2 else "")
        n = len(out)
        i += 3

    i = 0
    while i <= n - 4:
        raw0 = out[i].split("\n", 1)[0].rstrip("\n")
        m0 = re.match(r"^(\s*group\s+by\s+grouping\s+sets)\s*\(\s*$", raw0, re.I)
        if not m0:
            i += 1
            continue
        raw1 = out[i + 1].split("\n", 1)[0].strip()
        if not raw1.startswith("("):
            i += 1
            continue
        raw2 = out[i + 2].split("\n", 1)[0].strip()
        if not raw2.startswith(","):
            i += 1
            continue
        raw3 = out[i + 3].split("\n", 1)[0].strip()
        if not re.match(r"^\)+\s*$", raw3):
            i += 1
            continue

        merged = m0.group(1) + "(" + raw1
        gm = re.search(r"(?i)grouping\s+sets\s*\(", merged)
        if not gm:
            i += 1
            continue
        outer_open_col = gm.end() - 1
        p_tuple = merged.find("(", outer_open_col + 1)
        if p_tuple < 0:
            i += 1
            continue

        pad2 = max(0, p_tuple - 2)
        line2_new = " " * pad2 + raw2
        line3_new = " " * outer_open_col + raw3

        nl0 = out[i].endswith("\n")
        nl2 = out[i + 2].endswith("\n")
        nl3 = out[i + 3].endswith("\n")
        blk = [
            merged + ("\n" if nl0 else ""),
            line2_new + ("\n" if nl2 else ""),
            line3_new + ("\n" if nl3 else ""),
        ]
        out[i : i + 4] = blk
        n = len(out)
        i += len(blk)
    return out


def align_union_branch_keyword_column(lines: List[str]) -> List[str]:
    """``(`` … ``select`` … ``from`` … ``union all`` … 链上：内层 ``select``/``from``/``union`` 与首节 ``select`` 同列；

    外链独占 ``(`` 与收尾 ``) as``：若其紧邻上一非空行为 ``from``，则与**该 from 配对的**外层 ``select`` 同列（见 ``_wrap_paren_indent_partner_select_above_from``）。
    """
    if not lines:
        return lines
    out = list(lines)
    n = len(out)
    covered: Set[int] = set()
    i = 0
    while i < n:
        if i in covered:
            i += 1
            continue
        st = out[i].split("\n", 1)[0].strip()
        if not st or st.startswith("--"):
            i += 1
            continue
        if not (
            re.match(r"(?i)^union\s+all\s*$", st)
            or re.match(r"(?i)^union\s*$", st)
        ):
            i += 1
            continue
        anc = _union_chain_anchor_select_index(out, i)
        if anc is None:
            i += 1
            continue
        start = anc
        open_paren_line = start
        while start > 0:
            ps = out[start - 1].split("\n", 1)[0].strip()
            if not ps or ps.startswith("--"):
                start -= 1
                continue
            if re.match(r"^\($", ps):
                open_paren_line = start - 1
                start -= 1
                continue
            break
        ost0 = out[open_paren_line].split("\n", 1)[0].strip()
        if ost0 == "(":
            end_k = _find_union_subquery_close_as(out, open_paren_line, 220)
        else:
            end_k = None
        if end_k is None:
            i += 1
            continue
        tgt = len(out[anc]) - len(out[anc].lstrip())
        wrap_tgt = _wrap_paren_indent_union_outer_select(out, open_paren_line, anc)
        # 勿把 ``(`` 之上的外层 ``from`` 纳入（``start`` 可能已回退到 from 行）
        rw0 = min(anc, open_paren_line)
        # 仅改写「最外层 ``(`` … ``) as``」深度为 1 的 ``select``/``from``/``union``；跳过
        # ``from (`` 内再嵌套的子查询（否则会把已 ``(`` 列 +6 的内层 ``select``/``from`` 拉回与首节 ``select`` 同列）。
        run = 0
        for k in range(rw0, end_k + 1):
            if k in covered:
                continue
            raw = out[k]
            st0 = raw.split("\n", 1)[0].strip()
            if not st0 or st0.startswith("--"):
                run += _paren_delta_ignore_strings_sq(raw)
                continue
            is_kw_chain = re.match(
                r"^(select|from|union|(?:(?:left|right|inner|full)(?:\s+outer)?\s+)?(?:cross\s+)?join|where|group\s+by|having|order\s+by)\b",
                st0, re.I,
            )
            is_open = st0 == "("
            is_close_as = bool(re.match(r"^\)\s+as\b", st0, re.I))
            if is_kw_chain or is_open or is_close_as:
                depth_before = run
                do_rewrite = False
                if is_open:
                    if k == open_paren_line:
                        do_rewrite = True
                elif is_close_as:
                    if k == end_k:
                        do_rewrite = True
                elif is_kw_chain and depth_before == 1:
                    do_rewrite = True
                if do_rewrite:
                    has_nl = raw.endswith("\n")
                    use_tgt = tgt
                    if wrap_tgt is not None:
                        if k == open_paren_line and is_open:
                            use_tgt = wrap_tgt
                        elif k == end_k and is_close_as:
                            use_tgt = wrap_tgt
                    out[k] = " " * use_tgt + st0 + ("\n" if has_nl else "")
            run += _paren_delta_ignore_strings_sq(raw)
        for t in range(rw0, end_k + 1):
            covered.add(t)
        i += 1
    # UNION 链改写 ``select``/``from`` 行首列后须重算句首逗号列；因果收进本函数末尾（替代预处理中紧随其后的 ``align_field_names``）。
    return align_field_names(out)


def align_case_when_columns(lines: List[str]) -> List[str]:
    """按模块文档 **【CASE WHEN 排版规范】** 对多行 CASE 做列收敛（须已配合 ``merge_case_when`` 等前置步骤）。

    落实：同层 ``case``/``end``；同层 ``when``/``else``（栈顶 ``when_col``）；``then``/``else`` 独占行尾后换行且下一行直接 ``case when`` 时，子 ``case`` 与栈顶 ``when_col`` 同列（与父块首行第一个 ``when`` 的 ``W`` 一致）；**不要求**为对齐强行把同行的 ``then case when`` 拆开；其它形态仍可用
    ``_col_child_case_after_parent_then`` / ``_col_child_case_after_parent_else`` 作回退；单行判定 ``_case_when_fully_closed_on_line``；
    多行栈配对 ``end``；``case`` 后非 ``when`` 分支；CASE 内 ``and``/``or`` 续行。
    """
    new_lines: List[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped or stripped.startswith('--'):
            new_lines.append(line)
            i += 1
            continue

        lb0 = line.split("\n", 1)[0]
        case_m_gid = re.search(r"(?i)\bcase\b", line)
        if case_m_gid and not re.search(r"(?i)\bcase\s+when\s+", lb0):
            # ``case`` 后不是 ``when``：换行 ``when``/``else`` 与 ``case`` 后首非空同列（含 ``grouping_id`` 等，非单独特判）
            gid_m = re.search(r"(?i)\bcase\s+grouping_id\s*\(", lb0)
            if gid_m and ")" not in lb0[gid_m.end() :]:
                new_lines.append(line)
                i += 1
                continue
            case_col_gid = case_m_gid.start()
            c_after = _col_first_nonblank_after_case_keyword(lb0)
            when_col_gid = (
                c_after if c_after is not None else case_col_gid + SUBQUERY_INDENT
            )
            new_lines.append(line)
            i += 1
            while i < n:
                raw = lines[i]
                s = raw.strip()
                if not s:
                    new_lines.append(raw)
                    i += 1
                    continue
                if s.startswith("--"):
                    new_lines.append(raw)
                    i += 1
                    continue
                if re.match(r"^end\b", s, re.I):
                    has_nl = raw.endswith("\n")
                    new_l = " " * case_col_gid + s
                    if has_nl and not new_l.endswith("\n"):
                        new_l += "\n"
                    elif not has_nl and new_l.endswith("\n"):
                        new_l = new_l.rstrip("\n")
                    new_lines.append(new_l)
                    i += 1
                    break
                if (
                    re.match(r"^when\s+", s, re.I)
                    or re.match(r"^else\b", s, re.I)
                    or re.match(r"^(and|or)\b", s, re.I)
                ):
                    has_nl = raw.endswith("\n")
                    new_l = " " * when_col_gid + s
                    if has_nl and not new_l.endswith("\n"):
                        new_l += "\n"
                    elif not has_nl and new_l.endswith("\n"):
                        new_l = new_l.rstrip("\n")
                    new_lines.append(new_l)
                    i += 1
                else:
                    new_lines.append(raw)
                    i += 1
            continue

        if not re.search(r'(?i)\bcase\s+when\s+', line):
            new_lines.append(line)
            i += 1
            continue

        case_m = re.search(r'(?i)\bcase\b', line)
        if not case_m:
            new_lines.append(line)
            i += 1
            continue

        when_head = re.search(r'(?i)\bcase\s+(when\s+)', line)
        if not when_head:
            new_lines.append(line)
            i += 1
            continue

        # 规则 9–12：仅当本行自外层 ``case`` 起 ``case when``/``end`` 配对深度归零，才视为单行 CASE，跳过续行扫描。
        if _case_when_fully_closed_on_line(lb0, case_m.start()):
            new_lines.append(line)
            i += 1
            continue

        case_col = case_m.start()
        when_col = when_head.start(1)
        _wcond = _col_first_nonspace_after_first_when_on_line(line)
        when_cond_col = _wcond if _wcond is not None else when_col

        new_lines.append(line)
        i += 1
        # 规则 6–8、13–15：``end`` 与栈顶 ``case`` 左对齐；``when``/``else`` 与栈顶同层 ``when`` 列对齐。
        # 第三元素 ``when_cond_col``：``when`` 后首个非空字符列，用于多行 WHEN 条件内 and/or/then 续行对齐。
        stack: List[Tuple[int, int, int]] = [(case_col, when_col, when_cond_col)]

        while i < n:
            raw = lines[i]
            s = raw.strip()
            if not s:
                new_lines.append(raw)
                i += 1
                continue
            if s.startswith('--'):
                new_lines.append(raw)
                i += 1
                continue

            if re.match(r'^end\b', s, re.IGNORECASE):
                has_nl = raw.endswith('\n')
                if not stack:
                    new_lines.append(raw)
                    i += 1
                    continue
                ec = stack[-1][0]
                new_l = _replace_leading_indent_first_line(raw, ec)
                if has_nl and not new_l.endswith('\n'):
                    new_l += '\n'
                elif not has_nl and new_l.endswith('\n'):
                    new_l = new_l.rstrip('\n')
                new_lines.append(new_l)
                stack.pop()
                i += 1
                if not stack:
                    break
                continue

            if re.match(r"(?i)^then\b", s):
                has_nl = raw.endswith("\n")
                # 多行 WHEN 条件（when 与 then 之间存在 and/or 续行）时，then 对齐到 when 后首字符列；
                # 单行条件时仍对齐到 when_col。
                _multiline_when = False
                for _j in range(i - 1, -1, -1):
                    _ps = lines[_j].strip()
                    if not _ps or _ps.startswith('--'):
                        continue
                    if re.match(r"^(and|or)\b", _ps, re.I):
                        _multiline_when = True
                        break
                    if re.search(r"(?i)\bwhen\b", _ps):
                        break
                wcol = stack[-1][2] if (_multiline_when and stack) else stack[-1][1]
                new_l = _replace_leading_indent_first_line(raw, wcol)
                if has_nl and not new_l.endswith("\n"):
                    new_l += "\n"
                elif not has_nl and new_l.endswith("\n"):
                    new_l = new_l.rstrip("\n")
                # 多行 CASE 中「then value end」同行时，拆为 then value + 独立 end（end 与 case 同列）
                _th_line0 = new_l.split("\n", 1)[0]
                _th_rest = re.sub(r'^.*?\bthen\b', '', _th_line0, count=1, flags=re.I)
                _net_end = len(re.findall(r'\bend\b', _th_rest, re.I)) - len(re.findall(r'\bcase\s+when\b', _th_rest, re.I))
                if _net_end > 0 and _multiline_when and stack:
                    _end_m = None
                    for _em in re.finditer(r'\bend\b', _th_line0, re.I):
                        _end_m = _em
                    if _end_m:
                        _before_end = _th_line0[:_end_m.start()].rstrip()
                        _after_end = _th_line0[_end_m.end():]
                        _end_line = " " * stack[-1][0] + "end" + _after_end
                        new_l_split = _before_end + ("\n" if has_nl else "")
                        new_lines.append(new_l_split)
                        new_lines.append(_end_line + ("\n" if has_nl else ""))
                        stack.pop()
                        _net_end -= 1
                        while _net_end > 0 and stack:
                            stack.pop()
                            _net_end -= 1
                    else:
                        new_lines.append(new_l)
                        while _net_end > 0 and stack:
                            stack.pop()
                            _net_end -= 1
                else:
                    new_lines.append(new_l)
                    while _net_end > 0 and stack:
                        stack.pop()
                        _net_end -= 1
                i += 1
                if not stack:
                    break
            elif re.match(r'^when\s+', s, re.IGNORECASE) or re.match(r'^else\b', s, re.IGNORECASE):
                has_nl = raw.endswith('\n')
                use_when_col = stack[-1][1]
                new_l = _replace_leading_indent_first_line(raw, use_when_col)
                if has_nl and not new_l.endswith('\n'):
                    new_l += '\n'
                elif not has_nl and new_l.endswith('\n'):
                    new_l = new_l.rstrip('\n')
                new_lines.append(new_l)
                lbw = new_lines[-1].split("\n", 1)[0]
                if (
                    re.match(r"(?i)^else\b", s)
                    and re.search(r"(?i)\bcase\s+when\s+", lbw)
                    and not re.search(r"(?i)\bend\b", lbw)
                ):
                    kw_in = _case_when_keyword_columns(lbw)
                    if kw_in is not None and not _case_when_fully_closed_on_line(lbw, kw_in[0]):
                        _cc = _col_first_nonspace_after_first_when_on_line(lbw)
                        stack.append((kw_in[0], kw_in[1], _cc if _cc is not None else kw_in[1]))
                _we_net = len(re.findall(r'\bend\b', lbw, re.I)) - len(re.findall(r'\bcase\s+when\b', lbw, re.I))
                while _we_net > 0 and stack:
                    stack.pop()
                    _we_net -= 1
                i += 1
                if not stack:
                    break
            elif re.match(r"^(and|or)\b", s, re.IGNORECASE):
                # 若前一行以 and(/or( 打开了未闭合括号组，对齐到该行 and/or 后首非空字符
                cont = None
                for _j in range(len(new_lines) - 1, -1, -1):
                    _ps = new_lines[_j].strip()
                    if not _ps or _ps.startswith('--'):
                        continue
                    _paren_m = re.match(r"^(and|or)\s+\(", _ps, re.I)
                    if _paren_m:
                        _pline = new_lines[_j].split("\n", 1)[0]
                        _kw_m = re.search(r"(?i)\b(and|or)\s+", _pline)
                        if _kw_m:
                            _after = _kw_m.end()
                            while _after < len(_pline) and _pline[_after] in " \t":
                                _after += 1
                            if _after < len(_pline):
                                cont = _after
                    break
                if cont is None:
                    cont = _continuation_col_after_when_above(lines, i)
                if cont is None and stack:
                    cont = stack[-1][2]
                if cont is not None:
                    has_nl = raw.endswith("\n")
                    new_l = _replace_leading_indent_first_line(raw, cont)
                    if has_nl and not new_l.endswith("\n"):
                        new_l += "\n"
                    elif not has_nl and new_l.endswith("\n"):
                        new_l = new_l.rstrip("\n")
                    new_lines.append(new_l)
                else:
                    new_lines.append(raw)
                i += 1
            elif re.match(r"^case\b", s, re.I) and i > 0:
                prev_ln = lines[i - 1].split("\n", 1)[0].rstrip()
                pcol: Optional[int] = None
                # ``then``/``else`` 独占行尾后换行、下一行直接 ``case when``：子 ``case`` 与父级同层 ``when``/``else`` 起列（栈顶 ``when_col``），
                # 不追逐物理行中 ``then`` 后首非空（避免被 AS/子查询缩进拉至极右）。
                _sub_case_when = bool(re.search(r"(?i)^case\s+when\s+", s))
                if (
                    stack
                    and _sub_case_when
                    and (
                        re.search(r"(?i)\bthen\s*$", prev_ln)
                        or re.search(r"(?i)\belse\s*$", prev_ln)
                    )
                ):
                    pcol = stack[-1][1]
                elif re.search(r"(?i)\bthen\s*$", prev_ln):
                    pcol = _col_child_case_after_parent_then(lines[i - 1], raw)
                elif re.search(r"(?i)\belse\s*$", prev_ln):
                    pcol = _col_child_case_after_parent_else(lines[i - 1], raw)
                if pcol is not None:
                    has_nl = raw.endswith("\n")
                    new_l = _replace_leading_indent_first_line(raw, pcol)
                    if has_nl and not new_l.endswith("\n"):
                        new_l += "\n"
                    elif not has_nl and new_l.endswith("\n"):
                        new_l = new_l.rstrip("\n")
                    new_lines.append(new_l)
                    _nl0 = new_l.split("\n", 1)[0]
                    kw = _case_when_keyword_columns(_nl0)
                    if kw is not None and not _case_when_fully_closed_on_line(_nl0, kw[0]):
                        _cc2 = _col_first_nonspace_after_first_when_on_line(_nl0)
                        stack.append((kw[0], kw[1], _cc2 if _cc2 is not None else kw[1]))
                    i += 1
                    continue
                new_lines.append(raw)
                i += 1
            else:
                new_lines.append(raw)
                _line0 = raw.split("\n", 1)[0]
                _net_end = len(re.findall(r'\bend\b', _line0, re.I)) - len(re.findall(r'\bcase\b', _line0, re.I))
                while _net_end > 0 and stack:
                    stack.pop()
                    _net_end -= 1
                i += 1
                if not stack:
                    break

    return new_lines


def align_cross_line_parens(lines: List[str]) -> List[str]:
    """跨行圆括号对齐：闭括号 ``)`` 与对应开括号 ``(`` 同列。

    仅处理代码中的圆括号；忽略单引号/双引号/反引号字符串或标识符内的括号，以及 ``--`` 行注释、``/* */`` 块注释内的括号。
    仅当闭括号所在行在 ``)`` 之前全为空白时才调整缩进，避免破坏行内表达式。
    多组 ``)`` 同行时按列号从右向左依次应用，避免索引错位。
    """
    if not lines:
        return lines

    # 模式：code | line_comment | block_comment | sq | dq | bt
    mode = "code"
    stack: List[Tuple[int, int]] = []  # (line_idx, col)
    pairs: List[Tuple[int, int, int, int]] = []  # open_line, open_col, close_line, close_col

    n = len(lines)
    for li in range(n):
        line = lines[li]
        j = 0
        while j < len(line):
            ch = line[j]
            if ch == "\n":
                if mode == "line_comment":
                    mode = "code"
                j += 1
                continue

            if mode == "line_comment":
                j += 1
                continue

            if mode == "block_comment":
                if ch == "*" and j + 1 < len(line) and line[j + 1] == "/":
                    mode = "code"
                    j += 2
                else:
                    j += 1
                continue

            if mode == "sq":
                if ch == "'":
                    if j + 1 < len(line) and line[j + 1] == "'":
                        j += 2
                    else:
                        mode = "code"
                        j += 1
                else:
                    j += 1
                continue

            if mode == "dq":
                if ch == '"':
                    if j + 1 < len(line) and line[j + 1] == '"':
                        j += 2
                    else:
                        mode = "code"
                        j += 1
                else:
                    j += 1
                continue

            if mode == "bt":
                if ch == "`":
                    if j + 1 < len(line) and line[j + 1] == "`":
                        j += 2
                    else:
                        mode = "code"
                        j += 1
                else:
                    j += 1
                continue

            # mode == code
            if ch == "-" and j + 1 < len(line) and line[j + 1] == "-":
                mode = "line_comment"
                j += 2
                continue
            if ch == "/" and j + 1 < len(line) and line[j + 1] == "*":
                mode = "block_comment"
                j += 2
                continue
            if ch == "'":
                mode = "sq"
                j += 1
                continue
            if ch == '"':
                mode = "dq"
                j += 1
                continue
            if ch == "`":
                mode = "bt"
                j += 1
                continue
            if ch == "(":
                stack.append((li, j))
                j += 1
                continue
            if ch == ")":
                if stack:
                    ol, oc = stack.pop()
                    if ol != li:
                        pairs.append((ol, oc, li, j))
                j += 1
                continue

            j += 1

        # 行末无换行时，-- 行注释不会经换行符复位，避免泄漏到下一物理行
        if mode == "line_comment":
            mode = "code"

    if not pairs:
        return lines

    pairs.sort(key=lambda t: (-t[2], -t[3]))
    out = list(lines)
    for ol, oc, cl, cc in pairs:
        if cl >= len(out):
            continue
        raw = out[cl]
        if cc >= len(raw) or raw[cc] != ")":
            continue
        prefix = raw[:cc]
        if prefix and not prefix.isspace():
            continue
        has_nl = raw.endswith("\n")
        body = raw.rstrip("\n")
        if cc >= len(body) or body[cc] != ")":
            continue
        new_body = " " * oc + ")" + body[cc + 1 :]
        out[cl] = new_body + ("\n" if has_nl else "")

    return out


def merge_from_table(lines: List[str]) -> List[str]:
    """合并 FROM 后的表名到同一行

    规范：FROM 后的表名紧跟同行（不换行）

    示例转换：
        from
           table_name as t
    转换为：
        from table_name as t
    """
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 检测 FROM 关键字（单独一行）
        if re.match(r'^\s*from\s*$', line, re.IGNORECASE):
            from_indent = len(line) - len(line.lstrip())
            from_line = line.rstrip('\n')

            # 检查下一行是否是表名
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                next_stripped = next_line.strip()

                # 下一行不应该是括号（子查询）或SQL关键字
                if next_stripped and not next_stripped.startswith('(') and \
                   not re.match(r'^\s*(select|where|group\s+by|having|order\s+by|limit|union|left\s+join|right\s+join|inner\s+join|cross\s+join|full\s+outer\s+join|full\s+join|join)\b', next_line, re.IGNORECASE):
                    # 合并表名到 FROM 行
                    has_newline = next_line.endswith('\n')
                    merged_line = from_line + ' ' + next_stripped
                    if has_newline:
                        merged_line += '\n'
                    new_lines.append(merged_line)
                    i += 2  # 跳过 FROM 和表名行
                    continue
                else:
                    # 下一行是子查询或其他，保持原样
                    new_lines.append(line)
                    i += 1
            else:
                new_lines.append(line)
                i += 1
        else:
            new_lines.append(line)
            i += 1

    return new_lines


# JOIN 关键字独占一行（与 ``merge_join_table`` 匹配）
_JOIN_KEYWORD_ONLY_LINE_RE = re.compile(
    r"^(\s*)(left\s+outer\s+join|right\s+outer\s+join|full\s+outer\s+join|"
    r"left\s+join|right\s+join|inner\s+join|full\s+join|cross\s+join|join)\s*$",
    re.IGNORECASE,
)


def merge_join_table(lines: List[str]) -> List[str]:
    """合并 JOIN 关键字独占一行时，下一行的表名到同一行（表名紧跟 join，与 ``merge_from_table`` 对称）。"""
    new_lines: List[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        raw = line.rstrip("\n")
        jm = _JOIN_KEYWORD_ONLY_LINE_RE.match(raw)
        if jm and i + 1 < n:
            nxt = lines[i + 1]
            nx = nxt.strip()
            if nx.startswith("--"):
                new_lines.append(line)
                i += 1
                continue
            if not nx:
                new_lines.append(line)
                i += 1
                continue
            if nx.startswith("("):
                new_lines.append(line)
                i += 1
                continue
            if re.match(
                r"^(select|on|where|group\s+by|having|order\s+by|limit|union|"
                r"(?:left|right|inner|cross|full)(?:\s+outer)?\s+join)\b",
                nx,
                re.IGNORECASE,
            ):
                new_lines.append(line)
                i += 1
                continue
            has_nl = nxt.endswith("\n")
            merged = raw + " " + nx + ("\n" if has_nl else "")
            new_lines.append(merged)
            i += 2
            continue
        new_lines.append(line)
        i += 1
    return new_lines


# 行首 JOIN 变体（向上查找缩进、拆行、align_where 识别）
_JOIN_LINE_START_RE = re.compile(
    r'^(\s*)(left\s+outer\s+join|right\s+outer\s+join|full\s+outer\s+join|'
    r'left\s+join|right\s+join|inner\s+join|full\s+join|cross\s+join|join)\b',
    re.IGNORECASE,
)


def _scan_depth_zero_on_position(s: str, scan_from: int) -> int:
    """在 ``scan_from`` 之后扫描，返回首个「括号深度为 0」处的 `` on `` 起始下标；无则 -1。

    忽略字符串/行注释/块注释内的括号与 ``on``。
    """
    n = len(s)
    i = max(0, scan_from)
    depth = 0
    mode = "code"

    def try_match_on(pos: int) -> int:
        if pos >= n or depth != 0 or mode != "code":
            return -1
        m = re.match(r"(?i)\s+on\s+", s[pos:])
        if m:
            return pos + m.start()
        return -1

    while i < n:
        ch = s[i]
        if ch == "\n":
            if mode == "line_comment":
                mode = "code"
            i += 1
            continue

        if mode == "line_comment":
            i += 1
            continue

        if mode == "block_comment":
            if ch == "*" and i + 1 < n and s[i + 1] == "/":
                mode = "code"
                i += 2
            else:
                i += 1
            continue

        if mode == "sq":
            if ch == "'":
                if i + 1 < n and s[i + 1] == "'":
                    i += 2
                else:
                    mode = "code"
                    i += 1
            else:
                i += 1
            continue

        if mode == "dq":
            if ch == '"':
                if i + 1 < n and s[i + 1] == '"':
                    i += 2
                else:
                    mode = "code"
                    i += 1
            else:
                i += 1
            continue

        if mode == "bt":
            if ch == "`":
                if i + 1 < n and s[i + 1] == "`":
                    i += 2
                else:
                    mode = "code"
                    i += 1
            else:
                i += 1
            continue

        hit = try_match_on(i)
        if hit >= 0:
            return hit

        if ch == "-" and i + 1 < n and s[i + 1] == "-":
            mode = "line_comment"
            i += 2
            continue
        if ch == "/" and i + 1 < n and s[i + 1] == "*":
            mode = "block_comment"
            i += 2
            continue
        if ch == "'":
            mode = "sq"
            i += 1
            continue
        if ch == '"':
            mode = "dq"
            i += 1
            continue
        if ch == "`":
            mode = "bt"
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1

    return -1


def _find_nearest_join_indent(lines: List[str], from_index: int) -> int:
    """向上查找最近的 left join / join 等行首缩进，用于子查询后 ON 与同层 JOIN 对齐。"""
    for j in range(from_index, -1, -1):
        lj = lines[j]
        m = _JOIN_LINE_START_RE.match(lj)
        if m:
            return len(m.group(1))
    return -1


def _join_indent_for_close_alias_on(lines: List[str], line_idx: int, left_upto_alias: str) -> int:
    """``) as alias on`` 拆行时：在向上扫描到的 JOIN 行中，取 ``join_indent <= 本行 ) 前缩进`` 的最大值。

    避免命中子查询内更深缩进的 ``left join`` 却把 ON 缩进错套到外层（见嵌套 ``) as t10 on``）。
    """
    close_lead = len(left_upto_alias) - len(left_upto_alias.lstrip())
    best = -1
    for j in range(line_idx - 1, -1, -1):
        lj = lines[j]
        m = _JOIN_LINE_START_RE.match(lj)
        if m:
            ji = len(m.group(1))
            if ji <= close_lead:
                best = max(best, ji)
    if best >= 0:
        return best
    return _find_nearest_join_indent(lines, line_idx - 1)


_CLOSE_PAREN_ALIAS_ON_SQL_KW = frozenset({
    'as', 'on', 'and', 'or', 'end', 'where', 'group', 'having', 'order',
    'limit', 'union', 'from', 'select', 'case', 'when', 'then', 'else',
    'set', 'insert', 'into', 'values', 'update', 'delete', 'create',
    'drop', 'alter', 'table', 'not', 'in', 'is', 'like', 'between',
    'exists', 'null', 'true', 'false', 'lateral', 'view', 'over',
})


def _try_split_join_on_one_line(body: str, all_lines: List[str], line_idx: int) -> Optional[Tuple[str, str]]:
    """若本行含同行 ``… join … on …`` 或 ``) [as] alias on …``，返回 (首行, 带缩进的 on 行)；否则 None。"""
    stripped = body.strip()
    if not stripped or stripped.startswith("--"):
        return None

    # 1) 子查询闭合别名同行 on（已有 AS）
    m_close = re.match(r"(?i)^(\s*\)\s+as\s+\S+)\s+on\s+(.+)$", body.rstrip("\n"))
    if m_close:
        left = m_close.group(1).rstrip()
        join_indent = _join_indent_for_close_alias_on(all_lines, line_idx, m_close.group(1))
        if join_indent < 0:
            join_indent = len(body) - len(body.lstrip())
        on_line = " " * join_indent + "on " + m_close.group(2).strip()
        return (left, on_line)

    # 1.5) 子查询闭合别名同行 on（缺少 AS）: ") alias on cond" / ")alias on cond" → ") as alias" + "on cond"
    m_close_no_as = re.match(r"(?i)^(\s*\))\s*(\w+)\s+on\s+(.+)$", body.rstrip("\n"))
    if m_close_no_as:
        alias = m_close_no_as.group(2)
        if alias.lower() not in _CLOSE_PAREN_ALIAS_ON_SQL_KW:
            close_paren = m_close_no_as.group(1)
            left = f"{close_paren} as {alias}"
            join_indent = _join_indent_for_close_alias_on(all_lines, line_idx, left)
            if join_indent < 0:
                join_indent = len(body) - len(body.lstrip())
            on_line = " " * join_indent + "on " + m_close_no_as.group(3).strip()
            return (left, on_line)

    # 1.6) 子查询闭合别名同行 where（已有 AS）: ") as alias where cond" → ") as alias" + "where cond"
    m_close_where = re.match(r"(?i)^(\s*\)\s+as\s+\S+)\s+where\s+(.+)$", body.rstrip("\n"))
    if m_close_where:
        left = m_close_where.group(1).rstrip()
        close_indent = len(body) - len(body.lstrip())
        where_line = " " * close_indent + "where " + m_close_where.group(2).strip()
        return (left, where_line)

    # 1.7) 子查询闭合别名同行 where（缺少 AS）: ") alias where cond" / ")alias where cond" → ") as alias" + "where cond"
    m_close_no_as_where = re.match(r"(?i)^(\s*\))\s*(\w+)\s+where\s+(.+)$", body.rstrip("\n"))
    if m_close_no_as_where:
        alias = m_close_no_as_where.group(2)
        if alias.lower() not in _CLOSE_PAREN_ALIAS_ON_SQL_KW:
            close_paren = m_close_no_as_where.group(1)
            left = f"{close_paren} as {alias}"
            close_indent = len(body) - len(body.lstrip())
            where_line = " " * close_indent + "where " + m_close_no_as_where.group(3).strip()
            return (left, where_line)

    # 2) left join … on …（从行首 join 关键字后扫描深度 0 的 on）
    jm = _JOIN_LINE_START_RE.match(body)
    if not jm:
        return None
    join_indent = len(jm.group(1))
    scan_from = jm.end()
    on_pos = _scan_depth_zero_on_position(body, scan_from)
    if on_pos < 0:
        return None
    tail = body[on_pos:]
    m_on = re.match(r"(?i)(\s*)(on\s+)(.+)$", tail)
    if not m_on:
        return None
    left = body[:on_pos].rstrip()
    if not left:
        return None
    # 拆分后为 left 部分补充缺失的 AS（如 "left join t1 alias" → "left join t1 as alias"）
    m_join_alias = re.match(
        r'^(\s*(?:left\s+(?:outer\s+)?join|right\s+(?:outer\s+)?join|inner\s+join'
        r'|full\s+(?:outer\s+)?join|cross\s+join|join)\s+\S+)'
        r'\s+(\w+)\s*$',
        left, re.IGNORECASE)
    if m_join_alias and not re.search(r'(?i)\bas\b', left):
        alias = m_join_alias.group(2)
        if alias.lower() not in _CLOSE_PAREN_ALIAS_ON_SQL_KW:
            left = f"{m_join_alias.group(1)} as {alias}"
    cond = m_on.group(3).strip()
    on_line = " " * join_indent + "on " + cond
    return (left, on_line)


def split_inline_join_on_lines(lines: List[str]) -> List[str]:
    """将同行 ``join … on …`` / ``) as alias on …`` 拆成两行，满足「ON 单独成行」规范。

    多轮直到稳定，以处理极少数一行内多次 ``… join … on …`` 串联（每轮拆最前一对）。
    """
    buf = list(lines)
    max_rounds = max(20, len(buf))
    for _ in range(max_rounds):
        new_buf: List[str] = []
        changed = False
        for i, line in enumerate(buf):
            has_nl = line.endswith("\n")
            body = line[:-1] if has_nl else line
            pair = _try_split_join_on_one_line(body, buf, i)
            if pair:
                a, b = pair
                new_buf.append(a + ("\n" if has_nl else ""))
                new_buf.append(b + ("\n" if has_nl else ""))
                changed = True
            else:
                new_buf.append(line)
        buf = new_buf
        if not changed:
            break
    return buf


def _find_spaced_keyword_top_level(text: str, word: str, lo: int = 0, hi: Optional[int] = None) -> int:
    """在 ``text[lo:hi]`` 中找首个圆括号深度 0、且为 `` {word} ``（两侧空格）的匹配起点；找不到返回 ``-1``。"""
    hi = hi if hi is not None else len(text)
    needle = f" {word} "
    nl = needle.lower()
    depth = 0
    in_sq = False
    i = lo
    while i < hi:
        ch = text[i]
        if in_sq:
            if ch == "'" and i + 1 < hi and text[i + 1] == "'":
                i += 2
                continue
            if ch == "'":
                in_sq = False
            i += 1
            continue
        if ch == "'":
            in_sq = True
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and i + len(needle) <= hi and text[i : i + len(needle)].lower() == nl:
            return i
        i += 1
    return -1


def _split_commas_top_level(segment: str) -> List[str]:
    """在圆括号深度 0、单引号串外，按逗号拆分 ``segment``。"""
    parts: List[str] = []
    buf: List[str] = []
    depth = 0
    in_sq = False
    i = 0
    n = len(segment)
    while i < n:
        ch = segment[i]
        if in_sq:
            buf.append(ch)
            if ch == "'" and i + 1 < n and segment[i + 1] == "'":
                buf.append(segment[i + 1])
                i += 2
                continue
            if ch == "'":
                in_sq = False
            i += 1
            continue
        if ch == "'":
            in_sq = True
            buf.append(ch)
            i += 1
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
            i += 1
            continue
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def split_dense_select_list_same_line(lines: List[str]) -> List[str]:
    """将单行 ``select`` 多列 ``… , … from … [where …]`` 拆成多行（行尾逗号），供 ``convert_to_leading_comma`` 收敛为句首逗号。

    仅处理行首为 ``select`` 且同层含 `` from `` 的整行；``insert … select`` 等同行的 ``select`` 不在行首则跳过。
    """
    out: List[str] = []
    for line in lines:
        has_nl = line.endswith("\n")
        raw = line[:-1] if has_nl else line
        if raw.lstrip().startswith("--"):
            out.append(line)
            continue
        m = re.match(r"^(\s*)select\s+(.+)$", raw, re.IGNORECASE)
        if not m:
            out.append(line)
            continue
        indent, tail = m.group(1), m.group(2)
        from_i = _find_spaced_keyword_top_level(tail, "from", 0, len(tail))
        if from_i < 0:
            out.append(line)
            continue
        list_seg = tail[:from_i].rstrip()
        from_rest = tail[from_i:].lstrip()
        if not from_rest.lower().startswith("from"):
            out.append(line)
            continue
        fields = _split_commas_top_level(list_seg)
        if len(fields) < 2:
            out.append(line)
            continue
        fs = len(indent) + len("select ")
        suf = "\n" if has_nl else ""
        out.append(indent + "select " + fields[0] + "," + suf)
        for fld in fields[1:-1]:
            out.append(" " * (fs - 2) + fld + "," + suf)
        # 最后一列不得带行尾逗号，否则 ``convert_to_leading_comma`` 会把逗号挪到下一行 ``from`` 前
        out.append(" " * (fs - 2) + fields[-1] + suf)
        rest = from_rest
        wh_i = _find_spaced_keyword_top_level(rest, "where", 0, len(rest))
        if wh_i >= 0:
            from_line = indent + rest[:wh_i].rstrip()
            wh_tail = rest[wh_i:].lstrip()
            if wh_tail.lower().startswith("where"):
                out.append(from_line + suf)
                out.append(indent + wh_tail + suf)
            else:
                out.append(indent + rest + suf)
        else:
            out.append(indent + rest + suf)
    return out


def merge_lonely_on_with_next_line(lines: List[str]) -> List[str]:
    """``on`` 独占一行时下一行接条件：合并为 ``on 条件``（``on`` 后恰有一空格），便于 ``align_where_and_clauses`` 识别。"""
    if not lines:
        return lines
    out: List[str] = []
    i = 0
    n = len(lines)
    while i < n:
        raw0 = lines[i].split("\n", 1)[0]
        if raw0.strip().lower() != "on":
            out.append(lines[i])
            i += 1
            continue
        j = _next_meaningful_line_index(lines, i + 1)
        if j is None:
            out.append(lines[i])
            i += 1
            continue
        if any(lines[k].strip().startswith("--") for k in range(i + 1, j)):
            out.append(lines[i])
            i += 1
            continue
        nst = lines[j].strip().lower()
        if re.match(
            r"^(left\s+(?:outer\s+)?join|right\s+(?:outer\s+)?join|inner\s+join|cross\s+join|"
            r"full\s+(?:outer\s+)?join|join|where|group\s+by|order\s+by|limit|union|from|on)\b",
            nst,
            re.I,
        ):
            out.append(lines[i])
            i += 1
            continue
        lead = raw0[: len(raw0) - len(raw0.lstrip())]
        has_nl = lines[i].endswith("\n") or lines[j].endswith("\n")
        merged = lead + "on " + lines[j].strip()
        if has_nl:
            merged += "\n"
        for k in range(i + 1, j):
            out.append(lines[k])
        out.append(merged)
        i = j + 1
    return out


def merge_lonely_where_having_with_next_line(lines: List[str]) -> List[str]:
    """``where``/``having`` 独占一行且下一行即谓词（无中间注释）时合并为一行，避免续行缩进未被对齐。"""
    if not lines:
        return lines
    out: List[str] = []
    i = 0
    n = len(lines)
    while i < n:
        raw0 = lines[i].split("\n", 1)[0]
        m_kw = re.match(r"^(\s*)(where|having)\s*$", raw0, re.IGNORECASE)
        if not m_kw:
            out.append(lines[i])
            i += 1
            continue
        j = _next_meaningful_line_index(lines, i + 1)
        if j is None:
            out.append(lines[i])
            i += 1
            continue
        if any(lines[k].strip().startswith("--") for k in range(i + 1, j)):
            out.append(lines[i])
            i += 1
            continue
        nst = lines[j].strip().lower()
        if re.match(
            r"^(select|from|where|having|group\s+by|order\s+by|limit|union|"
            r"left\s+|right\s+|inner\s+|full\s+|cross\s+|join)\b",
            nst,
            re.I,
        ):
            out.append(lines[i])
            i += 1
            continue
        lead = m_kw.group(1)
        kw = m_kw.group(2).lower()
        has_nl = lines[i].endswith("\n") or lines[j].endswith("\n")
        merged = f"{lead}{kw} {lines[j].strip()}"
        if has_nl:
            merged += "\n"
        for k in range(i + 1, j):
            out.append(lines[k])
        out.append(merged)
        i = j + 1
    return out


def _split_top_level_and_fragments(expr: str) -> List[str]:
    """在圆括号嵌套深度 0、且不在单/双引号字符串内时，按 `` and ``（不区分大小写）拆分。"""
    n = len(expr)
    i = 0
    parts: List[str] = []
    buf: List[str] = []
    depth = 0
    in_sq = False
    in_dq = False
    while i < n:
        ch = expr[i]
        if in_sq:
            buf.append(ch)
            if ch == "'" and i + 1 < n and expr[i + 1] == "'":
                buf.append(expr[i + 1])
                i += 2
                continue
            if ch == "'":
                in_sq = False
            i += 1
            continue
        if in_dq:
            buf.append(ch)
            if ch == "\\" and i + 1 < n:
                buf.append(expr[i + 1])
                i += 2
                continue
            if ch == '"':
                in_dq = False
            i += 1
            continue
        if ch == "'":
            in_sq = True
            buf.append(ch)
            i += 1
            continue
        if ch == '"':
            in_dq = True
            buf.append(ch)
            i += 1
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
            i += 1
            continue
        if depth == 0 and i + 5 <= n and expr[i : i + 5].lower() == " and ":
            parts.append("".join(buf).strip())
            buf = []
            i += 5
            continue
        buf.append(ch)
        i += 1
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p]


def split_long_on_conditions(lines: List[str]) -> List[str]:
    """将过长且含顶层 ``and`` 的独立 ``on`` 行拆成 ``on …`` + 若干 ``and …`` 行。

    在 ``split_inline_join_on_lines`` 之后、``align_where_and_clauses`` 之前执行，
    以便后续把 ``and`` 与 ``on``/``join`` 同列对齐。不处理 ``or`` 折行。
    """
    if not lines:
        return lines
    out: List[str] = []
    for line in lines:
        has_nl = line.endswith("\n")
        raw = line[:-1] if has_nl else line
        m = re.match(r"^(\s*)on\s+(.+)$", raw, re.IGNORECASE)
        if not m:
            out.append(line)
            continue
        indent, rest = m.group(1), m.group(2).strip()
        if len(rest) < LONG_ON_PREDICATE_MIN_LEN:
            out.append(line)
            continue
        frags = _split_top_level_and_fragments(rest)
        if len(frags) < 2:
            out.append(line)
            continue
        suf = "\n" if has_nl else ""
        out.append(f"{indent}on {frags[0]}{suf}")
        for frag in frags[1:]:
            out.append(f"{indent}and {frag}{suf}")
    return out


def split_where_conditions(lines: List[str]) -> List[str]:
    """将 ``where cond1 and cond2 ...`` 按顶层 ``and``/``or`` 拆成多行。

    仅拆分行首为 ``where``/``having`` 的行；括号/引号内的 ``and``/``or`` 不拆。
    拆分后第一个谓词留在 ``where``/``having`` 行，后续 ``and``/``or`` 各起新行，
    缩进与 ``where``/``having`` 行首相同。
    """
    if not lines:
        return lines
    out: List[str] = []
    for line in lines:
        has_nl = line.endswith("\n")
        raw = line[:-1] if has_nl else line
        m = re.match(r"^(\s*)(where|having)\s+(.+)$", raw, re.IGNORECASE)
        if not m:
            out.append(line)
            continue
        indent, kw, rest = m.group(1), m.group(2), m.group(3).strip()
        frags = _split_top_level_and_or_fragments(rest)
        if len(frags) < 2:
            out.append(line)
            continue
        suf = "\n" if has_nl else ""
        out.append(f"{indent}{kw} {frags[0][1]}{suf}")
        for connector, frag_text in frags[1:]:
            out.append(f"{indent}{connector} {frag_text}{suf}")
    return out


def _split_top_level_and_or_fragments(expr: str) -> List[Tuple[str, str]]:
    """在顶层（括号深度 0、不在引号内）按 `` and ``/`` or `` 拆分。

    返回 ``[(connector, fragment), ...]``，第一个元素 connector 为空字符串。
    """
    n = len(expr)
    i = 0
    parts: List[Tuple[str, str]] = []
    buf: List[str] = []
    depth = 0
    in_sq = False
    in_dq = False
    while i < n:
        ch = expr[i]
        if in_sq:
            buf.append(ch)
            if ch == "'" and i + 1 < n and expr[i + 1] == "'":
                buf.append(expr[i + 1])
                i += 2
                continue
            if ch == "'":
                in_sq = False
            i += 1
            continue
        if in_dq:
            buf.append(ch)
            if ch == "\\" and i + 1 < n:
                buf.append(expr[i + 1])
                i += 2
                continue
            if ch == '"':
                in_dq = False
            i += 1
            continue
        if ch == "'":
            in_sq = True
            buf.append(ch)
            i += 1
            continue
        if ch == '"':
            in_dq = True
            buf.append(ch)
            i += 1
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
            i += 1
            continue
        if depth == 0:
            if i + 5 <= n and expr[i : i + 5].lower() == " and ":
                parts.append(("" if not parts else "and", "".join(buf).strip()))
                buf = []
                i += 5
                continue
            if i + 4 <= n and expr[i : i + 4].lower() == " or ":
                parts.append(("" if not parts else "or", "".join(buf).strip()))
                buf = []
                i += 4
                continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        parts.append(("" if not parts else "and", tail))
    if parts and parts[0][0] == "":
        pass
    elif parts:
        parts[0] = ("", parts[0][1])
    return parts


def fix_subquery_on_indent(lines: List[str]) -> List[str]:
    """子查询 `) as alias` 下一行的 ON：与同层 left join / join 首列对齐（不与 `)` 对齐）。"""
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 检测右括号 + 表别名
        bracket_match = re.match(r'^(\s*)\)(\s+\w+)?\s*$', line)
        if bracket_match:
            join_indent = _find_nearest_join_indent(lines, i - 1)

            # 检查下一行是否是 ON
            if i + 1 < len(lines) and join_indent >= 0:
                next_line = lines[i + 1]
                on_match = re.match(r'^(\s*)on\s+(.*)$', next_line, re.IGNORECASE)

                if on_match:
                    current_on_indent = len(on_match.group(1))
                    on_content = on_match.group(2)

                    if current_on_indent != join_indent:
                        has_newline = next_line.endswith('\n')
                        new_on_line = ' ' * join_indent + 'on ' + on_content
                        if has_newline:
                            new_on_line += '\n'
                        new_lines.append(line)
                        new_lines.append(new_on_line)
                        i += 2
                        continue

        new_lines.append(line)
        i += 1

    return new_lines


def _is_with_cte_comma_line(stripped: str, next_line: Optional[str] = None) -> bool:
    """``, name as (`` 同行，或 ``, name as`` 且下一行仅为 ``(``（WITH 下一 CTE）。"""
    if re.match(r"^,\s*\w+\s+as\s*\(\s*$", stripped, re.I):
        return True
    if re.match(r"^,\s*\w+\s+as\s*$", stripped, re.I) and next_line is not None:
        if next_line.split("\n", 1)[0].strip() == "(":
            return True
    return False


def fix_with_cte_comma_indent(lines: List[str]) -> List[str]:
    """WITH 链：独占一行的 ``)`` 后接 ``, cte_name as (`` 时，逗号应与同链 ``with`` 行首同列。

    修复 ``align_field_names`` 在 ``in_case_block`` 等情况下未在 ``)`` 处结束 SELECT 列表、误把下一行
    ``, xxx as (`` 当成字段逗号列而多缩进的问题（见多 CTE：首段 ``group by`` 内嵌 CASE 时）。

    另：``),`` 与下一 CTE 之间可夹整行 ``--`` 注释；若下一非注释行为 ``name as (`` 且无行首逗号，则拆成
    ``)``、保留注释、``, name as`` 与 ``(`` 两行（括号列与同链已出现的 ``, xxx as`` / ``(`` 一致，均用 ``with`` 缩进列）。
    """
    if not lines:
        return lines
    out: List[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        raw = line.split("\n", 1)[0]
        st = raw.strip()
        # `),` + 可选空行/注释 + `name as (` 或 `name as` + 单独 `(`
        if i + 1 < n and re.match(r"^\)\s*,\s*$", st):
            lead_close = raw[: len(raw) - len(raw.lstrip())]
            j = i + 1
            middle: List[str] = []
            while j < n:
                rj = lines[j].split("\n", 1)[0]
                sj = rj.strip()
                if not sj:
                    middle.append(lines[j])
                    j += 1
                    continue
                if sj.startswith("--"):
                    middle.append(lines[j])
                    j += 1
                    continue
                break
            if j < n:
                hdr_raw = lines[j].split("\n", 1)[0]
                hdr_st = hdr_raw.strip()
                n2 = lines[j + 1] if j + 1 < n else None
                n2s = n2.split("\n", 1)[0].strip() if n2 else ""
                cte_name: Optional[str] = None
                consumed = 1
                m_one = re.match(r"^(\w+)\s+as\s*\(\s*$", hdr_st, re.I)
                if m_one:
                    cte_name = m_one.group(1)
                else:
                    m_two = re.match(r"^(\w+)\s+as\s*$", hdr_st, re.I)
                    if m_two and n2s == "(":
                        cte_name = m_two.group(1)
                        consumed = 2
                if cte_name:
                    tgt = 0
                    for jj in range(i, -1, -1):
                        rjj = lines[jj].split("\n", 1)[0].strip()
                        if re.match(r"(?i)^with\s+\S+\s+as\b", rjj):
                            tgt = len(lines[jj]) - len(lines[jj].lstrip())
                            break
                    has_nl = line.endswith("\n")
                    out.append(lead_close + ")" + ("\n" if has_nl else ""))
                    for ml in middle:
                        out.append(ml)
                    has_nl_hdr = lines[j].endswith("\n")
                    out.append(" " * tgt + f", {cte_name} as" + ("\n" if has_nl_hdr else ""))
                    if consumed == 1:
                        out.append(" " * tgt + "(" + ("\n" if has_nl_hdr else ""))
                        i = j + 1
                    else:
                        has_nl_op = bool(n2 and n2.endswith("\n"))
                        out.append(" " * tgt + "(" + ("\n" if has_nl_op else ""))
                        i = j + 2
                    continue
        if i + 1 < n and re.match(r"^\)\s*$", raw.strip()):
            nxt = lines[i + 1]
            nraw = nxt.split("\n", 1)[0]
            ns = nraw.strip()
            n2 = lines[i + 2] if i + 2 < n else None
            if _is_with_cte_comma_line(ns, n2):
                tgt = 0
                for j in range(i, -1, -1):
                    rj = lines[j].split("\n", 1)[0].strip()
                    if re.match(r"(?i)^with\s+\S+\s+as\b", rj):
                        tgt = len(lines[j]) - len(lines[j].lstrip())
                        break
                has_nl = nxt.endswith("\n")
                body = ns
                out.append(line)
                out.append(" " * tgt + body + ("\n" if has_nl else ""))
                i += 2
                continue
        out.append(line)
        i += 1
    return out


def align_field_names(lines: List[str]) -> List[str]:
    """对齐字段名首字母（针对没有AS关键字的字段列表）。

    单次对外调用内部迭代单遍 ``_align_field_names_pass`` 至稳定，以合并原 ``UNION`` 链后再次
    ``align_field_names`` 的因果（链上改列后逗号列须重算）。

    多行 `, … case when … end` 后若单独一行 `) as col`，须在 `)` 行之后才结束 CASE 块扫描，
    否则后续行首逗号不再统一列；见 ``docs/KNOWN_ISSUES.md`` Issue #4。
    """
    if not lines:
        return lines
    out = lines
    for _ in range(_ALIGN_FIELD_NAMES_MAX_STABLE):
        nxt = _align_field_names_pass(out)
        if nxt == out:
            return nxt
        out = nxt
    return out


def _align_field_names_pass(lines: List[str]) -> List[str]:
    """单遍字段名/逗号列对齐；由 ``align_field_names`` 迭代至稳定调用。"""
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip().lower()

        # 检测SELECT或GROUP BY的起始行
        select_match = re.match(r'^(\s*)(select|group\s+by)\s+(\S+)', line, re.IGNORECASE)

        if select_match:
            indent = select_match.group(1)
            keyword = select_match.group(2)
            first_field = select_match.group(3)

            # 计算第一个字段的起始位置
            keyword_end_pos = len(indent) + len(keyword)
            # 找到keyword后第一个非空格字符的位置
            after_keyword = line[keyword_end_pos:]
            spaces_after = len(after_keyword) - len(after_keyword.lstrip())
            field_start_pos = keyword_end_pos + spaces_after

            new_lines.append(line)
            i += 1

            # 处理后续逗号开头的字段行：统一行首逗号列（与首字段对齐）；后部原样保留，供后续 AS 对齐改写
            in_case_block = False
            while i < len(lines):
                next_line = lines[i]
                next_stripped = next_line.strip().lower()

                # 检测 CASE 多行块：从 `, ... case when` 开始；``end`` 后常有单独一行的 ``) as col``，
                # 不能在 ``end`` 行清 in_case_block，否则 ``)`` 行会误判为列表结束并 break，后续 ``, field`` 逗号列不再统一。
                if next_stripped.startswith(',') and 'case' in next_stripped and 'when' in next_stripped:
                    in_case_block = True

                # 如果遇到空行，停止
                if not next_stripped:
                    break

                # 整行 ``--`` 注释：原样写出且不断裂 select 列表（否则注释后逗号列会多缩进一格）
                if next_stripped.startswith("--"):
                    new_lines.append(next_line)
                    i += 1
                    continue

                # 子句起始：无论是否仍在 CASE 块内都要结束字段列表（避免 in_case 未清时把 from 吃进 select 循环）。
                # 不得在此用 ``order by`` / ``group by`` 截断：窗口函数 ``over (… order by …)`` 与 ``grouping sets`` 等会出现在选列区内，
                # 误断会导致后续 ``, expr`` 不再统一逗号列，并被 ``align_function_arg_continuations`` 按函数续行多垫空格。
                if re.match(
                    r'^(from|where|having|limit|union|'
                    r'left\s+join|right\s+join|inner\s+join|cross\s+join|full\s+outer\s+join|full\s+join|join)\b',
                    next_stripped,
                    re.I,
                ):
                    break

                # 如果不以逗号开头，且不在CASE块中，说明遇到新SQL子句，停止
                if not next_stripped.startswith(',') and not in_case_block:
                    # 窗口/分析函数括号内续行（尚未出现顶层 ``from`` 前不可能有真正的 ``ORDER BY``/``GROUP BY`` 子句）
                    if re.match(
                        r'^(order\s+by|group\s+by|partition\s+by|rows\s+between)\b',
                        next_stripped,
                        re.I,
                    ):
                        new_lines.append(next_line)
                        i += 1
                        continue
                    # 检查是否是CASE块的中间行（WHEN, ELSE等）
                    if not (next_stripped.startswith('when ') or
                           next_stripped.startswith('else ') or
                           next_stripped.startswith('end')):
                        break

                # 不以逗号开头的行（CASE块中间行），保持原样
                if not next_stripped.startswith(','):
                    new_lines.append(next_line)
                    if in_case_block and next_stripped.startswith(')'):
                        in_case_block = False
                    i += 1
                    # 同上：已写出 ``)`` 后若下一行是 WITH 链 ``, name as (``，结束字段列表
                    if re.match(r"^\)\s*$", next_stripped) and i < len(lines):
                        n2raw = lines[i]
                        n2s = n2raw.split("\n", 1)[0].strip()
                        n3 = lines[i + 1] if i + 1 < len(lines) else None
                        if _is_with_cte_comma_line(n2s, n3):
                            break
                    continue

                # 提取逗号后的内容（逗号后可能有空格也可能没有）
                comma_match = re.match(r'^(\s*),\s*(.*)', next_line)
                if comma_match:
                    rest = comma_match.group(2)
                    # 统一行首逗号列（含「将交给 AS 对齐」的简单 `, expr as col` 行），避免与 `, case` 多行首行错位
                    new_indent = ' ' * (field_start_pos - 2)
                    has_newline = next_line.endswith('\n')
                    new_line = f"{new_indent}, {rest}"
                    if has_newline and not new_line.endswith('\n'):
                        new_line += '\n'
                    elif not has_newline and new_line.endswith('\n'):
                        new_line = new_line[:-1]
                    new_lines.append(new_line)
                else:
                    new_lines.append(next_line)

                i += 1
        else:
            new_lines.append(line)
            i += 1

    return new_lines


_KW_MULTI_SPACE_RE = re.compile(
    r'\b(select|from|where|and|or|on|having|group\s+by|order\s+by|limit|when|then|else)\s{2,}(?=\S)',
    re.IGNORECASE,
)


def normalize_keyword_spacing(lines: List[str]) -> List[str]:
    """将 SQL 关键字后的多余空格压缩为单空格（跳过注释行和字符串内部）。"""
    new_lines: List[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('--'):
            new_lines.append(line)
            continue
        parts = re.split(r"('(?:[^'\\]|\\.)*')", line)
        rebuilt = []
        for i, part in enumerate(parts):
            if i % 2 == 0:
                part = _KW_MULTI_SPACE_RE.sub(lambda m: m.group(1) + ' ', part)
            rebuilt.append(part)
        new_lines.append(''.join(rebuilt))
    return new_lines


_SQL_KEYWORDS_LOWER = {
    'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'EXISTS',
    'LEFT', 'RIGHT', 'INNER', 'CROSS', 'FULL', 'JOIN', 'ON',
    'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'UNION', 'ALL',
    'INSERT', 'INTO', 'OVERWRITE', 'TABLE', 'PARTITION',
    'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'AS', 'DISTINCT',
    'OVER', 'BETWEEN', 'LIKE', 'RLIKE', 'IS', 'NULL', 'TRUE', 'FALSE',
    'SET', 'CREATE', 'IF', 'DROP', 'ALTER', 'ADD', 'WITH',
    'LATERAL', 'VIEW', 'STORED', 'ORC', 'PARTITIONED', 'COMMENT',
    'CAST', 'INT', 'BIGINT', 'STRING', 'DECIMAL', 'DOUBLE', 'FLOAT',
    'BOOLEAN', 'TIMESTAMP', 'DATE', 'ARRAY', 'MAP', 'STRUCT',
    'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'COALESCE', 'NVL',
    'CONCAT', 'SUBSTR', 'SUBSTRING', 'TRIM', 'LOWER', 'UPPER',
    'LENGTH', 'REPLACE', 'REGEXP_REPLACE', 'REGEXP_EXTRACT', 'SPLIT',
    'DATE_FORMAT', 'TO_DATE', 'DATE_ADD', 'DATE_SUB', 'DATEDIFF',
    'FROM_UNIXTIME', 'UNIX_TIMESTAMP', 'YEAR', 'MONTH', 'DAY',
    'ROUND', 'CEIL', 'FLOOR', 'ABS', 'MOD', 'POWER', 'SQRT',
    'SIZE', 'EXPLODE', 'COLLECT_LIST', 'COLLECT_SET',
    'ROW_NUMBER', 'RANK', 'DENSE_RANK', 'LAG', 'LEAD',
    'FIRST_VALUE', 'LAST_VALUE', 'NTILE',
    'IF', 'IFNULL', 'NULLIF', 'GREATEST', 'LEAST',
    'GET_JSON_OBJECT', 'JSON_TUPLE', 'PARSE_URL',
    'CONCAT_WS', 'FIND_IN_SET', 'INSTR', 'LPAD', 'RPAD',
    'REFLECT', 'HASH', 'MD5', 'SHA1', 'SHA2', 'CRC32',
    'PERCENTILE', 'PERCENTILE_APPROX', 'VARIANCE', 'STDDEV',
    'GROUPING', 'SETS', 'CUBE', 'ROLLUP',
    'EXCEPT', 'INTERSECT', 'SEMI', 'ANTI',
    'TABLESAMPLE', 'DISTRIBUTE', 'SORT', 'CLUSTER',
    'TBLPROPERTIES', 'EXTERNAL', 'TEMPORARY', 'LOCATION',
    'ROW', 'FORMAT', 'DELIMITED', 'FIELDS', 'TERMINATED',
    'COLLECTION', 'ITEMS', 'KEYS', 'LINES', 'SERDE',
    'INPUTFORMAT', 'OUTPUTFORMAT',
    'DESCRIBE', 'SHOW', 'USE', 'DATABASE', 'DATABASES', 'TABLES',
    'COLUMNS', 'FUNCTIONS', 'FORMATTED',
    'MSCK', 'REPAIR', 'RECOVER', 'PARTITIONS',
    'GRANT', 'REVOKE', 'ROLE', 'PRIVILEGES',
    'ASC', 'DESC', 'NULLS', 'FIRST', 'LAST',
    'FETCH', 'NEXT', 'ROWS', 'ONLY', 'OFFSET',
    'WINDOW', 'RANGE', 'UNBOUNDED', 'PRECEDING', 'FOLLOWING', 'CURRENT',
}
_SQL_KW_LOWER_RE = re.compile(
    r"(?<![`'\w])\b(" + '|'.join(sorted(_SQL_KEYWORDS_LOWER, key=len, reverse=True)) + r")\b(?![`'\w])",
    re.IGNORECASE,
)


def lowercase_sql_keywords(lines: List[str]) -> List[str]:
    """将注释和字符串之外的 SQL 关键字/函数名统一为小写。"""
    new_lines: List[str] = []
    for line in lines:
        parts = re.split(r"(--.*|'[^']*')", line)
        rebuilt: List[str] = []
        for idx_p, part in enumerate(parts):
            if idx_p % 2 == 1:
                rebuilt.append(part)
            else:
                rebuilt.append(_SQL_KW_LOWER_RE.sub(lambda m: m.group(1).lower(), part))
        new_lines.append(''.join(rebuilt))
    return new_lines


_TOPLEVEL_TRIGGER_RE = re.compile(
    r"^\s*(?:create\s+table\b.*\bas|insert\s+(?:overwrite|into)\s+table\b.*\))\s*$",
    re.IGNORECASE,
)

_TOPLEVEL_KW_RE = re.compile(
    r"^(\s+)(select|from|where|group\s+by|having|order\s+by|limit|left\s+join|right\s+join|inner\s+join|cross\s+join|full\s+(?:outer\s+)?join|join|lateral\s+view|on)\b(.*)$",
    re.IGNORECASE,
)


def flush_select_after_create_table_as(lines: List[str]) -> List[str]:
    """顶层语句（``create table … as`` / ``insert … partition(…)``）后的主导查询关键字顶格。

    找到触发行后，将其后同层（括号深度 0）的 ``select``/``from``/``where``/``join`` 等关键字
    行首空白去掉，直到遇到下一个触发行或文件末尾。
    """
    out = list(lines)
    n = len(out)
    i = 0
    while i < n:
        head = out[i].split("--", 1)[0]
        if not _TOPLEVEL_TRIGGER_RE.match(head.rstrip()):
            i += 1
            continue
        depth = 0
        j = i + 1
        while j < n:
            raw = out[j]
            stripped = raw.strip()
            if not stripped or stripped.startswith("--"):
                j += 1
                continue
            if _TOPLEVEL_TRIGGER_RE.match(stripped):
                break
            if stripped.startswith(";"):
                break
            if depth == 0:
                m = _TOPLEVEL_KW_RE.match(raw.rstrip("\n"))
                if m:
                    has_nl = raw.endswith("\n")
                    out[j] = m.group(2).lower() + m.group(3) + ("\n" if has_nl else "")
            code = raw.split("--", 1)[0]
            in_sq = False
            for ch in code:
                if ch == "'" and not in_sq:
                    in_sq = True
                elif ch == "'" and in_sq:
                    in_sq = False
                elif not in_sq:
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
            j += 1
        i += 1
    return out


def normalize_operator_spacing(lines: List[str]) -> List[str]:
    """标准化运算符空格：所有比较运算符和赋值运算符前后都添加空格

    规范：
    1. 比较运算符：=, !=, <>, <, >, <=, >= 前后必须有空格
    2. 注意：不处理字符串内的运算符

    示例：
        dt<='${p_date}' → dt <= '${p_date}'
        order_seq=1 → order_seq = 1
    """
    new_lines = []

    for line in lines:
        # 跳过注释行
        if line.strip().startswith('--'):
            new_lines.append(line)
            continue

        # 处理运算符，按优先级从长到短
        result = line

        # 1. 双字符运算符：<=, >=, !=, <>
        result = re.sub(r'(\S)\s*(<=|>=|!=|<>)\s*', r'\1 \2 ', result)

        # 2. 单字符运算符：=, <, >（但要避免已经处理过的 <=, >= 等）
        # 先处理 = 号（不是 != <> >= <= 的一部分）
        result = re.sub(r'(\w)\s*=\s*(?!=)', r'\1 = ', result)
        result = re.sub(r'(?<!<|>|!)\s*=\s*(\S)', r' = \1', result)

        # 处理 < 和 >（不是 <>, <=, >= 的一部分）
        result = re.sub(r'([\w)])\s*<\s*(?![>=])', r'\1 < ', result)
        result = re.sub(r'([\w)])\s*>\s*(?![=])', r'\1 > ', result)

        new_lines.append(result)

    return new_lines


def convert_to_leading_comma(lines: List[str]) -> List[str]:
    """将逗号后置转换为逗号前置

    规范：
    1. SELECT 字段列表：逗号移到下一行行首
    2. CREATE TABLE 列定义：逗号移到下一行行首
    3. 保留第一个字段/列（不加逗号）

    示例：
        field1,
        field2,
        field3
    转换为：
        field1
        , field2
        , field3
    """
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 跳过注释行
        if stripped.startswith('--'):
            new_lines.append(line)
            i += 1
            continue

        # 检测行尾逗号（排除函数内的逗号，如 f(a, b)）
        # 处理行尾逗号（后面只有空格/换行）以及逗号后跟 -- 注释的情况
        _comma_tail_m = re.search(r',\s*(?:--.*)?$', line)
        _is_trailing_comma = False
        if _comma_tail_m and i + 1 < len(lines):
            _pre_comma = line[:_comma_tail_m.start()]
            _open = _pre_comma.count('(') - _pre_comma.count(')')
            _is_trailing_comma = _open <= 0

        if _is_trailing_comma:
            # look-ahead：跳过注释行和空行，找到第一个有效数据行
            next_data_idx = i + 1
            while next_data_idx < len(lines):
                _ns = lines[next_data_idx].strip()
                if _ns and not _ns.startswith('--'):
                    break
                next_data_idx += 1

            if next_data_idx >= len(lines):
                new_lines.append(line)
                i += 1
                continue

            next_line = lines[next_data_idx]
            next_stripped = next_line.strip()

            # 提取当前行的行尾注释（逗号后面的 -- ...）
            _trailing_comment = ''
            _tc_m = re.search(r',\s*(--.*?)\s*$', line)
            if _tc_m:
                _trailing_comment = ' ' + _tc_m.group(1)

            # 检查目标数据行是否已经以逗号开头
            if next_stripped.startswith(','):
                line_without_comma = re.sub(r',\s*(?:--.*)?$', '', line)
                has_newline = line.endswith('\n')
                line_without_comma = line_without_comma.rstrip() + _trailing_comment
                if has_newline:
                    line_without_comma += '\n'
                new_lines.append(line_without_comma)
                # 把中间的注释/空行原样追加
                for mid_idx in range(i + 1, next_data_idx):
                    new_lines.append(lines[mid_idx])
                i = next_data_idx
                continue

            # 目标数据行不是逗号开头，需要转换
            line_without_comma = re.sub(r',\s*(?:--.*)?$', '', line)
            has_newline = line.endswith('\n')
            line_without_comma = line_without_comma.rstrip() + _trailing_comment
            if has_newline:
                line_without_comma += '\n'
            new_lines.append(line_without_comma)

            # 把中间的注释/空行原样追加
            for mid_idx in range(i + 1, next_data_idx):
                new_lines.append(lines[mid_idx])

            # 给目标数据行添加前导逗号
            next_indent = len(next_line) - len(next_line.lstrip())
            next_has_newline = next_line.endswith('\n')
            new_next_line = ' ' * next_indent + ', ' + next_stripped
            if next_has_newline and not new_next_line.endswith('\n'):
                new_next_line += '\n'
            lines[next_data_idx] = new_next_line
            i = next_data_idx
            continue

        new_lines.append(line)
        i += 1

    return new_lines


def fix_select_as_error(lines: List[str]) -> List[str]:
    """修复 'select as field_name' 的错误，应为 'select field_name'"""
    new_lines = []
    for line in lines:
        # 匹配 "select as field_name" 模式
        fixed = re.sub(r'\bselect\s+as\s+(\w+)', r'select \1', line, flags=re.IGNORECASE)
        new_lines.append(fixed)
    return new_lines


def _is_as_inside_unclosed_cast(line: str, as_match) -> bool:
    """判断某个 `` as `` 是否位于 ``cast(`` 尚未闭合的括号内（类型转换的 as，非列别名）。"""
    pos = as_match.start()
    lower = line.lower()
    while pos > 0:
        cast_pos = lower.rfind('cast(', 0, pos)
        if cast_pos < 0:
            return False
        snippet = line[cast_pos + 5: pos]
        depth = 1
        for ch in snippet:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
        if depth > 0:
            return True
        pos = cast_pos
    return False


def _last_nonspace_idx_before_column_as(lb: str) -> Optional[int]:
    """列别名 `` as word`` 之前最后一个非空字符的 0-based 下标；无合法列别名 ``as`` 则 ``None``。"""
    for cand in reversed(list(re.finditer(r"\s+as\s+(\w+)", lb, re.I))):
        if _is_as_inside_unclosed_cast(lb, cand):
            continue
        pre = lb[: cand.start()]
        pre2 = pre.rstrip()
        if not pre2:
            return cand.start() - 1
        return len(pre2) - 1
    return None


def _unify_gate_char_span_len_from_pos(lb: str, pos: int) -> int:
    """闸门用：从 0-based ``pos`` 起，到该行「列别名 ``as`` 前最后非空」或（无 ``as`` 时）行末最后非空的字符个数。"""
    end_as = _last_nonspace_idx_before_column_as(lb)
    if end_as is None:
        end0 = len(lb.rstrip()) - 1
        while end0 >= pos and lb[end0] in " \t":
            end0 -= 1
    else:
        end0 = end_as
        while end0 >= pos and lb[end0] in " \t":
            end0 -= 1
    if end0 < pos:
        return 0
    return end0 - pos + 1


def parse_select_field(line: str) -> Tuple[str, int, str, str, int]:
    """解析 SELECT 字段行，返回字段表达式、AS位置、别名、原始行、字段起始位置"""
    if line.lstrip().startswith('--') or line.lstrip().startswith('/*'):
        return None, -1, None, line, -1
    matches = list(re.finditer(r'\s+as\s+(\w+)', line, re.IGNORECASE))
    if not matches:
        return None, -1, None, line, -1

    match = None
    for cand in reversed(matches):
        if _is_as_inside_unclosed_cast(line, cand):
            continue
        match = cand
        break
    if match is None:
        return None, -1, None, line, -1

    char_pos_before_as = match.start()
    alias = match.group(1)

    matched_text = match.group()
    leading_spaces = len(matched_text) - len(matched_text.lstrip())
    as_display_pos = get_width(line[:char_pos_before_as]) + leading_spaces

    line_stripped = line.lstrip()
    field_start_display_pos = 0

    if line_stripped.startswith(','):
        comma_char_pos = line.find(',')
        field_start_display_pos = get_width(line[:comma_char_pos]) + 1
        temp_char_pos = comma_char_pos + 1
        while temp_char_pos < char_pos_before_as and line[temp_char_pos] == ' ':
            field_start_display_pos += 1
            temp_char_pos += 1
        field_expr = line[comma_char_pos+1:char_pos_before_as].strip()
    elif 'select' in line_stripped.lower()[:10]:
        select_match = re.search(r'\bselect\b', line, re.IGNORECASE)
        if select_match:
            field_start_display_pos = get_width(line[:select_match.end()])
            temp_char_pos = select_match.end()
            while temp_char_pos < char_pos_before_as and line[temp_char_pos] == ' ':
                field_start_display_pos += 1
                temp_char_pos += 1
            field_expr = line[select_match.end():char_pos_before_as].strip()
        else:
            field_start_display_pos = 0
            field_expr = line[:char_pos_before_as].strip()
    else:
        indent = line[:len(line) - len(line_stripped)]
        field_start_display_pos = get_width(indent)
        temp_char_pos = len(indent)
        while temp_char_pos < char_pos_before_as and line[temp_char_pos] == ' ':
            field_start_display_pos += 1
            temp_char_pos += 1
        field_expr = line[len(indent):char_pos_before_as].strip()

    return field_expr, as_display_pos, alias, line, field_start_display_pos


def detect_select_blocks(lines: List[str]) -> List[Tuple[int, int, str]]:
    """自动检测文件中的所有 SELECT 块"""
    blocks = []
    in_select = False
    select_start = -1
    select_indent = 0

    for i, line in enumerate(lines):
        stripped = line.strip().lower()

        if re.match(r'^\s*select\s+', line, re.IGNORECASE):
            if in_select:
                blocks.append((select_start, i - 1, f"SELECT block {len(blocks)+1}"))

            in_select = True
            select_start = i
            select_indent = len(line) - len(line.lstrip())

        elif in_select:
            current_indent = len(line) - len(line.lstrip())

            if current_indent <= select_indent and re.match(r'^\s*(from|where|group\s+by|having|order\s+by|limit|union|\))\s', line, re.IGNORECASE):
                blocks.append((select_start, i - 1, f"SELECT block {len(blocks)+1}"))
                in_select = False

    if in_select:
        blocks.append((select_start, len(lines) - 1, f"SELECT block {len(blocks)+1}"))

    return blocks


def _select_list_line_char_len_unify_gate(lb: str, ref_1based: Optional[int]) -> Tuple[int, Optional[int]]:
    """单行字符长度（闸门用）及头行对 ``ref_1based`` 的更新。

    头行：``select``/``group by`` 起首或 strip 以 ``,`` 起首——从句首逗号等价列（1-based 记为 ``ref``）起，至该行**列别名** ``as`` **之前**最后一个非空字符（无 ``as`` 则至行末最后非空）。

    续行：从 ``ref_1based`` 在本行的垂直位置（下标 ``ref_1based - 1``）起，规则同上。

    返回 ``(length, new_ref_1based_or_None)``；头行时第二元为新的 ``ref``；续行时第二元为 ``None``。
    """
    st = lb.strip()
    if not st or st.startswith("--"):
        return -1, None
    if re.match(r"^\s*select\s+", lb, re.I):
        m = re.search(r"\bselect\b", lb, re.I)
        if not m:
            return -1, None
        pos = m.end()
        while pos < len(lb) and lb[pos] in " \t":
            pos += 1
        new_ref = pos + 1
        return _unify_gate_char_span_len_from_pos(lb, pos), new_ref
    if re.match(r"^\s*group\s+by\s+", lb, re.I):
        m = re.search(r"\bgroup\s+by\b", lb, re.I)
        if not m:
            return -1, None
        pos = m.end()
        while pos < len(lb) and lb[pos] in " \t":
            pos += 1
        new_ref = pos + 1
        return _unify_gate_char_span_len_from_pos(lb, pos), new_ref
    if st.startswith(","):
        pos = len(lb) - len(lb.lstrip())
        new_ref = pos + 1
        return _unify_gate_char_span_len_from_pos(lb, pos), new_ref
    # 续行
    if ref_1based is None:
        return -1, None
    pos = ref_1based - 1
    if pos >= len(lb):
        return 0, None
    return _unify_gate_char_span_len_from_pos(lb, pos), None


def select_block_unify_as_by_head_char_span(lines: List[str], start: int, end: int) -> bool:
    """同一 SELECT 块内：选列区每物理行（整行 ``--`` 除外）按句首逗号列 1-based 垂直续行量字符长（有列别名 ``as`` 时以 ``as`` 前最后非空为右端）；若 ``max-min`` ≤ ``SELECT_AS_UNIFY_HEAD_CHAR_SPAN_MAX`` 则整块 ``as`` 单列对齐。"""
    lens: List[int] = []
    ref_1based: Optional[int] = None
    for i in range(start, min(end + 1, len(lines))):
        raw = lines[i]
        lb = raw.split("\n", 1)[0]
        L, new_ref = _select_list_line_char_len_unify_gate(lb, ref_1based)
        if L < 0:
            continue
        if new_ref is not None:
            ref_1based = new_ref
        lens.append(L)
    if not lens:
        return False
    return (max(lens) - min(lens)) <= SELECT_AS_UNIFY_HEAD_CHAR_SPAN_MAX


def _gate_ref_before_line(lines: List[str], select_start: int, line_idx: int) -> Optional[int]:
    """模拟闸门逐行扫描，返回处理 ``line_idx`` 行时沿用的句首 ref（1-based）；与 ``_select_list_line_char_len_unify_gate`` 一致。"""
    ref_1based: Optional[int] = None
    for i in range(select_start, min(line_idx, len(lines))):
        lb = lines[i].split("\n", 1)[0]
        st = lb.strip()
        if not st or st.startswith("--"):
            continue
        _, new_ref = _select_list_line_char_len_unify_gate(lb, ref_1based)
        if new_ref is not None:
            ref_1based = new_ref
    return ref_1based


def _field_gate_rel_display_width(
    lines: List[str], select_start: int, line_num: int, lb: str
) -> Optional[float]:
    """与闸门一致：从句首 ref（垂直对齐列）到列别名 ``as`` 前最后非空的显示宽度（续行同 ref）。"""
    ref_1based = _gate_ref_before_line(lines, select_start, line_num)
    if ref_1based is None:
        return None
    pos = ref_1based - 1
    if pos < 0 or pos >= len(lb):
        return None
    end_as = _last_nonspace_idx_before_column_as(lb)
    if end_as is None or end_as < pos:
        return None
    return get_width(lb[pos : end_as + 1])


def _field_gate_abs_end_display(lb: str) -> Optional[float]:
    """行首至列别名 ``as`` 前最后非空字符的显示宽度（与 ref + rel 之和一致）。"""
    end_as = _last_nonspace_idx_before_column_as(lb)
    if end_as is None:
        return None
    return get_width(lb[: end_as + 1])


def analyze_select_block(lines: List[str], start: int, end: int) -> Dict:
    """分析 SELECT 块中的字段并按长度分组"""
    fields = []

    for i in range(start, min(end + 1, len(lines))):
        line = lines[i]
        field_expr, as_pos, alias, original, field_start_pos = parse_select_field(line)

        if field_expr and alias:
            # 子查询闭合 ``) as alias`` 不应参与选列 ``as`` 列对齐（避免 ``)`` 与 ``as`` 间被垫空）
            if re.fullmatch(r"\)+", field_expr.strip()):
                continue
            field_len = get_width(field_expr)
            lb = line.split("\n", 1)[0]
            gate_rel = _field_gate_rel_display_width(lines, start, i, lb)
            gate_abs_end = _field_gate_abs_end_display(lb)
            tier_len = float(gate_rel) if gate_rel is not None else float(field_len)

            fields.append({
                'line_num': i,
                'field_expr': field_expr,
                'field_len': field_len,
                'tier_len': tier_len,
                'gate_abs_end': gate_abs_end,
                'as_pos': as_pos,
                'alias': alias,
                'original': original,
                'field_start_pos': field_start_pos
            })

    short_group = [f for f in fields if f['tier_len'] <= SHORT_FIELD_MAX]
    medium_group = [f for f in fields if SHORT_FIELD_MAX < f['tier_len'] <= MEDIUM_FIELD_MAX]
    long_group = [f for f in fields if f['tier_len'] > MEDIUM_FIELD_MAX]
    groups: List[List[Dict]] = [g for g in [short_group, medium_group, long_group] if g]

    return {
        'groups': groups,
        'all': fields
    }


def calculate_target_as_column(fields: List[Dict]) -> int:
    """计算目标 AS 对齐列位置（右端优先用闸门同源的 ``gate_abs_end``，避免跨行续行片段误算）。"""
    if not fields:
        return 0

    max_field_end_pos = 0
    for field in fields:
        end_w = field.get("gate_abs_end")
        if end_w is None:
            end_w = float(field["field_start_pos"]) + float(field["field_len"])
        # 用 floor 取「表达式尾后第一列」，避免浮点宽度使 max 比 ideal 大 1
        end_i = int(math.floor(float(end_w) + 1e-9))
        max_field_end_pos = max(max_field_end_pos, end_i)
    return max_field_end_pos + AS_SPACING


def align_fields_in_place(lines: List[str], fields: List[Dict], target_col: int, select_start: int) -> List[str]:
    """对齐字段的 AS 关键字"""
    new_lines = lines.copy()

    # 计算SELECT块的字段起始位置（用于统一逗号开头字段的缩进）
    select_line = lines[select_start]
    select_match = re.match(r'^(\s*)(select|group\s+by)\s+(\S+)', select_line, re.IGNORECASE)
    field_start_pos = None
    if select_match:
        indent = select_match.group(1)
        keyword = select_match.group(2)
        keyword_end_pos = len(indent) + len(keyword)
        after_keyword = select_line[keyword_end_pos:]
        spaces_after = len(after_keyword) - len(after_keyword.lstrip())
        field_start_pos = keyword_end_pos + spaces_after

    # 预计算括号深度：深度>0 的行是函数参数续行，不应重置缩进
    _func_cont_lines: set = set()
    if fields:
        _max_ln = max(f['line_num'] for f in fields)
        _depth = 0
        for _idx in range(select_start, min(_max_ln + 1, len(new_lines))):
            if _depth > 0:
                _func_cont_lines.add(_idx)
            _depth += _paren_delta_ignore_strings_sq(new_lines[_idx])

    for field in fields:
        line_num = field['line_num']
        old_line = new_lines[line_num]
        field_expr = field['field_expr'].rstrip()
        alias = field['alias']

        line_stripped = old_line.lstrip()

        if line_stripped.startswith(','):
            if line_num in _func_cont_lines:
                indent = old_line[:len(old_line) - len(line_stripped)]
                prefix = indent + ', '
            elif field_start_pos is not None:
                prefix = ' ' * (field_start_pos - 2) + ', '
            else:
                indent = old_line[:len(old_line) - len(line_stripped)]
                prefix = indent + ', '
        elif 'select' in line_stripped.lower()[:10]:
            select_match = re.search(r'\bselect\b', old_line, re.IGNORECASE)
            prefix = old_line[:select_match.end() + 1]
        else:
            indent = old_line[:len(old_line) - len(line_stripped)]
            prefix = indent

        prefix_get_width = get_width(prefix)
        field_expr_get_width = get_width(field_expr)
        current_display_len = prefix_get_width + field_expr_get_width
        # 用 floor 避免 float 与 round 导致 ``))  as`` 多出一格垫空格
        spaces_needed = max(
            1,
            int(
                math.floor(
                    float(target_col) - float(current_display_len) + 1e-9
                )
            ),
        )

        trailing_comment = ''
        cm = re.search(r'\s+--|(?<=\w)--', old_line)
        if cm:
            trailing_comment = old_line[cm.start():].rstrip('\n')

        has_newline = old_line.endswith('\n')
        new_line = prefix + field_expr + " " * spaces_needed + "as " + alias + trailing_comment
        if has_newline:
            new_line += '\n'

        new_lines[line_num] = new_line

    return new_lines


def verify_select_alignment(lines: List[str], start: int, end: int) -> bool:
    """验证 SELECT 块的 AS 对齐情况"""
    result = analyze_select_block(lines, start, end)

    if not result["all"]:
        return True

    if select_block_unify_as_by_head_char_span(lines, start, end):
        as_positions = set(f["as_pos"] for f in result["all"])
        return len(as_positions) <= 1

    is_aligned = True
    prev_pos = -1

    for group in result['groups']:
        if group:
            as_positions = set(f['as_pos'] for f in group)
            if len(as_positions) > 1:
                is_aligned = False
            else:
                cur_pos = list(as_positions)[0]
                if prev_pos >= 0 and cur_pos <= prev_pos:
                    is_aligned = False
                prev_pos = cur_pos

    return is_aligned


def parse_create_table_column(line: str) -> Tuple[str, str, str, str]:
    """解析建表语句的列定义行"""
    # 列名：反引号包裹（Hive 保留字/习惯）或裸标识符；其余逻辑不变
    pattern = r'^(\s*,?\s*)((?:`[^`]+`)|\w+)\s+(.+?)\s+comment\s+(.*?)$'
    match = re.match(pattern, line.rstrip(), re.IGNORECASE)

    if match:
        prefix = match.group(1)
        column_name = match.group(2)
        data_type = match.group(3)
        comment_text = match.group(4).rstrip(',').strip()  # 移除行尾逗号和空格
        return column_name, data_type, comment_text, line

    return None, None, None, line


def split_create_table_open_paren(lines: List[str]) -> List[str]:
    """若 ``create table ... 表名(`` 左括号在行尾，拆到下一行独占，与 ``create`` 行首对齐。"""
    new_lines: List[str] = []
    for line in lines:
        m = re.match(r'^(\s*create\s+table\b.+?)\(\s*$', line, re.IGNORECASE)
        if m:
            indent = len(line) - len(line.lstrip())
            has_nl = line.endswith('\n')
            suf = '\n' if has_nl else ''
            new_lines.append(m.group(1).rstrip() + suf)
            new_lines.append(' ' * indent + '(' + suf)
        else:
            new_lines.append(line)
    return new_lines


def split_cte_as_open_paren(lines: List[str]) -> List[str]:
    """若 ``with name as (`` 或 ``, name as (`` 行尾 ``(`` 与 ``as`` 同行，拆 ``(`` 到下一行独占。

    亦处理 ``as (select ...`` 同行（``(`` 后仍有内容），与 ``split_from_join_open_paren`` 中 ``from (select`` 一致。
    """
    new_lines: List[str] = []
    for line in lines:
        m = re.match(r'^(\s*(?:with\s+\w+|,\s*\w+)\s+as)\s*\(\s*$', line, re.IGNORECASE)
        if m:
            indent = len(line) - len(line.lstrip())
            has_nl = line.endswith('\n')
            suf = '\n' if has_nl else ''
            new_lines.append(m.group(1) + suf)
            new_lines.append(' ' * indent + '(' + suf)
            continue
        m2 = re.match(
            r'^(\s*)((?:with\s+\w+|,\s*\w+)\s+as)\s*\((.+)$',
            line,
            re.IGNORECASE,
        )
        if m2:
            ws, name_as, content = m2.group(1), m2.group(2), m2.group(3)
            has_nl = line.endswith('\n')
            if has_nl and content.endswith('\n'):
                content = content[:-1]
            suf = '\n' if has_nl else ''
            indent = len(ws)
            new_lines.append(ws + name_as + suf)
            new_lines.append(' ' * indent + '(' + suf)
            new_lines.append(' ' * (indent + SUBQUERY_INDENT) + content.lstrip() + suf)
            continue
        new_lines.append(line)
    return new_lines


def align_create_table_tail(lines: List[str]) -> List[str]:
    """将 CREATE TABLE 闭合 ``)`` 之后到 ``;`` 之间的表属性子句与 ``create`` 行首对齐。"""
    new_lines = lines.copy()
    i = 0
    while i < len(new_lines):
        if re.match(r'^\s*create\s+table\b', new_lines[i], re.IGNORECASE):
            create_indent = len(new_lines[i]) - len(new_lines[i].lstrip())
            paren_depth = 0
            j = i
            close_line = -1
            while j < len(new_lines):
                paren_depth += new_lines[j].count('(') - new_lines[j].count(')')
                if paren_depth == 0 and j > i:
                    close_line = j
                    break
                j += 1
            if close_line < 0:
                i += 1
                continue
            k = close_line + 1
            while k < len(new_lines):
                stripped = new_lines[k].strip()
                if not stripped:
                    k += 1
                    continue
                if stripped == ';' or stripped.endswith(';'):
                    has_nl = new_lines[k].endswith('\n')
                    new_lines[k] = ' ' * create_indent + stripped + ('\n' if has_nl else '')
                    break
                has_nl = new_lines[k].endswith('\n')
                new_lines[k] = ' ' * create_indent + stripped + ('\n' if has_nl else '')
                k += 1
            i = k + 1
        else:
            i += 1
    return new_lines


def detect_create_table_blocks(lines: List[str]) -> List[Tuple[int, int, str]]:
    """检测文件中的 CREATE TABLE 语句块"""
    blocks = []
    in_create_table = False
    table_start = -1
    table_name = ""
    paren_count = 0

    for i, line in enumerate(lines):
        stripped = line.strip().lower()

        if re.match(r'^create\s+table', stripped):
            in_create_table = True
            table_start = i
            table_match = re.search(r'create\s+table\s+(?:if\s+not\s+exists\s+)?(\S+)', line, re.IGNORECASE)
            if table_match:
                table_name = table_match.group(1)

        if in_create_table:
            paren_count += line.count('(') - line.count(')')

            if paren_count == 0 and table_start != i:
                blocks.append((table_start, i, table_name))
                in_create_table = False
                table_start = -1
                table_name = ""

    return blocks


def analyze_create_table_block(lines: List[str], start: int, end: int) -> Dict:
    """分析 CREATE TABLE 块中的列定义"""
    columns = []

    for i in range(start, min(end + 1, len(lines))):
        line = lines[i]
        column_name, data_type, comment_text, original = parse_create_table_column(line)

        if column_name:
            columns.append({
                'line_num': i,
                'column_name': column_name,
                'column_len': len(column_name),
                'data_type': data_type,
                'data_type_len': len(data_type),
                'comment_text': comment_text,
                'original': original
            })

    return {
        'columns': columns,
        'max_column_len': max([c['column_len'] for c in columns]) if columns else 0,
        'max_datatype_len': max([c['data_type_len'] for c in columns]) if columns else 0
    }


def align_create_table_columns(lines: List[str], columns: List[Dict],
                                datatype_col: int, comment_col: int) -> List[str]:
    """对齐建表语句的列定义"""
    new_lines = lines.copy()

    for idx, col in enumerate(columns):
        line_num = col['line_num']
        old_line = new_lines[line_num]

        # 第一个字段（idx==0）不加逗号，其余字段都加逗号前置
        # 统一使用固定的缩进，不保留原始文件的缩进
        if idx == 0:
            # 第一个字段前面留2个空格（模拟逗号+空格的长度），保证与后续字段的字段名对齐
            prefix = '  '
        else:
            # 其他字段都加逗号前置，从行首开始（0空格）
            prefix = ', '

        current_pos = len(prefix) + len(col['column_name'])
        spaces_to_datatype = datatype_col - current_pos
        if spaces_to_datatype < 1:
            spaces_to_datatype = 1

        current_pos = datatype_col + len(col['data_type'])
        spaces_to_comment = comment_col - current_pos
        if spaces_to_comment < 1:
            spaces_to_comment = 1

        has_newline = old_line.endswith('\n')
        new_line = (prefix +
                   col['column_name'] +
                   ' ' * spaces_to_datatype +
                   col['data_type'] +
                   ' ' * spaces_to_comment +
                   'comment ' +
                   col['comment_text'])
        if has_newline:
            new_line += '\n'

        new_lines[line_num] = new_line

    return new_lines


def verify_create_table_alignment(lines: List[str], start: int, end: int) -> bool:
    """验证 CREATE TABLE 块的对齐情况"""
    result = analyze_create_table_block(lines, start, end)
    columns = result['columns']

    if not columns:
        return True

    column_name_positions = []
    datatype_positions = []
    comment_positions = []

    for col in columns:
        line = lines[col['line_num']]

        # 检查字段名首字母位置（反引号列名两侧非 \w，\b 不适用）
        if col['column_name'].startswith('`'):
            column_match = re.search(re.escape(col['column_name']), line)
        else:
            column_match = re.search(r'\b' + re.escape(col['column_name']) + r'\b', line)
        if column_match:
            column_name_positions.append(column_match.start())

        datatype_match = re.search(r'(' + re.escape(col['data_type']) + r')\s+comment', line, re.IGNORECASE)
        if datatype_match:
            datatype_positions.append(datatype_match.start())

        comment_match = re.search(r'(comment)\s+', line, re.IGNORECASE)
        if comment_match:
            comment_positions.append(comment_match.start())

    # 检查字段名首字母是否对齐
    if len(set(column_name_positions)) > 1:
        return False
    if len(set(datatype_positions)) > 1:
        return False
    if len(set(comment_positions)) > 1:
        return False

    max_col_len = result['max_column_len']
    if datatype_positions:
        first_datatype_pos = datatype_positions[0]
        min_required_pos = 2 + 2 + max_col_len + 6
        if first_datatype_pos < min_required_pos:
            return False

    return True


def format_sql_file(input_file: str, verify_only: bool = False,
                   as_only: bool = False, table_only: bool = False, char_mode: bool = True,
                   cjk_width: float = 2.0):
    """格式化 SQL 文件的对齐"""
    global USE_CHAR_MODE, CJK_WIDTH_RATIO
    USE_CHAR_MODE = char_mode
    CJK_WIDTH_RATIO = cjk_width

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print(f"{'='*70}")
    print(f"SQL 代码对齐工具 v3.1.1")
    print(f"{'='*70}")
    print(f"文件: {input_file}")
    print(f"总行数: {len(lines)}")
    print(f"模式: {'验证' if verify_only else '格式化'}")
    if as_only:
        print(f"范围: 仅 AS 对齐")
    elif table_only:
        print(f"范围: 仅建表语句对齐")
    else:
        print(f"范围: 全部对齐（AS + 建表语句）")
    print(f"{'='*70}\n")

    # 预处理阶段
    if not verify_only:
        print("【预处理】代码规范化")
        print("="*70)

        # 0-pre-a. CREATE TABLE 行尾 ( 拆到下一行独占
        original_lines = lines.copy()
        lines = split_create_table_open_paren(lines)
        paren_split = len(lines) - len(original_lines)
        if paren_split > 0:
            print(f"✅ 拆分建表语句行尾 ( 到独立行，新增 {paren_split} 行")

        # 0-pre-a2. CTE with/逗号 name as ( 行尾 ( 拆到独立行
        original_lines = lines.copy()
        lines = split_cte_as_open_paren(lines)
        cte_paren_split = len(lines) - len(original_lines)
        if cte_paren_split > 0:
            print(f"✅ 拆分 CTE as ( 行尾 ( 到独立行，新增 {cte_paren_split} 行")

        # 0-pre-b. CREATE TABLE 闭合括号后的表属性子句与 create 行首对齐
        original_lines = lines.copy()
        lines = align_create_table_tail(lines)
        tail_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if tail_count > 0:
            print(f"✅ 对齐 {tail_count} 行建表尾部子句（COMMENT/PARTITIONED/stored）")

        # 0-pre-c0. create table … as 后的主导 select 顶格
        original_lines = lines.copy()
        lines = flush_select_after_create_table_as(lines)
        flush_ctas = sum(1 for k in range(len(lines)) if k < len(original_lines) and lines[k] != original_lines[k])
        if flush_ctas > 0:
            print(f"✅ CTAS 后主导 select 顶格 {flush_ctas} 行")

        # 0-pre-c. SQL 关键字/函数名小写
        original_lines = lines.copy()
        lines = lowercase_sql_keywords(lines)
        kw_lower_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if kw_lower_count > 0:
            print(f"✅ 小写化 {kw_lower_count} 行的 SQL 关键字/函数名")

        # 0. 标准化运算符空格
        original_lines = lines.copy()
        lines = normalize_operator_spacing(lines)
        operator_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if operator_count > 0:
            print(f"✅ 标准化 {operator_count} 行的运算符空格")

        # 0.1 关键字后多余空格压缩为单空格
        original_lines = lines.copy()
        lines = normalize_keyword_spacing(lines)
        kw_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if kw_count > 0:
            print(f"✅ 压缩 {kw_count} 行关键字后多余空格")

        # 1. 修复 select as 错误
        original_lines = lines.copy()
        lines = fix_select_as_error(lines)
        select_as_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if select_as_count > 0:
            print(f"✅ 修复 {select_as_count} 处 'select as field' 错误")

        # 1.5 补充表别名的 AS 关键字
        original_lines = lines.copy()
        lines = add_table_alias_as_keyword(lines)
        alias_as_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if alias_as_count > 0:
            print(f"✅ 补充 {alias_as_count} 处表别名的 AS 关键字")

        # 2. 将第一个字段合并到 SELECT 行
        original_lines = lines.copy()
        lines = merge_first_field_to_select(lines)
        merge_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if merge_count > 0:
            print(f"✅ 合并 SELECT 首字段到同一行，调整 {merge_count} 行")

        # 2.15 ``select`` 与首字段间多个空格压成单空格（须在逗号处理与子查询对齐之前）
        original_lines = lines.copy()
        lines = normalize_select_keyword_spacing(lines)
        if lines != original_lines:
            print("✅ 规范 select 与首列之间的空格为单空格")

        # 2.4 在逗号后添加空格（必须在合并CASE WHEN之前，确保case_indent计算准确）
        original_lines = lines.copy()
        lines = add_space_after_commas(lines)
        comma_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if comma_count > 0:
            print(f"✅ 在 {comma_count} 行逗号后添加空格")

        # 2.45 聚合行末 ``(`` 与下一行 ``case when`` 合并到同一行（如 ``max(case when ...``）
        original_lines = lines.copy()
        lines = merge_aggregate_open_paren_case_when_same_line(lines)
        if lines != original_lines:
            print("✅ 聚合函数开括号与 case when 合并同一行")

        # 2.5 合并 CASE WHEN 格式
        original_lines = lines.copy()
        lines = merge_case_when(lines)
        case_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if case_count > 0:
            print(f"✅ 合并 CASE WHEN 格式，调整 {case_count} 行")

        # 2.6 拆分 from/join ( 和 from/join (select ... 到独立行（须在逗号前置转换之前，否则拆出的行尾逗号不会被处理）
        original_lines = lines.copy()
        lines = split_from_join_open_paren(lines)
        fj_split = len(lines) - len(original_lines)
        if fj_split > 0:
            print(f"✅ 拆分 from/join ( 到独立行，新增 {fj_split} 行")

        # 2.65 单行 ``select a, b from … [where …]`` 拆行（行尾逗号），否则 ``convert_to_leading_comma`` 无法处理选列内逗号
        original_lines = lines.copy()
        lines = split_dense_select_list_same_line(lines)
        if lines != original_lines:
            print("✅ 拆分单行 select 多列 + from/where，便于句首逗号")

        # 2.7 转换逗号后置为逗号前置
        original_lines = lines.copy()
        lines = convert_to_leading_comma(lines)
        comma_convert_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if comma_convert_count > 0:
            print(f"✅ 转换 {comma_convert_count} 行逗号为前置格式")

        # 3. 自动补充缺失的AS关键字
        original_lines = lines.copy()
        lines = add_missing_as_keywords(lines)
        as_count = 0
        for i in range(len(lines)):
            if i < len(original_lines):
                old_has_as = re.search(r'\s+as\s+\w+', original_lines[i], re.IGNORECASE)
                new_has_as = re.search(r'\s+as\s+\w+', lines[i], re.IGNORECASE)
                if new_has_as and not old_has_as:
                    as_count += 1
        if as_count > 0:
            print(f"✅ 补充 {as_count} 个缺失的 AS 关键字")

        # 3.02 ``) as alias`` 下一行若仅为 join，行首与 ``)`` 同列（须在 align_subquery_brackets 之前）
        original_lines = lines.copy()
        lines = align_join_after_subquery_close(lines)
        join_alias_count = sum(
            1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i]
        )
        if join_alias_count > 0:
            print(f"✅ 校正 {join_alias_count} 行子查询闭合后的 join 缩进")

        # 3.03 预拆分 `) alias on/where condition` 确保子查询闭合行干净（须在 align_subquery_brackets 之前）
        original_lines = lines.copy()
        lines = split_inline_join_on_lines(lines)
        pre_split_extra = len(lines) - len(original_lines)
        if pre_split_extra > 0:
            print(f"✅ 预拆分 ) alias on/where，新增 {pre_split_extra} 行（为括号对齐做准备）")

        # 3.021 ``on`` / ``where`` 独占一行时合并下一行条件，避免 ON 续行与 where 谓词缩进错位
        original_lines = lines.copy()
        lines = merge_lonely_on_with_next_line(lines)
        if lines != original_lines:
            print("✅ 合并独占一行的 on 与下一行条件")
        original_lines = lines.copy()
        lines = merge_lonely_where_having_with_next_line(lines)
        if lines != original_lines:
            print("✅ 合并独占一行的 where/having 与下一行谓词")

        # 3. 对齐子查询括号（必须在字段名对齐之前）
        original_lines = lines.copy()
        lines = align_subquery_brackets(lines)
        bracket_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if bracket_count > 0:
            print(f"✅ 对齐 {bracket_count} 行子查询括号及内容（含内部迭代至稳定）")

        original_lines = lines.copy()
        lines = fix_open_paren_indent_after_lone_from(lines)
        if lines != original_lines:
            print("✅ 校正 from 后独占一行的左括号缩进")

        # 3.015 子查询对齐后再收敛 ``) as`` 后的 join 行（否则二轮 align 会把 ``left join`` 多推一档）
        original_lines = lines.copy()
        lines = align_join_after_subquery_close(lines)
        if lines != original_lines:
            print("✅ 二次校正子查询闭合后的 join 缩进")

        # 3.5 合并 FROM 后表名到同一行
        original_lines = lines.copy()
        lines = merge_from_table(lines)
        from_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if from_count > 0:
            print(f"✅ 合并 FROM 表名到同一行，调整 {from_count} 行")

        # 3.55 合并 JOIN 后表名到同一行（与 merge_from_table 对称）
        original_lines = lines.copy()
        lines = merge_join_table(lines)
        join_merge_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if join_merge_count > 0:
            print(f"✅ 合并 JOIN 表名到同一行，调整 {join_merge_count} 行")

        # 4. 对齐字段名首字母
        original_lines = lines.copy()
        lines = align_field_names(lines)
        field_align_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if field_align_count > 0:
            print(f"✅ 对齐 {field_align_count} 行字段名首字母")

        # 4.01 WITH 链 ``, cte as (`` 与 ``with`` 同列（修正误当 SELECT 逗号列的多缩进）
        original_lines = lines.copy()
        lines = fix_with_cte_comma_indent(lines)
        cte_comma_count = sum(
            1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i]
        )
        if cte_comma_count > 0:
            print(f"✅ 校正 {cte_comma_count} 行 WITH 链逗号缩进")

        # 4.015 ``fix_with_cte_comma_indent`` 会将 ``name as (`` 拆成 ``, name as`` 与独占 ``(``，
        # 须在拆分后再次对齐子查询，方能使 CTE 第一层体套用与 ``from/join`` 相同的「定义行首列 + 6」锚定。
        original_lines = lines.copy()
        lines = align_subquery_brackets(lines)
        bracket_count_cte = sum(
            1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i]
        )
        if bracket_count_cte > 0:
            print(f"✅ CTE 拆行后第三次对齐子查询括号，调整 {bracket_count_cte} 行")

        # 4.5 CASE：case/end 同列，when/else 同列（在子查询与字段对齐之后再收敛一次）
        original_lines = lines.copy()
        lines = align_case_when_columns(lines)
        case_col_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if case_col_count > 0:
            print(f"✅ 统一 {case_col_count} 行 CASE 块 when/else/end 列对齐")

        # 4.55 跨行圆括号：) 与匹配 ( 同列（忽略引号/注释内括号；仅闭行前全空白时改写）
        original_lines = lines.copy()
        lines = align_cross_line_parens(lines)
        paren_align_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if paren_align_count > 0:
            print(f"✅ 对齐 {paren_align_count} 行跨行圆括号")

        # 4.555 ``group by grouping sets`` 多行块：首组并入 ``(`` 后；``, (`` 与首组 ``(`` 同列；``)`` 与 ``grouping sets (`` 配对左括号同列
        original_lines = lines.copy()
        lines = align_grouping_sets_layout(lines)
        if lines != original_lines:
            print("✅ 已应用 grouping sets 布局调整")

        # 4.56 ``union all`` 子链：``(``/``select``/``from``/``union``/``) as`` 与首节 ``select`` 同列（须在跨行括号之后）
        original_lines = lines.copy()
        lines = align_union_branch_keyword_column(lines)
        union_kw_count = sum(
            1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i]
        )
        if union_kw_count > 0:
            print(f"✅ 对齐 {union_kw_count} 行 UNION 子链关键字列")

        # 4.556 UNION 链后逗号列重算已收进 ``align_union_branch_keyword_column`` 末尾对 ``align_field_names`` 的调用。

        # 4.557 UNION 链改写 ``from`` 行首列后，``from`` 下一行独占 ``(`` 可能与新 ``from`` 不同列。
        original_lines = lines.copy()
        lines = align_grouping_sets_layout(lines)
        if lines != original_lines:
            print("✅ UNION 链后重算 grouping sets 布局")

        original_lines = lines.copy()
        lines = align_join_after_subquery_close(lines)
        if lines != original_lines:
            print("✅ UNION 链后修正 ) as 后 join 缩进")

        original_lines = lines.copy()
        lines = fix_open_paren_indent_after_lone_from(lines)
        if lines != original_lines:
            print("✅ UNION 链后修正 from 下一行括号缩进")

        # 5.8 同行 ``join … on`` / ``) as alias on`` 拆成两行（须在 align_where 之前）
        original_lines = lines.copy()
        lines = split_inline_join_on_lines(lines)
        join_on_extra_lines = len(lines) - len(original_lines)
        if join_on_extra_lines > 0:
            print(f"✅ 拆分内联 join…on / ) as … on，新增 {join_on_extra_lines} 行独立 ON")

        # 5.85 过长 ``on`` 条件按顶层 ``and`` 折行（须在 align_where 之前）
        original_lines = lines.copy()
        lines = split_long_on_conditions(lines)
        on_and_lines = len(lines) - len(original_lines)
        if on_and_lines > 0:
            print(f"✅ 拆分过长 ON 条件（按 and），新增 {on_and_lines} 行")

        # 5.9 拆分 where/having 行内的顶层 and/or 为独立行
        original_lines = lines.copy()
        lines = split_where_conditions(lines)
        where_split_extra = len(lines) - len(original_lines)
        if where_split_extra > 0:
            print(f"✅ 拆分 WHERE/HAVING 条件（按 and/or），新增 {where_split_extra} 行")

        # 6. 对齐 WHERE/JOIN 和 AND/OR/ON
        original_lines = lines.copy()
        lines = align_where_and_clauses(lines)
        where_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if where_count > 0:
            print(f"✅ 对齐 {where_count} 行 ON/AND/OR 与 JOIN/WHERE（含末尾 CASE 列再收敛）")

        # 6.25 ``align_where`` 后 CASE 再收敛已收进 ``align_where_and_clauses`` 返回前对 ``align_case_when_columns`` 的调用。

        # 6.5 修复子查询闭合括号后 ON 的缩进
        original_lines = lines.copy()
        lines = fix_subquery_on_indent(lines)
        on_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if on_count > 0:
            print(f"✅ 修复 {on_count} 行子查询 ON 的缩进")

        # 6.6 整行 ``--`` 注释对齐改在 AS 对齐之后执行（见 ``format_sql_file`` 内 ``align_comments``）

        # 7. 删除空行
        original_count = len(lines)
        lines = remove_empty_lines(lines)
        removed_count = original_count - len(lines)
        if removed_count > 0:
            print(f"✅ 删除 {removed_count} 个空行")

        # 7.5 函数参数折行对齐（续行逗号对齐到函数名末字符列，非逗号对齐到首参数列）
        original_lines = lines.copy()
        lines = align_function_arg_continuations(lines)
        func_arg_count = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if func_arg_count > 0:
            print(f"✅ 对齐 {func_arg_count} 行函数参数续行")

        # 7.6 函数参数折行可能移动了 case when 首行，须重新收敛 CASE 列
        original_lines = lines.copy()
        lines = align_case_when_columns(lines)
        case_reconv = sum(1 for i in range(len(lines)) if i < len(original_lines) and lines[i] != original_lines[i])
        if case_reconv > 0:
            print(f"✅ 函数参数对齐后 CASE WHEN 列再收敛 {case_reconv} 行")

        print(f"\n{'='*70}\n")

    modified_lines = compact_close_paren_as_alias_lines(lines.copy())
    all_aligned = True

    if not table_only:
        print("【1/3】处理 AS 对齐")
        print("="*70)
        select_blocks = detect_select_blocks(lines)
        print(f"检测到 {len(select_blocks)} 个 SELECT 块\n")

        for start, end, name in select_blocks:
            print(f"\n{'-'*70}")
            print(f"处理: {name} (行 {start+1}-{end+1})")
            print(f"{'-'*70}")

            result = analyze_select_block(modified_lines, start, end)

            if not result['all']:
                print("  (无 AS 别名)")
                continue

            if select_block_unify_as_by_head_char_span(modified_lines, start, end):
                all_fields = result["all"]
                print(
                    f"\n  选列头行字符极差 ≤ {SELECT_AS_UNIFY_HEAD_CHAR_SPAN_MAX}：整块 AS 统一对齐（{len(all_fields)} 个字段）"
                )
                current_positions = set(f["as_pos"] for f in all_fields)
                target_col = calculate_target_as_column(all_fields)
                if len(current_positions) == 1:
                    current_col = list(current_positions)[0]
                    if current_col == target_col:
                        print(f"    ✅ 已统一对齐在第 {current_col} 列")
                        if not verify_only:
                            modified_lines = align_fields_in_place(
                                modified_lines, all_fields, target_col, start
                            )
                    else:
                        print(
                            f"    ⚠️  已对齐但位置不对: 当前第 {current_col} 列，应为第 {target_col} 列"
                        )
                        all_aligned = False
                        if not verify_only:
                            print(f"    🔧 重新对齐到第 {target_col} 列...")
                            modified_lines = align_fields_in_place(
                                modified_lines, all_fields, target_col, start
                            )
                            print(f"    ✅ 已完成对齐")
                else:
                    print(f"    ⚠️  未对齐: AS位置 = {sorted(current_positions)}")
                    all_aligned = False
                    if not verify_only:
                        print(f"    🔧 对齐到第 {target_col} 列...")
                        modified_lines = align_fields_in_place(
                            modified_lines, all_fields, target_col, start
                        )
                        print(f"    ✅ 已完成对齐")
            else:
                for gi, group in enumerate(result['groups']):
                    if not group:
                        continue

                    print(f"\n  分组 {gi+1}: {len(group)} 个字段")

                    current_positions = set(f['as_pos'] for f in group)
                    target_col = calculate_target_as_column(group)

                    if len(current_positions) == 1:
                        current_col = list(current_positions)[0]
                        if current_col == target_col:
                            print(f"    ✅ 已对齐在第 {current_col} 列")
                            # 即使AS已对齐，也需要统一逗号缩进
                            if not verify_only:
                                modified_lines = align_fields_in_place(modified_lines, group, target_col, start)
                        else:
                            print(f"    ⚠️  已对齐但位置不对: 当前第 {current_col} 列，应为第 {target_col} 列")
                            all_aligned = False
                            if not verify_only:
                                print(f"    🔧 重新对齐到第 {target_col} 列...")
                                modified_lines = align_fields_in_place(modified_lines, group, target_col, start)
                                print(f"    ✅ 已完成对齐")
                    else:
                        print(f"    ⚠️  未对齐: AS位置 = {sorted(current_positions)}")
                        all_aligned = False

                        if not verify_only:
                            print(f"    🔧 对齐到第 {target_col} 列...")
                            modified_lines = align_fields_in_place(modified_lines, group, target_col, start)
                            print(f"    ✅ 已完成对齐")

        print(f"\n{'='*70}\n")

    if not verify_only:
        modified_lines = compact_close_paren_as_alias_lines(modified_lines)
        _cmt_before = modified_lines.copy()
        modified_lines = align_comments(modified_lines)
        _cmt_n = sum(
            1
            for i in range(len(modified_lines))
            if i < len(_cmt_before) and modified_lines[i] != _cmt_before[i]
        )
        if _cmt_n > 0:
            print(f"✅ AS 后对齐整行注释，调整 {_cmt_n} 行")

    if not as_only:
        print("【2/3】处理建表语句对齐")
        print("="*70)
        create_table_blocks = detect_create_table_blocks(modified_lines)
        print(f"检测到 {len(create_table_blocks)} 个 CREATE TABLE 语句\n")

        for start, end, table_name in create_table_blocks:
            print(f"\n{'-'*70}")
            print(f"处理: {table_name} (行 {start+1}-{end+1})")
            print(f"{'-'*70}")

            result = analyze_create_table_block(modified_lines, start, end)
            columns = result['columns']

            if not columns:
                print("  (无列定义)")
                continue

            max_col_len = result['max_column_len']
            max_datatype_len = result['max_datatype_len']

            print(f"  列数: {len(columns)}")
            print(f"  最长列名: {max_col_len} 字符")
            print(f"  最长数据类型: {max_datatype_len} 字符")

            datatype_col = 2 + 2 + max_col_len + 6
            comment_col = datatype_col + max_datatype_len + 1

            print(f"  目标数据类型列: 第 {datatype_col} 列")
            print(f"  目标 COMMENT 列: 第 {comment_col} 列")

            is_aligned = verify_create_table_alignment(modified_lines, start, end)

            if is_aligned:
                print(f"  ✅ 已对齐")
            else:
                print(f"  ⚠️  未对齐")
                all_aligned = False

                if not verify_only:
                    print(f"  🔧 正在对齐...")
                    modified_lines = align_create_table_columns(modified_lines, columns,
                                                               datatype_col, comment_col)
                    print(f"  ✅ 已完成对齐")

        print(f"\n{'='*70}\n")

    print(f"{'='*70}")

    if verify_only:
        if all_aligned:
            print("🎉 验证通过：所有代码都已正确对齐！")
            return True
        else:
            print("⚠️  验证失败：存在未对齐的代码")
            print("提示：运行不带 --verify-only 参数来自动修正")
            return False
    else:
        with open(input_file, 'w', encoding='utf-8') as f:
            f.writelines(modified_lines)

        print("✅ 格式化完成！")
        print(f"已保存到: {input_file}")

        # 验证SQL关键字完整性（防止丢失SELECT/FROM等）
        print(f"\n{'-'*70}")
        print("验证SQL语法完整性...")
        print(f"{'-'*70}")
        if not verify_sql_keywords(lines, modified_lines):
            print("❌ 错误：格式化后SQL关键字数量不匹配，可能破坏了原逻辑！")
            print("提示：请检查 align_subquery_brackets 或其他预处理函数")
            return False
        else:
            print("  ✅ 所有SQL关键字完整")

        # 验证注释内容完整性（防止修改注释文本）
        if not verify_comments_content(lines, modified_lines):
            print("❌ 错误：格式化后注释内容被修改，违反了硬约束！")
            print("提示：仅允许调整注释行首缩进，不得修改注释文本内容")
            return False
        else:
            print("  ✅ 所有注释内容未修改")

        print(f"\n{'-'*70}")
        print("验证对齐结果...")
        print(f"{'-'*70}")

        verification_passed = True

        if not table_only:
            select_blocks = detect_select_blocks(modified_lines)
            for start, end, name in select_blocks:
                is_aligned = verify_select_alignment(modified_lines, start, end)
                status = "✅" if is_aligned else "⚠️ "
                print(f"  {status} {name}: {'对齐正确' if is_aligned else '仍有问题'}")
                if not is_aligned:
                    verification_passed = False

        if not as_only:
            create_table_blocks = detect_create_table_blocks(modified_lines)
            for start, end, table_name in create_table_blocks:
                is_aligned = verify_create_table_alignment(modified_lines, start, end)
                status = "✅" if is_aligned else "⚠️ "
                print(f"  {status} {table_name}: {'对齐正确' if is_aligned else '仍有问题'}")
                if not is_aligned:
                    verification_passed = False

        print(f"\n{'='*70}")
        if verification_passed:
            print("🎉🎉🎉 完美！所有代码都已正确对齐！")
        else:
            print("⚠️  部分代码仍有问题，可能需要手动调整")
        print(f"{'='*70}")

        return verification_passed


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法:")
        print("  格式化全部:      python sql_aligner.py <file.sql>")
        print("  验证全部:        python sql_aligner.py <file.sql> --verify-only")
        print("  仅 AS 对齐:      python sql_aligner.py <file.sql> --as-only")
        print("  仅建表语句对齐:  python sql_aligner.py <file.sql> --table-only")
        print("  字符位置模式:    python sql_aligner.py <file.sql> --char-mode")
        print("  自定义CJK宽度:   python sql_aligner.py <file.sql> --cjk-width 1.5")
        print("  组合使用:        python sql_aligner.py <file.sql> --as-only --verify-only")
        print("")
        print("说明:")
        print("  --cjk-width: 设置中文字符宽度比例（默认2.0）")
        print("               - 2.0: 标准终端显示（推荐）")
        print("               - 1.5: PyCharm部分字体配置")
        print("               - 1.0: 等同于--char-mode")
        sys.exit(1)

    input_file = sys.argv[1]
    verify_only = '--verify-only' in sys.argv
    as_only = '--as-only' in sys.argv
    table_only = '--table-only' in sys.argv
    char_mode = '--char-mode' in sys.argv

    # 解析 --cjk-width 参数
    cjk_width = 2.0
    for i, arg in enumerate(sys.argv):
        if arg == '--cjk-width' and i + 1 < len(sys.argv):
            try:
                cjk_width = float(sys.argv[i + 1])
                if cjk_width <= 0 or cjk_width > 2:
                    print("❌ 错误: --cjk-width 必须在 0 到 2 之间")
                    sys.exit(1)
            except ValueError:
                print("❌ 错误: --cjk-width 参数必须是数字")
                sys.exit(1)

    if as_only and table_only:
        print("❌ 错误: --as-only 和 --table-only 不能同时使用")
        sys.exit(1)

    try:
        format_sql_file(input_file, verify_only, as_only, table_only, char_mode, cjk_width)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
