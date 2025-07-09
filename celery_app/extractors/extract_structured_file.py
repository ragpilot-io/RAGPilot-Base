import os
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from RAGPilot.celery import app
from sources.models import SourceFile, SourceFileChunk, SourceFileTable, ProcessingStatus
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from utils.file_to_df import FileDataFrameHandler
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from celery_app.extractors import utils

SUMMARY_PROMPT = PromptTemplate.from_template("""這份資料的檔案名稱叫做：{filename}。
這份資料共有 {record_count} 筆紀錄，欄位有：{columns}。
以下是部分欄位的統計資訊：
{column_summary}

請以繁體中文撰寫一段 500 字以內的摘要，說明這份資料的特性與可能用途，
語氣自然流暢，避免逐條列點，並且使用繁體中文，同時，如果檔案名稱為亂碼，摘要過程請不要參考檔案名稱。""")


@app.task()
def extract_structured_file_content(source_file_id: int):
    source_file = SourceFile.objects.get(id=source_file_id)

    try:
        source_file.failed_reason = None
        source_file.save()
        source_file.refresh_from_db()
        if source_file.sourcefiletable_set.count() > 0:
            source_file.sourcefiletable_set.all().delete()
    except Exception as e:
        utils.set_source_file_status(source_file, ProcessingStatus.FAILED, f"刪除 SourceFileTable 物件失敗。")
        return f"刪除 SourceFileTable 物件失敗: {str(e)}"

    utils.set_source_file_status(source_file, ProcessingStatus.PROCESSING)
    supported_formats = ['csv', 'json', 'xml']
    if source_file.format not in supported_formats:
        return f"檔案 {source_file.filename} 格式 {source_file.format} 不支援結構化資料提取"
        
    try:
        if not os.path.exists(source_file.path):
            raise FileNotFoundError(f"檔案不存在: {source_file.path}")    
        with open(source_file.path, 'rb') as f:
            file_content = f.read()
    except Exception as e:
        utils.set_source_file_status(source_file, ProcessingStatus.FAILED, f"讀取檔案失敗。")
        return f"讀取檔案失敗: {str(e)}"
    
    handler = FileDataFrameHandler()
    try:
        df = handler.convert_to_dataframe(file_content, source_file.format, encoding='utf-8')
    except Exception as e:
        utils.set_source_file_status(source_file, ProcessingStatus.FAILED, f"轉換為 DataFrame 失敗。")
        return f"轉換為 DataFrame 失敗: {str(e)}"
    
    if df is None or df.empty:
        utils.set_source_file_status(source_file, ProcessingStatus.COMPLETED)
        return f"檔案 {source_file.filename} 沒有可提取的結構化資料"
    
    success, message = handler.save_to_database(
            df=df, 
            table_name=source_file.uuid, 
            database_name=source_file.user.username
        )
    if not success:
        utils.set_source_file_status(source_file, ProcessingStatus.FAILED, message)
        return f"儲存資料到資料庫失敗: {str(e)}"
    
    SourceFileTable.objects.create(
        user=source_file.user,
        source_file=source_file,
        table_name=source_file.uuid,
        database_name=source_file.user.username
    )
    
    col_summary = df.describe(include='all').to_dict()
    summary_prompt = SUMMARY_PROMPT.format(
        filename=source_file.filename,
        record_count=len(df),
        columns=', '.join(df.columns),
        column_summary=col_summary
    )
    
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        summary_content = llm.invoke(summary_prompt).content
    except Exception as e:
        utils.set_source_file_status(source_file, ProcessingStatus.FAILED, f"生成摘要失敗。")
        return f"生成摘要失敗: {str(e)}"
    
    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        summary_embedding = embeddings.embed_query(summary_content)
    except Exception as e:
        utils.set_source_file_status(source_file, ProcessingStatus.FAILED, f"生成摘要嵌入失敗。")
        return f"生成摘要嵌入失敗: {str(e)}"
    
    source_file.summary = summary_content
    source_file.summary_embedding = summary_embedding
    source_file.save()
    source_file.refresh_from_db()

    utils.set_source_file_status(source_file, ProcessingStatus.COMPLETED)
    
    return f"成功提取結構化資料 {source_file.filename}，創建資料表 {source_file.uuid}"
    
