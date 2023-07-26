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
            try:
                self.execute(command, log=False, do_raise=True)
            except:
                logging.error(f"Could not execute {filename}", exc_info=True)
                break
        else:
            logging.info(f"Database initialize: {filename} executed")

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
        if statements is not None:
            sl = []
            for s in statements:
                if not isinstance(s[1], str):
                    s = (s[0], str(s[1]))
                else:
                    s = (s[0], "'" + s[1] + "'")
                sl.append(s[0] + " = " + s[1])
            sl = " AND ".join(sl)
            return self._query("SELECT", column, "FROM", table_name, "WHERE", sl)
        q = self._query("SELECT", column, "FROM", table_name)
        if q[0][0] is None:
            return []
        return q

    def _query(self, *args):
        self.execute(*args)
        return self._cur.fetchall()

    def update(self, statements, new_values, table_name):
        sl = []
        for s in statements:
            if not isinstance(s[1], str):
                s = (s[0], str(s[1]))
            else:
                s = (s[0], "'" + s[1] + "'")
            sl.append(s[0] + " = " + s[1])
        sl = " AND ".join(sl)
        nv = []
        for v in new_values:
            if not isinstance(v[1], str):
                v = (v[0], str(v[1]))
            else:
                v = (v[0], "'" + v[1] + "'")
            nv.append(v[0] + " = " + v[1])
        nv = ",".join(nv)
        self.execute("UPDATE ", table_name, "SET", nv, "WHERE", sl)

    def execute(self, *args, log=True, do_raise=False):
        sql_command = " ".join(args)
        try:
            self._cur.execute(sql_command)
            self._con.commit()
            if log:
                logging.debug(f"Execute sql: \"" + sql_command + "\"")
        except Exception as sql_error:
            if log:
                logging.error("Fail Execute sql: \"" + sql_command + "\"", exc_info=True)
            if do_raise:
                raise sql_error