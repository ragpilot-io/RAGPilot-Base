import pandas as pd
from datetime import datetime
from langchain_openai import ChatOpenAI


def parse_datetime_string(date_string):
    """
    解析時間字串並轉換為 datetime 物件
    支援格式：'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD'
    如果傳統格式失敗，會使用 OpenAI 協助解析
    """
    if not date_string or pd.isna(date_string):
        return None
    
    date_string = str(date_string).strip()
    
    # 第一階段：嘗試常見的時間格式
    common_formats = [
        '%Y-%m-%d %H:%M:%S',  # 2024-01-01 12:00:00
        '%Y-%m-%d',           # 2024-01-01
        '%Y/%m/%d %H:%M:%S',  # 2024/01/01 12:00:00
        '%Y/%m/%d',           # 2024/01/01
        '%Y.%m.%d %H:%M:%S',  # 2024.01.01 12:00:00
        '%Y.%m.%d',           # 2024.01.01
        '%d/%m/%Y %H:%M:%S',  # 01/01/2024 12:00:00
        '%d/%m/%Y',           # 01/01/2024
        '%d-%m-%Y %H:%M:%S',  # 01-01-2024 12:00:00
        '%d-%m-%Y',           # 01-01-2024
        '%Y年%m月%d日 %H:%M:%S',  # 2024年01月01日 12:00:00
        '%Y年%m月%d日',           # 2024年01月01日
        '%m/%d/%Y %H:%M:%S',  # 01/01/2024 12:00:00 (美式格式)
        '%m/%d/%Y'            # 01/01/2024 (美式格式)
    ]
    
    for date_format in common_formats:
        try:
            return datetime.strptime(date_string, date_format)
        except ValueError:
            continue
    
    # 第二階段：使用 OpenAI 協助解析時間格式
    try:
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            max_tokens=50
        )
        
        prompt = f"""
請將以下時間字串轉換為 ISO 8601 格式 (YYYY-MM-DDTHH:MM:SS)。
如果沒有時間部分，請使用 00:00:00。
如果無法解析，請回傳 "INVALID"。

時間字串: "{date_string}"

請只回傳轉換後的時間字串，不要有其他解釋。
"""
        
        response = llm.invoke(prompt)
        iso_date_string = response.content.strip()
        
        if iso_date_string == "INVALID":
            print(f"OpenAI 也無法解析時間格式: {date_string}")
            return None
        
        # 嘗試解析 OpenAI 轉換的 ISO 格式
        try:
            # 移除可能的時區資訊
            if 'T' in iso_date_string:
                return datetime.fromisoformat(iso_date_string.replace('Z', ''))
            else:
                return datetime.fromisoformat(iso_date_string)
        except ValueError:
            # 如果 ISO 格式解析失敗，嘗試其他格式
            try:
                return datetime.strptime(iso_date_string, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    return datetime.strptime(iso_date_string, '%Y-%m-%d')
                except ValueError:
                    print(f"OpenAI 轉換的格式仍無法解析: {iso_date_string} (原始: {date_string})")
                    return None
                    
    except Exception as e:
        print(f"使用 OpenAI 解析時間時發生錯誤: {str(e)}")
        print(f"無法解析時間格式: {date_string}")
        return None

