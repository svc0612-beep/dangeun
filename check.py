import sqlite3

con = sqlite3.connect("danggeun.db")
tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print(tables)