from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pymysql


class DBClient:
    """
    企业级数据库客户端：
    - session 级复用基础连接参数
    - function 级独立连接 + 事务回滚
    - 支持常用查询封装
    """

    def __init__(self, host: str, port: int, user: str, password: str, database: str, charset: str = "utf8mb4"):
        self.conn_kwargs = {
            "host": host,
            "port": int(port),
            "user": user,
            "password": password,
            "database": database,
            "charset": charset,
            "cursorclass": pymysql.cursors.Cursor,
        }
        # 会话级常驻连接（只读查询场景）
        self.session_conn = self._new_connection(autocommit=True)

    def _new_connection(self, autocommit: bool) -> pymysql.connections.Connection:
        return pymysql.connect(autocommit=autocommit, **self.conn_kwargs)

    def query_first(self, sql: str, conn: pymysql.connections.Connection | None = None) -> Any:
        use_conn = conn or self.session_conn
        with use_conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            if row is None:
                return None
            if isinstance(row, (tuple, list)) and row:
                return row[0]
            return row

    @contextmanager
    def transaction(self) -> Iterator[pymysql.connections.Connection]:
        """
        function 级事务连接：
        - 用例中可执行增删改查
        - 结束统一 rollback，保证可重复、可并行
        """
        conn = self._new_connection(autocommit=False)
        try:
            yield conn
        finally:
            conn.rollback()
            conn.close()

    def close(self) -> None:
        self.session_conn.close()


# 向后兼容旧名
MysqlClient = DBClient
