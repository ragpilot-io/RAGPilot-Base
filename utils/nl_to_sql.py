import json
import re
from typing import Type
from pydantic import BaseModel, Field
from django.conf import settings
from langchain_core.tools import BaseTool
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.agents import AgentFinish
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent


class MarkdownOnlyParser(BaseOutputParser):
    def parse(self, text: str) -> AgentFinish:
        match = re.search(r"```(?:markdown|md)?\s*(.*?)\s*```", text, re.DOTALL)
        content = match.group(1).strip() if match else text.strip()
        if "查無資料" in content:
            return AgentFinish(return_values={"output": "⚠️ 模型回傳查無資料，請確認欄位或描述是否模糊"}, log=text)
        return AgentFinish(return_values={"output": content}, log=text)


class NL2SQLQueryInput(BaseModel):
    question: str = Field(description="使用者原本的問題")
    table_info_list: str = Field(default="", description="""資料表資訊列表，格式如下：
[
    {
        "database_name": "資料庫名稱",
        "table_name": "資料表名稱",
        "column_name_mapping_list": [["a", "欄位描述"], ["b", "欄位描述"]] (可選)
    }
]
""")


class CustomNL2SQLQueryTool(BaseTool):
    name: str = "custom_nl2sql_query"
    description: str = "根據自然語言問題查詢 SQL，回傳 Markdown 格式查詢摘要"
    args_schema: Type[BaseModel] = NL2SQLQueryInput

    def _run(self, question: str, table_info_list: str):
        llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
        table_info_list = json.loads(table_info_list)
        db_tables = {}
        for info in table_info_list:
            db = info["database_name"]
            db_tables.setdefault(db, []).append({
                "table_name": info.get("table_name"),
                "column_name_mapping_list": info.get("column_name_mapping_list")
            })

        markdown_results = []

        for db_name, tables in db_tables.items():
            db_uri = f"postgresql://{settings.DATABASES['default']['USER']}:{settings.DATABASES['default']['PASSWORD']}@{settings.DATABASES['default']['HOST']}:{settings.DATABASES['default']['PORT']}/{db_name}"

            for i in range(0, len(tables), 2):
                batch = tables[i:i + 2]
                batch_table_names = [t["table_name"] for t in batch if t.get("table_name")]
                db = SQLDatabase.from_uri(db_uri, include_tables=batch_table_names)

                user_prompt = f"你可以查詢資料庫 `{db_name}` 中的以下資料表：\n"
                for table in batch:
                    tname = table["table_name"]
                    col_map = table.get("column_name_mapping_list", [])
                    if col_map:
                        user_prompt += f"\n- 資料表 `{tname}` 的欄位描述如下：\n"
                        for col, desc in col_map:
                            user_prompt += f"  - `{col}`：{desc}\n"
                    else:
                        user_prompt += f"\n- 資料表 `{tname}` 無欄位說明。\n"

                user_prompt += (
                    f"\n請根據上述資料表與欄位說明查詢以下問題：\n「{question}」\n\n"
                    "查詢規則如下：\n"
                    "- 若你能理解問題，請回傳符合條件的資料，並加上 LIMIT 10 限制筆數。\n"
                    "- 若問題不夠明確，請回傳各表的前 10 筆樣本資料（SELECT * FROM 表 LIMIT 10）。\n"
                    "- 若 SQL 執行錯誤、查詢失敗或條件不明，請直接回傳樣本資料。\n"
                    "- 不得主觀認定為『查無資料』，除非所有欄位明確為空。\n"
                    "結果請包在 Markdown 區塊中，其他格式與語氣不限。"
                )

                system_message = (
                    "你是一個 SQL 查詢助手。回覆內容務必包在 ```markdown ...``` 區塊中，"
                    "若查詢結果不明確，請將資料樣本彙整為 markdown 格式並回傳，禁止主觀猜測或回覆『查無資料』。"
                )

                toolkit = SQLDatabaseToolkit(db=db, llm=llm)
                agent_executor = create_sql_agent(
                    llm=llm,
                    toolkit=toolkit,
                    verbose=True,
                    handle_parsing_errors=True,
                    agent_kwargs={"system_message": system_message},
                    output_parser=MarkdownOnlyParser()
                )

                try:
                    result = agent_executor.invoke({"input": user_prompt})
                    result_text = result.get("output", "") if isinstance(result, dict) else str(result).strip()
                    markdown_results.append(result_text)
                except Exception:
                    continue

        return "\n\n".join(markdown_results) if markdown_results else "在所有資料表中皆無資料。"
