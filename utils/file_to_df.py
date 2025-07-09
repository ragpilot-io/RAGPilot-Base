import io
import hashlib
import pandas as pd
import json
import psycopg2
from psycopg2 import errors
import xml.etree.ElementTree as ET
import string
from django.conf import settings


class FileDataFrameHandler:
    
    def __init__(self):
        self.supported_formats = ['csv', 'json', 'xml']
    
    def convert_to_dataframe(self, content: bytes, file_format: str, encoding: str = 'utf-8') -> pd.DataFrame:
        if file_format.lower() not in self.supported_formats:
            raise ValueError(f"不支援的檔案格式: {file_format}")
        
        try:
            decoded_content = content.decode(encoding, errors='ignore')
            file_format = file_format.lower()
            
            if file_format == 'csv':
                return self._read_csv_to_dataframe(decoded_content)
            elif file_format == 'json':
                return self._read_json_to_dataframe(decoded_content)
            elif file_format == 'xml':
                return self._read_xml_to_dataframe(decoded_content)
                
        except Exception as e:
            print(f"讀取 {file_format} 格式失敗: {str(e)}")
            return None
    
    def save_to_database(self, df: pd.DataFrame, table_name: str, database_name: str) -> tuple[bool, str]:
        if df is None or df.empty:
            return False, "DataFrame 為空"
        
        try:
            success = self._create_table_from_dataframe(df, table_name, database_name)
            
            if success:
                return True, f"成功儲存到資料表 {table_name}"
            else:
                return False, "儲存到資料庫失敗，請檢查資料表欄位名稱是否符合規範"
                
        except Exception as e:
            return False, f"儲存失敗: {str(e)}"
    
    def get_dataframe_md5(self, df: pd.DataFrame) -> str:
        df_copy = df.copy().astype(str)
        df_copy = df_copy[sorted(df_copy.columns)]
        df_copy = df_copy.sort_values(by=sorted(df_copy.columns)).reset_index(drop=True)
        
        content_str = df_copy.to_csv(index=False)
        return hashlib.md5(content_str.encode('utf-8')).hexdigest()
    
    def generate_excel_column_names(self, num_columns: int) -> list:
        return self._generate_excel_column_names(num_columns)
    
    def rename_dataframe_columns_to_excel_style(self, df: pd.DataFrame) -> pd.DataFrame:
        num_columns = len(df.columns)
        excel_column_names = self._generate_excel_column_names(num_columns)
        df_copy = df.copy()
        df_copy.columns = excel_column_names
        return df_copy
    
    def _read_csv_to_dataframe(self, content: str) -> pd.DataFrame:
        return pd.read_csv(io.StringIO(content))
    
    def _read_json_to_dataframe(self, content: str) -> pd.DataFrame:
        json_data = json.loads(content)
        
        if isinstance(json_data, list):
            return pd.DataFrame(json_data)
        elif isinstance(json_data, dict):
            for value in json_data.values():
                if isinstance(value, list) and len(value) > 0:
                    return pd.DataFrame(value)
            return pd.DataFrame([json_data])
        
        return None
    
    def _read_xml_to_dataframe(self, content: str) -> pd.DataFrame:
        root = ET.fromstring(content)
        
        data = []
        for child in root:
            row = {subchild.tag: subchild.text for subchild in child}
            if row:
                data.append(row)
        
        if data:
            return pd.DataFrame(data)
        else:
            row = {child.tag: child.text for child in root}
            if row:
                return pd.DataFrame([row])
        
        return None        
    
    def _generate_excel_column_names(self, num_columns: int) -> list:
        column_names = []
        
        if num_columns <= 26:
            for i in range(num_columns):
                column_names.append(string.ascii_lowercase[i])
        else:
            for i in range(26):
                column_names.append(string.ascii_lowercase[i])
            
            remaining = num_columns - 26
            for i in range(min(remaining, 676)):
                first_letter = string.ascii_lowercase[i // 26]
                second_letter = string.ascii_lowercase[i % 26]
                column_names.append(first_letter + second_letter)
        
        return column_names
    
    def _create_table_from_dataframe(self, df: pd.DataFrame, table_name: str, database_name: str) -> bool:
        try:
            db_config = settings.DATABASES['default']
            
            # 首先連接到默認資料庫 (通常是 postgres) 來創建目標資料庫
            default_conn = psycopg2.connect(
                host=db_config['HOST'],
                port=db_config['PORT'],
                database='postgres',  # 連接到默認的 postgres 資料庫
                user=db_config['USER'],
                password=db_config['PASSWORD']
            )
            
            # 設置自動提交模式以執行 CREATE DATABASE 命令
            default_conn.autocommit = True
            
            with default_conn.cursor() as cursor:
                # 先檢查資料庫是否已經存在
                cursor.execute(
                    "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
                    (database_name,)
                )
                exists = cursor.fetchone()
                
                if not exists:
                    # 資料庫不存在，創建它
                    try:
                        # 注意：CREATE DATABASE 不能使用參數化查詢，需要格式化字符串
                        # 但我們先驗證 database_name 只包含安全字符
                        if not database_name.replace('_', '').replace('-', '').isalnum():
                            raise ValueError(f"資料庫名稱包含不安全字符: {database_name}")
                        
                        cursor.execute(f'CREATE DATABASE "{database_name}"')
                    except Exception as e:
                        raise
            
            default_conn.close()
            
            # 現在連接到目標資料庫來創建資料表
            conn = psycopg2.connect(
                host=db_config['HOST'],
                port=db_config['PORT'],
                database=database_name,
                user=db_config['USER'],
                password=db_config['PASSWORD']
            )
            
            create_sql = self._generate_create_table_sql(df, table_name)
            
            with conn.cursor() as cursor:
                cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
                conn.commit()
                
                # 創建新的資料表
                cursor.execute(create_sql)
                conn.commit()
                
                self._insert_dataframe_to_table(cursor, df, table_name)
                conn.commit()
                
            return True
        except Exception as e:
            return False
        finally:
            if 'default_conn' in locals():
                default_conn.close()
            if 'conn' in locals():
                conn.close()
    
    def _generate_create_table_sql(self, df: pd.DataFrame, table_name: str) -> str:
        columns = []
        for col in df.columns:
            col_type = self._infer_column_type(df[col])
            columns.append(f'"{col}" {col_type}')
        
        columns_sql = ', '.join(columns)
        return f'CREATE TABLE "{table_name}" ({columns_sql})'
    
    def _infer_column_type(self, series: pd.Series) -> str:
        non_null_series = series.dropna()
        
        if non_null_series.empty:
            return 'TEXT'
        
        if series.dtype in ['int64', 'int32', 'int16', 'int8']:
            return 'BIGINT'
        elif series.dtype in ['float64', 'float32']:
            return 'DOUBLE PRECISION'
        elif series.dtype == 'bool':
            return 'BOOLEAN'
        elif pd.api.types.is_datetime64_any_dtype(series):
            return 'TIMESTAMP'
        
        if series.dtype == 'object':
            str_values = non_null_series.astype(str)
            max_length = str_values.str.len().max()
            
            if max_length <= 50:
                return 'VARCHAR(100)'
            elif max_length <= 200:
                return 'VARCHAR(500)'
            elif max_length <= 1000:
                return 'VARCHAR(2000)'
            else:
                return 'TEXT'
        
        return 'TEXT'
    
    def _insert_dataframe_to_table(self, cursor, df: pd.DataFrame, table_name: str):
        if df.empty:
            return
        
        columns = [f'"{col}"' for col in df.columns]
        placeholders = ['%s'] * len(df.columns)
        expected_col_count = len(df.columns)
        
        insert_sql = f"""
            INSERT INTO "{table_name}" ({', '.join(columns)}) 
            VALUES ({', '.join(placeholders)})
        """
        
        values = []
        for idx, row in df.iterrows():
            row_values = []
            
            for col in df.columns:
                val = row.get(col)
                if pd.isna(val):
                    row_values.append(None)
                else:
                    str_val = str(val)
                    if len(str_val) > 10000:
                        str_val = str_val[:9997] + "..."
                    row_values.append(str_val)
            
            if len(row_values) != expected_col_count:
                print(f"第 {idx+1} 行欄位數量不符 (期望: {expected_col_count}, 實際: {len(row_values)})，跳過")
                continue
                
            values.append(tuple(row_values))
        
        if not values:
            print("沒有有效的資料行可插入")
            return
        
        try:
            cursor.executemany(insert_sql, values)
        except Exception as e:
            print(f"批量插入失敗，嘗試逐行插入: {str(e)}")
            success_count = 0
            for i, value_tuple in enumerate(values):
                try:
                    if len(value_tuple) != expected_col_count:
                        print(f"第 {i+1} 行 tuple 長度不符 (期望: {expected_col_count}, 實際: {len(value_tuple)})，跳過")
                        continue
                        
                    cursor.execute(insert_sql, value_tuple)
                    success_count += 1
                except Exception as row_error:
                    print(f"第 {i+1} 行插入失敗，跳過: {str(row_error)}")
                    continue 