import pytest

from mcp_server.sql_guard import check_sql, has_partition_filter


@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "  with a as (select 1) select * from a",
    "SELECT * FROM `p.d.ads_daily_total` WHERE event_dt = '2020-12-28'",
    "SELECT page_title FROM t WHERE page_title = 'Update your cart; then delete'",
    "-- 先删掉 DROP 这个想法\nSELECT 1",
    "SELECT 1;",
    "(SELECT 1) UNION ALL (SELECT 2)",
    "SELECT * REPLACE (1 AS x) FROM t",
])
def test_allowed(sql):
    assert check_sql(sql)[0], sql


@pytest.mark.parametrize("sql", [
    "DELETE FROM t WHERE 1=1",
    "SELECT 1; DROP TABLE t",
    "/* SELECT */ DROP TABLE t",
    "CREATE TABLE x AS SELECT 1",
    "SELECT 1 FROM t WHERE x IN (SELECT 1); INSERT INTO t VALUES (1)",
    "DECLARE x INT64; SELECT x",
    "EXECUTE IMMEDIATE 'DROP TABLE t'",
    "MERGE t USING s ON TRUE WHEN MATCHED THEN DELETE",
    "",
])
def test_blocked(sql):
    assert not check_sql(sql)[0], sql


def test_partition_hint():
    assert has_partition_filter("SELECT * FROM t WHERE event_dt IN (DATE '2020-12-01')")
    assert not has_partition_filter("SELECT * FROM t -- WHERE event_dt = 1")
