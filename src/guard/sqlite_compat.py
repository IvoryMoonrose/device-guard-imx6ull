"""Use stdlib sqlite3 when available, otherwise the existing libsqlite3 C API."""
import ctypes


class NativeRow:
    def __init__(self, names, values):
        self.names = names
        self.values = values

    def keys(self):
        return self.names

    def __getitem__(self, key):
        return self.values[key if isinstance(key, int) else self.names.index(key)]


class NativeCursor:
    def __init__(self, rows, lastrowid):
        self.rows = rows
        self.lastrowid = lastrowid

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class NativeConnection:
    def __init__(self, path):
        self.lib = ctypes.CDLL('libsqlite3.so.0')
        void = ctypes.c_void_p
        integer = ctypes.c_int
        string = ctypes.c_char_p
        signatures = {
            'sqlite3_open_v2': ([string, ctypes.POINTER(void), integer, string], integer),
            'sqlite3_close': ([void], integer),
            'sqlite3_busy_timeout': ([void, integer], integer),
            'sqlite3_errmsg': ([void], string),
            'sqlite3_prepare_v2': ([void, string, integer, ctypes.POINTER(void), void], integer),
            'sqlite3_bind_null': ([void, integer], integer),
            'sqlite3_bind_int64': ([void, integer, ctypes.c_int64], integer),
            'sqlite3_bind_double': ([void, integer, ctypes.c_double], integer),
            'sqlite3_bind_text': ([void, integer, string, integer, void], integer),
            'sqlite3_step': ([void], integer),
            'sqlite3_finalize': ([void], integer),
            'sqlite3_column_count': ([void], integer),
            'sqlite3_column_name': ([void, integer], string),
            'sqlite3_column_type': ([void, integer], integer),
            'sqlite3_column_int64': ([void, integer], ctypes.c_int64),
            'sqlite3_column_double': ([void, integer], ctypes.c_double),
            'sqlite3_column_text': ([void, integer], string),
            'sqlite3_last_insert_rowid': ([void], ctypes.c_int64),
        }
        for name, (arguments, returns) in signatures.items():
            function = getattr(self.lib, name)
            function.argtypes = arguments
            function.restype = returns
        self.handle = void()
        self.check(self.lib.sqlite3_open_v2(path.encode('utf8'), ctypes.byref(self.handle), 0x10006, None))
        self.lib.sqlite3_busy_timeout(self.handle, 3000)

    def check(self, code):
        if code != 0:
            message = self.lib.sqlite3_errmsg(self.handle)
            raise RuntimeError('SQLite: '+(message.decode('utf8', 'replace') if message else str(code)))

    def execute(self, sql, parameters=()):
        statement = ctypes.c_void_p()
        self.check(self.lib.sqlite3_prepare_v2(self.handle, sql.encode('utf8'), -1, ctypes.byref(statement), None))
        rows = []
        try:
            for index, value in enumerate(parameters, 1):
                if value is None:
                    code = self.lib.sqlite3_bind_null(statement, index)
                elif isinstance(value, (int, bool)):
                    code = self.lib.sqlite3_bind_int64(statement, index, int(value))
                elif isinstance(value, float):
                    code = self.lib.sqlite3_bind_double(statement, index, value)
                else:
                    data = str(value).encode('utf8')
                    code = self.lib.sqlite3_bind_text(statement, index, data, len(data), ctypes.c_void_p(-1))
                self.check(code)
            while True:
                code = self.lib.sqlite3_step(statement)
                if code == 101:
                    break
                if code != 100:
                    self.check(code)
                names, values = [], []
                for index in range(self.lib.sqlite3_column_count(statement)):
                    names.append(self.lib.sqlite3_column_name(statement, index).decode('utf8'))
                    value_type = self.lib.sqlite3_column_type(statement, index)
                    if value_type == 5:
                        value = None
                    elif value_type == 1:
                        value = self.lib.sqlite3_column_int64(statement, index)
                    elif value_type == 2:
                        value = self.lib.sqlite3_column_double(statement, index)
                    else:
                        raw = self.lib.sqlite3_column_text(statement, index)
                        value = raw.decode('utf8') if raw is not None else ''
                    values.append(value)
                rows.append(NativeRow(names, values))
            return NativeCursor(rows, self.lib.sqlite3_last_insert_rowid(self.handle))
        finally:
            self.lib.sqlite3_finalize(statement)

    def commit(self):
        # Each statement above is finalized and SQLite autocommit is enabled.
        pass

    def close(self):
        self.check(self.lib.sqlite3_close(self.handle))


def connect(path, force_native=False):
    if not force_native:
        try:
            import sqlite3
            connection = sqlite3.connect(path, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            return connection
        except ImportError:
            pass
    return NativeConnection(path)
