import os
import sqlite3
import pandas as pd

# スクリプトの場所にカレントディレクトリを変更
os.chdir(os.path.dirname(os.path.abspath(__file__)))

conn = sqlite3.connect('../db/KYG.db')
cur = conn.cursor()

# m_stockテーブルが存在するか確認
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='m_stock';")
exists = cur.fetchone()

# テーブルが存在しない場合のみcreate文を実行
if not exists:
    with open('../db/SQL/create_m_stock.sql', encoding='utf-8') as f:
        create_sql = f.read()
    cur.executescript(create_sql)

df = pd.read_csv("csv/output_2025_6_12_PM.csv", encoding='utf-8')


# データフレームをSQLiteのテーブルに書き込む
for idx, row in df.iterrows():
    cur.execute('''
        INSERT INTO m_stock (stock_code, stock_name, insert_user, update_user, delete_flag)
        VALUES (?, ?, ?, ?, 0)
    ''', (str(row['証券コード']), row['銘柄名'], 'system', 'system'))
conn.commit()

# 作成したデータベースを1行ずつ見る
select_sql = 'SELECT * FROM m_stock'
for row in cur.execute(select_sql):
    print(row)

cur.close()
conn.close()