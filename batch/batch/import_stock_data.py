import pandas as pd
import os
import sqlite3
from datetime import datetime

def import_stock_data():
    """
    data_j.xlsから株式データを読み込み、m_stockテーブルに登録する
    """
    try:
        # ファイルパスの設定
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_dir, 'import', 'data_j.xls')
        
        # xlsファイルを読み込む
        df = pd.read_excel(file_path)
        
        # カラム名のマッピング
        column_mapping = {
            'コード': 'stock_code',
            '銘柄名': 'stock_name',
            '市場・商品区分': 'market_type',
            '33業種コード': 'industry_code_33',
            '33業種区分': 'industry_type_33',
            '17業種コード': 'industry_code_17',
            '17業種区分': 'industry_type_17',
            '規模コード': 'scale_code',
            '規模区分': 'scale_name'
        }
        
        # カラム名を英語に変換
        df = df.rename(columns=column_mapping)
        
        # データベースに登録
        # スクリプトの場所にカレントディレクトリを変更
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

        conn = sqlite3.connect('../db/KYG.db')
        cur = conn.cursor()


        """
        全データを削除する
        """
        try:
            cur.execute("DELETE FROM m_stock")
            conn.commit()
        except Exception as e:
            print(f"エラー: データの削除中にエラーが発生しました: {str(e)}")
            raise

        # 新規データを登録
        for _, row in df.iterrows():
            cur.execute('''
                INSERT INTO m_stock (stock_code, stock_name, market_type, industry_code_33, industry_type_33, industry_code_17, industry_type_17, insert_date, insert_user, update_date, update_user)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (row['stock_code'], row['stock_name'], row['market_type'], row['industry_code_33'], row['industry_type_33'], row['industry_code_17'], row['industry_type_17'], datetime.now(), 'system', datetime.now(), 'system'))
        conn.commit()

        print(f"登録完了: {len(df)}件のデータを登録しました。")
        
    except Exception as e:
        print(f"エラー: データの取り込み中にエラーが発生しました: {str(e)}")

if __name__ == "__main__":
    import_stock_data() 