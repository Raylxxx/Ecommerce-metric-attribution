"""run_sql 的安全护栏：只允许单条只读查询。

光用正则匹配开头的 SELECT 不够，下面这些情况我都踩过或者想到过：
- 注释里藏关键字：`-- DROP` 不应误杀；`/* */ DELETE ...` 不应放过；
- 字符串里有关键字：WHERE page_title = 'Update your cart' 不应误杀；
- 多条语句：`SELECT 1; DROP TABLE x` 必须拦住；
- 脚本语法：DECLARE / SET / EXECUTE IMMEDIATE / CALL 也算写操作或绕过手段。
所以先去掉注释和字符串字面量，再检查关键字。
"""

from __future__ import annotations

import re

FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|"
    r"DECLARE|SET|EXECUTE|CALL|EXPORT|LOAD|BEGIN|COMMIT|ROLLBACK)\b",
    re.I,
)
READ_ONLY_START = re.compile(r"^\s*\(*\s*(WITH|SELECT)\b", re.I)


def strip_comments_and_strings(sql: str) -> str:
    """去掉 -- / # 行注释、/* */ 块注释、以及 '...' "..." 字符串内容（保留引号占位）。"""
    out, i, n = [], 0, len(sql)
    while i < n:
        c = sql[i]
        if sql.startswith("--", i) or c == "#":
            j = sql.find("\n", i)
            i = n if j == -1 else j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j == -1 else j + 2
            out.append(" ")
        elif c in ("'", '"'):
            q, j = c, i + 1
            while j < n and sql[j] != q:
                j += 2 if sql[j] == "\\" else 1
            out.append(q + q)
            i = j + 1
        elif c == "`":
            # 反引号里是表名，整体换成占位符，避免表名里的单词被当成关键字
            j = sql.find("`", i + 1)
            j = n - 1 if j == -1 else j
            out.append("`T`")
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def check_sql(sql: str) -> tuple[bool, str]:
    """返回 (是否允许, 原因)。"""
    body = strip_comments_and_strings(sql).strip()
    if not body:
        return False, "空查询"
    stmts = [s for s in body.split(";") if s.strip()]
    if len(stmts) > 1:
        return False, "一次只能执行一条语句"
    if not READ_ONLY_START.match(stmts[0]):
        return False, "只允许 SELECT / WITH 开头的只读查询"
    m = FORBIDDEN.search(stmts[0])
    if m:
        return False, f"查询里包含不允许的关键字：{m.group(1).upper()}"
    return True, "ok"


def has_partition_filter(sql: str, partition_col: str = "event_dt") -> bool:
    """粗略判断查询有没有用分区字段过滤，没有的话我会在结果里提醒一句（不拦截）。"""
    body = strip_comments_and_strings(sql)
    return re.search(rf"\b{partition_col}\b\s*(=|IN|BETWEEN|>=|<=|>|<)", body, re.I) is not None
