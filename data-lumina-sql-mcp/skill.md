---
name: data-lumina-sql-mcp
description: >
  当用户想要查询数据、浏览数据库、查看表结构、执行SQL、分析业务数据时使用此skill。
  触发关键词包括："查数据"、"跑SQL"、"查表"、"看数据"、"数据源"、"表结构"、"字段信息"、
  "数据分析"、"数仓查询"，以及配置或连接 lumina-sql-mcp-server 的请求。
  也适用于用户询问如何申请 API Key、配置 MCP 服务、获取令牌、连接 DataLumina 平台等场景。
---

# Lumina SQL MCP Server - 数据查询 Skill

你正在帮助用户通过 **lumina-sql-mcp-server** MCP 服务查询企业数据仓库。该服务提供 7 个工具用于元数据浏览和 SQL 执行。请严格遵循以下工作流程和规则。

## MCP 连接配置

MCP 服务按国家/地区区分，每个国家有独立的服务地址和数据源。请根据用户要查询的数据所在国家选择对应配置。

### 各国服务地址

| 国家/地区 | 服务名 | URL | DataLumina 平台地址 |
|-----------|--------|-----|---------------------|
| 中国 (CN) | `lumina-sql-cn` | `https://datalumina.fintopia.tech/mcp/sql` | `https://datalumina.fintopia.tech` |
| 印尼 (INDO) | `lumina-sql-indo` | `https://datalumina.easycash.id/mcp/sql` | `https://datalumina.easycash.id` |
| 西班牙 (ESP) | `lumina-sql-esp` | `https://datalumina.creditoya.com.es/mcp/sql` | `https://datalumina.creditoya.com.es` |
| 墨西哥 (MEX) | `lumina-sql-mex` | `https://datalumina-mex.fintopia.tech/mcp/sql` | `https://datalumina-mex.fintopia.tech` |

### 第一步：申请 API Key

1. 打开对应国家的 **DataLumina 平台**（见上表"平台地址"列）
2. 登录后进入 **AI → 令牌管理** 页面
3. 点击 **创建令牌**，填写令牌名称（如 "cursor-mcp"）
4. 创建成功后，**立即复制并妥善保存令牌值**（令牌只在创建时显示一次，关闭后无法再查看）
5. 如果需要查询多个国家的数据，需分别在各国平台申请对应的 API Key

### 第二步：配置 MCP 客户端

按需添加对应国家的配置（可同时配置多个国家）。以下分别提供 Cursor 和 Claude Code 的配置方式。

#### Cursor 配置

在项目根目录创建或编辑 `.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "lumina-sql-cn": {
      "url": "https://datalumina.fintopia.tech/mcp/sql",
      "headers": { "X-API-Key": "<your-api-token>" }
    },
    "lumina-sql-indo": {
      "url": "https://datalumina.easycash.id/mcp/sql",
      "headers": { "X-API-Key": "<your-api-token>" }
    },
    "lumina-sql-esp": {
      "url": "https://datalumina.creditoya.com.es/mcp/sql",
      "headers": { "X-API-Key": "<your-api-token>" }
    },
    "lumina-sql-mex": {
      "url": "https://datalumina-mex.fintopia.tech/mcp/sql",
      "headers": { "X-API-Key": "<your-api-token>" }
    }
  }
}
```

#### Claude Code 配置

在项目的 `.claude/` 目录或用户级 `~/.claude/` 目录下创建或编辑 `.mcp.json`：

- **项目级**：`<project-root>/.claude/.mcp.json`
- **用户级**：`~/.claude/.mcp.json`

```json
{
  "mcpServers": {
    "lumina-sql-cn": {
      "url": "https://datalumina.fintopia.tech/mcp/sql",
      "headers": { "X-API-Key": "<your-api-token>" }
    },
    "lumina-sql-indo": {
      "url": "https://datalumina.easycash.id/mcp/sql",
      "headers": { "X-API-Key": "<your-api-token>" }
    },
    "lumina-sql-esp": {
      "url": "https://datalumina.creditoya.com.es/mcp/sql",
      "headers": { "X-API-Key": "<your-api-token>" }
    },
    "lumina-sql-mex": {
      "url": "https://datalumina-mex.fintopia.tech/mcp/sql",
      "headers": { "X-API-Key": "<your-api-token>" }
    }
  }
}
```

> **注意**：
> - 每个国家的 `<your-api-token>` 需替换为在该国 DataLumina 平台申请到的令牌。不同国家的令牌不通用。
> - 只需查询单个国家时，只配置对应国家的服务即可，无需全部添加。
> - Claude Code 的 `.mcp.json` 文件需放在 `.claude/` 目录下（项目级或用户级），而非项目根目录。
> - Cursor 使用 `.cursor/mcp.json`，Claude Code 使用 `.claude/.mcp.json`，两者路径和格式略有不同。

### 常见配置问题

- **连接失败 / 401 Unauthorized**：检查 API Key 是否正确、是否过期，前往对应平台的"令牌管理"页面确认令牌状态
- **工具未出现在可用列表**：确认配置文件路径正确，Cursor 重启后生效；Claude Code 重新启动会话后生效
- **多国数据联合查询**：不支持跨国 JOIN，需分别在各国服务中查询后自行合并

## 标准工作流程（必须按此顺序执行）

### 第一步：发现数据源
调用 `list_data_sources` 获取所有可用数据源及其 ID 和支持的引擎列表。

### 第二步：浏览元数据（按需）
- `list_databases(dataSourceId)` — 列出数据源下的所有数据库
- `list_tables(dataSourceId, database)` — 列出数据库下的所有表（含注释）
- `get_columns(dataSourceId, database, table)` — 获取表的列元数据（名称、类型、注释）

**写 SQL 之前必须先调用 `get_columns`**，确认列名和数据类型。

### 第三步：提交查询
调用 `submit_query(dataSourceId, engineType, sql, database?)` 提交 SQL 异步执行，立即返回 `queryId`。

### 第四步：轮询状态
调用 `get_query_status(queryId)` 检查执行进度，可能的状态：
- **RUNNING** — 仍在执行（含进度百分比）
- **FINISHED** — 执行完成，可获取结果
- **FAILED** — 执行失败，查看 message 字段获取错误详情

### 第五步：获取结果
状态为 FINISHED 后，调用 `get_query_result(queryId, maxRows?)` 获取数据。检查返回的 `truncated` 字段——如果为 true，需优化 SQL 添加 LIMIT 或聚合。

## 引擎选择规则

| 引擎 | 适用场景 |
|------|---------|
| **SMART**（推荐默认） | 自动路由：优先使用 DORIS，不可用时回退到 KYUUBI_SPARK |
| DORIS | 针对 StarRocks/Doris 表的快速 OLAP 查询 |
| KYUUBI_SPARK | 大规模 Hive/Spark 查询 |

**除非用户特别指定或数据源不支持，否则始终优先使用 SMART 引擎。**

## SQL 编写规则（HiveQL 方言）

本服务使用 **HiveQL 语法**，与标准 SQL 的主要差异：

1. **保留字** — 必须用反引号包裹：`` `date` ``、`` `user` ``、`` `order` ``、`` `group` ``
2. **字符串函数** — `concat()`、`substr()`、`regexp_replace()`、`split()`
3. **日期函数** — `date_format()`、`datediff()`、`date_add()`、`to_date()`
4. **数组展开** — 使用 `LATERAL VIEW explode()`，而非 UNNEST
5. **数组/Map长度** — 使用 `SIZE()`，而非 `LENGTH()`
6. **只读查询** — 不支持 UPDATE/DELETE/INSERT，仅支持 SELECT
7. **必须加 LIMIT** — 控制结果大小，避免超时

## 结果限制

- 单次查询最多返回 **10,000 行**
- 响应体最大 **1MB**
- 如果结果被截断，优化方式：
  - 添加更精确的 WHERE 条件
  - 使用聚合查询（GROUP BY、COUNT、SUM 等）
  - 减小 LIMIT 值

## 错误处理

- `submit_query` 返回无效引擎错误时，重新调用 `list_data_sources` 确认支持的引擎
- 查询 FAILED 时，阅读错误信息修正 SQL（常见问题：列名错误、语法错误、保留字未加反引号）
- 结果被截断时，应添加聚合或更严格的过滤条件，而非单纯增大 LIMIT
- 当返回结果包含"缺少权限（select），请到安全中心申请"等类似权限不足的提示时，说明用户当前账号没有该数据库/表的查询权限，需提示用户前往 **DataPilot平台的安全中心** 申请相应的数据权限后再重试

## 交互风格

- 展示查询结果时，格式化为易读的表格或摘要
- 尽可能从业务角度解释数据的含义
- 用户请求模糊时，先确认目标数据库/表再执行查询
- 当用户的查询可能返回过多数据时，主动建议添加聚合或过滤条件
