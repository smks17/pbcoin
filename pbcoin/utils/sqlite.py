from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import sqlite3

from pbcoin.logger import getLogger


logging = getLogger(__name__)


class Sqlite:
    def __init__(self, db_path, connect=True, **kwargs):
        self.db_path = db_path
        if connect:
            self.connect(**kwargs)

    def connect(self, **kwargs):
        self._con = sqlite3.connect(self.db_path, **kwargs)
        self._cur = self._con.cursor()

    def create_table(self, name: str, columns: Dict[str, str], force: bool=True):
        BASE_COMMAND = "CREATE TABLE"
        args = [BASE_COMMAND]
        if force:
            args.append("IF NOT EXISTS")
        args.append(name)
        args.append("(")
        for i, c in enumerate(columns):
            args.append(c + " " + columns[c])
            if i != len(columns) - 1:
                args.append(",")
        args.append(")")
        self.execute(*args)

    def run_sql_file(self, filename: str):
        with open(filename, "r") as file:
            script = file.read()
        commands = script.split(";")
        for command in commands:
            self.execute(command)

    def insert(self, data: Dict[str, Any], table_name: str):
        keys = ",".join(list(data.keys()))
        values = []
        for key in data:
            v = data[key]
            if not isinstance(v, str):
                v = str(v)
            else:
                v = "'" + v + "'"
            values.append(v)
        values = ",".join(values)
        self.execute(
            "INSERT INTO", table_name, "(", keys, ")", "VALUES", "(", values, ")"
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cur.close()
        self._con.close()

    def query(self,
              column: str,
              table_name: str,
              statements: Optional[List[Tuple[str, Any]]] = None):
        if statements is not None and sl:
            sl = []
            for s in statements:
                if not isinstance(s[1], str):
                    s = (s[0], str(s[1]))
                else:
                    s = (s[0], "'" + s[1] + "'")
                sl.append(s[0] + " = " + s[1])
            sl = " AND ".join(sl)
            return self._query("SELECT", column, "FROM", table_name, "WHERE", sl)
        return self._query("SELECT", column, "FROM", table_name)

    def _query(self, *args):
        self.execute(*args)
        return self._cur.fetchall()

    def execute(self, *args):
        sql_command = " ".join(args)
        try:
            self._cur.execute(sql_command)
            self._con.commit()
            logging.debug(f"Execute sql: \"" + sql_command + "\"")
        except sqlite3.OperationalError:
            logging.error("Fail Execute sql: \"" + sql_command + "\"", exc_info=True)
