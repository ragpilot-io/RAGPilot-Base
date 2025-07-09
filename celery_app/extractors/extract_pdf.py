from RAGPilot.celery import app
from sources.models import SourceFile, SourceFileChunk, ProcessingStatus
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from celery_app.extractors import utils
from langchain_experimental.text_splitter import SemanticChunker

MAP_PROMPT = PromptTemplate.from_template("""
你是一個專業的文本摘要助手，請將以下內容進行摘要，使用繁體中文，並保持重點清晰。摘要請控制在 200 字以內：

{text}
""")

COMBINE_PROMPT = PromptTemplate.from_template("""
請綜合以下多段摘要，統一成一篇簡潔有重點的繁體中文摘要，總長度限制為 500 字以內：

{text}
""")

@app.task()
def extract_pdf_soruce_file_content(source_file_id: int):
    try:
        source_file = SourceFile.objects.get(id=source_file_id)
        source_file = utils.set_source_file_status(source_file, ProcessingStatus.PROCESSING)
    except Exception as e:
        utils.set_source_file_status(source_file, ProcessingStatus.FAILED, "找不到 SourceFile 物件。")
        return f"找不到 SourceFile 物件: {str(e)}"
    
    try:
        source_file.failed_reason = None
        source_file.save()
        source_file.refresh_from_db()
        
        if source_file.sourcefilechunk_set.count() > 0:
            source_file.sourcefilechunk_set.all().delete()
    except Exception as e:
        utils.set_source_file_status(source_file, ProcessingStatus.FAILED, "刪除 SourceFileChunk 物件失敗。")
        return f"刪除 SourceFileChunk 物件失敗: {str(e)}"

    try:
        # 使用 PyPDFLoader 載入 PDF
        loader = PyPDFLoader(source_file.path)
        documents = loader.load()
    except Exception as e:
        utils.set_source_file_status(source_file, ProcessingStatus.FAILED, "載入 PDF 檔案失敗。")
        return f"載入 PDF 檔案失敗: {str(e)}"
        
    if not documents:
        utils.set_source_file_status(source_file, ProcessingStatus.COMPLETED)
        source_file.summary = f"PDF 檔案 {source_file.filename} 沒有可提取的內容，請使用其他方式提取內容。"
        source_file.save()
        return f"PDF 檔案 {source_file.filename} 沒有可提取的內容，請使用其他方式提取內容。"
    
    # 初始化 embeddings 模型
    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    except Exception as e:
        utils.set_source_file_status(source_file, ProcessingStatus.FAILED, "初始化 embeddings 模型失敗。")
        return f"初始化 embeddings 模型失敗: {str(e)}"
    
    parent_text_splitter = SemanticChunker(
        embeddings=embeddings,
        buffer_size=3,  # 增加緩衝區大小，提供更好的上下文
        add_start_index=True,  # 啟用索引追蹤，便於除錯
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=0.75,  # 提高閾值，減少過度分割
        sentence_split_regex=r"(?<=[。！？.!?])\s*",  # 支援中英文標點符號
    )
    
    child_text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,  # 增加塊大小，更適合語義搜索
        chunk_overlap=50,  # 適當的重疊
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]  # 支援中英文分隔符
    )

    try:
        parent_chunks_docs = parent_text_splitter.split_documents(documents)
        parent_chunks = [doc.page_content for doc in parent_chunks_docs]
        tmp_parent_chunks = "---".join(parent_chunks)
        print(tmp_parent_chunks)
        
        # 分批處理 embeddings 以避免 API 限制
        parent_chunk_embeddings = []
        batch_size = 1000  # 每批處理 1000 個文字塊，OpenAI API 可以處理更大批次
        
        for i in range(0, len(parent_chunks), batch_size):
            batch = parent_chunks[i:i + batch_size]
            batch_embeddings = embeddings.embed_documents(batch)
            parent_chunk_embeddings.extend(batch_embeddings)
            
    except Exception as e:
        utils.set_source_file_status(source_file, ProcessingStatus.FAILED, "分割父段落失敗。")
        return f"分割父段落失敗: {str(e)}"
    
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        chain = load_summarize_chain(
            llm, 
            chain_type="map_reduce", 
            map_prompt=MAP_PROMPT, 
            combine_prompt=COMBINE_PROMPT
        )
        summary = chain.invoke(parent_chunks_docs)
        source_file.summary = summary.get("output_text")
        source_file.save()
        source_file.refresh_from_db()
    except Exception as e:
        utils.set_source_file_status(source_file, ProcessingStatus.FAILED, "生成摘要失敗。")
        return f"生成摘要失敗: {str(e)}"
    
    parent_chunks_created = 0
    child_chunks_created = 0
    
    for i, (parent_chunk_text, embedding) in enumerate(zip(parent_chunks, parent_chunk_embeddings)):
        try:
            parent_chunk = SourceFileChunk.objects.create(
                user=source_file.user,
                source_file=source_file,
                content=parent_chunk_text,
                content_embedding=embedding
            )
            parent_chunks_created += 1

            # 分割子文字塊
            child_chunks = child_text_splitter.split_text(parent_chunk_text)
            if child_chunks:
                child_chunk_embeddings = embeddings.embed_documents(child_chunks)
                
                for child_chunk_text, child_chunk_embedding in zip(child_chunks, child_chunk_embeddings):
                    SourceFileChunk.objects.create(
                        user=source_file.user,
                        source_file=source_file,
                        source_file_chunk=parent_chunk,
                        content=child_chunk_text,
                        content_embedding=child_chunk_embedding
                    )
                    child_chunks_created += 1
                    
        except Exception as e:
            utils.set_source_file_status(source_file, ProcessingStatus.FAILED, f"處理文字塊失敗: {str(e)}")
            return f"處理文字塊失敗: {str(e)}"

    utils.set_source_file_status(source_file, ProcessingStatus.COMPLETED)
    
    return f"成功提取 PDF 檔案 {source_file.filename} 的內容，創建了 {parent_chunks_created} 個父文字片段和 {child_chunks_created} 個子文字片段。"
