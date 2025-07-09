import json
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from utils.search import hybrid_search_with_rerank
from typing import Type
from sources.models import Source, SourceFile, SourceFileTable, SourceFileChunk


class SourceFileQueryInput(BaseModel):
    """自建資料源檔案查詢工具的輸入參數"""
    question: str = Field(description="使用者原本的問題")
    user_id: int = Field(description="使用者 ID，用於過濾該使用者的檔案")
    reference_id_list: str = Field(default="", description="參考資料 ID，以 JSON 字串格式傳入，例如：[1, 2, 3]")


class SourceFileChunkQueryInput(BaseModel):
    """自建資料源檔案片段查詢工具的輸入參數"""
    question: str = Field(description="使用者原本的問題")
    source_file_id_list: str = Field(description="SourceFile ID 列表，以 JSON 字串格式傳入，例如：[1, 2, 3]")


class SourceFileQueryTool(BaseTool):
    """自建資料源檔案檢索工具 - 檢索結構化檔案並提供資料表資訊"""
    
    name: str = "source_file_retrieval"
    description: str = """檢索自建資料源檔案的工具，用於找出相關檔案並組織其他工具所需的參數。

使用情境：
- 若有參考資料ID (reference_id_list)，請將其轉換為 JSON 字串格式傳入，例如：[1, 2, 3]，這些ID是 Source 的 id
- 若無參考資料，則會查詢該使用者的所有檔案
- 使用 hybrid search 技術根據檔案摘要找出最相關的檔案

此工具會返回：
- 檔案的基本資訊（名稱、格式、資料源等）
- **source_file_id_list**：可用於 source_file_chunk_retrieval 工具
- **table_info_list**：可用於 custom_nl2sql_query 工具

參數描述：
- question: 使用者的查詢問題，用於語意搜尋檔案摘要
- user_id: 使用者 ID，確保只查詢該使用者的檔案
- reference_id_list: 指定要查詢的資料源ID列表，JSON字串格式"""
    args_schema: Type[BaseModel] = SourceFileQueryInput

    def _run(
        self, 
        question: str,
        user_id: int,
        reference_id_list: str = "",
    ) -> str:
        # 1. 根據 reference_id_list 決定要查詢的 SourceFile
        if reference_id_list:
            try:
                reference_ids = json.loads(reference_id_list)
            except (json.JSONDecodeError, ValueError):
                return "參考資料ID格式錯誤，請提供正確的JSON格式。"
            
            # 根據指定的 Source ID 拉取所有檔案
            source_files = SourceFile.objects.filter(
                source_id__in=reference_ids,
                user_id=user_id,
                status='completed'
            ).order_by('-created_at')
        else:
            # 查詢該使用者的所有檔案
            source_files = SourceFile.objects.filter(
                user_id=user_id,
                status='completed'
            ).order_by('-created_at')
        
        if not source_files.exists():
            return "未找到可查詢的資料檔案。"

        # 2. 如果有問題，使用語意搜尋重新排序
        if question.strip():
            source_files = hybrid_search_with_rerank(
                queryset=source_files, 
                vector_field_name="summary_embedding",
                text_field_name="summary",
                original_question=question
            )

        # 3. 按檔案格式分組
        structured_files = []  # csv, json, xml
        pdf_files = []  # pdf
        
        for file in source_files:
            if file.format in ['csv', 'json', 'xml']:
                structured_files.append(file)
            elif file.format == 'pdf':
                pdf_files.append(file)

        # 4. 組織檔案資訊
        result = f"找到 {source_files.count()} 個相關的檔案：\n\n"
        
        # 5. 組織結構化檔案資訊和資料表資訊
        table_info_list = []
        if structured_files:
            result += f"=== 結構化檔案 ({len(structured_files)} 個) ===\n"
            for i, file in enumerate(structured_files, 1):
                result += f"   資料源：{file.source.name}\n"
                result += f"{i}. 【{file.format.upper()}】{file.filename}\n"
                if file.summary:
                    result += f"   摘要：{file.summary[:150]}{'...' if len(file.summary) > 150 else ''}\n"
                
                # 獲取該檔案的資料表資訊
                tables = SourceFileTable.objects.filter(source_file=file)
                if tables.exists():
                    for table in tables:
                        table_info_list.append({
                            "database_name": table.database_name,
                            "table_name": table.table_name,
                            "column_name_mapping_list": []
                        })
                result += "\n"

        # 6. 組織 PDF 檔案資訊
        if pdf_files:
            result += f"=== PDF 檔案 ({len(pdf_files)} 個) ===\n"
            for i, file in enumerate(pdf_files, 1):
                result += f"{i}. 【PDF】{file.filename}\n"
                result += f"   資料源：{file.source.name}\n"
                result += f"   檔案大小：{file.size:.2f} MB\n"
                if file.summary:
                    result += f"   摘要：{file.summary[:150]}{'...' if len(file.summary) > 150 else ''}\n"
                result += "\n"

        # 7. 附加工具參數
        if structured_files and table_info_list:
            result += f"table_info_list: {json.dumps(table_info_list, ensure_ascii=False)}\n"
        
        if pdf_files:
            pdf_file_ids = [file.id for file in pdf_files]
            result += f"source_file_id_list: {json.dumps(pdf_file_ids, ensure_ascii=False)}\n"
        
        return result


class SourceFileChunkQueryTool(BaseTool):
    """自建資料源檔案片段檢索工具 - 檢索 PDF 檔案內容片段"""
    
    name: str = "source_file_chunk_retrieval"
    description: str = """檢索自建資料源 PDF 檔案內容片段的工具。

使用情境：
- 接收指定的 SourceFile ID 列表，查詢這些檔案的內容片段
- 專門用於查詢 PDF 檔案的文字內容

查詢方式：
- 使用 hybrid search 技術對子段落進行語意搜尋
- 透過相關的子段落反向查找到父段落
- 回傳完整的父段落內容以提供更好的上下文

參數描述：
- question: 使用者的查詢問題
- source_file_id_list: 指定要查詢的 SourceFile ID 列表，JSON字串格式"""
    args_schema: Type[BaseModel] = SourceFileChunkQueryInput

    def _run(
        self, 
        question: str,
        source_file_id_list: str,
    ) -> str:
        # 1. 解析 source_file_id_list
        try:
            file_ids = json.loads(source_file_id_list)
        except (json.JSONDecodeError, ValueError):
            return "SourceFile ID 格式錯誤，請提供正確的JSON格式。"
        
        # 2. 獲取子段落（source_file_chunk_id 不為空）
        child_chunks_queryset = SourceFileChunk.objects.filter(
            source_file_id__in=file_ids,
            source_file_chunk_id__isnull=False  # 子段落
        )
        
        if not child_chunks_queryset.exists():
            return "未找到可查詢的檔案內容片段。"

        # 3. 使用 hybrid search 查詢子段落
        try:
            searched_child_chunks = hybrid_search_with_rerank(
                queryset=child_chunks_queryset,
                vector_field_name="content_embedding",
                text_field_name="content",
                original_question=question
            )
            
            if not searched_child_chunks:
                return "未找到相關的檔案內容片段。"

            # 4. 收集父段落 ID 並去重
            parent_chunk_ids = list(set([
                child_chunk.source_file_chunk_id 
                for child_chunk in searched_child_chunks 
                if child_chunk.source_file_chunk_id
            ]))
            
            if not parent_chunk_ids:
                return "未找到對應的父段落。"
            
            # 5. 批量查詢父段落
            parent_chunks = SourceFileChunk.objects.filter(id__in=parent_chunk_ids)
            
            if not parent_chunks.exists():
                return "未找到有效的父段落。"

            # 6. 組織結果（顯示父段落內容）
            result = f"找到 {len(parent_chunks)} 個相關的檔案內容段落：\n\n"
            
            for i, parent_chunk in enumerate(parent_chunks, 1):
                result += f"{i}. 【PDF】{parent_chunk.source_file.filename}\n"
                result += f"   資料源：{parent_chunk.source_file.source.name}\n"
                result += f"   檔案大小：{parent_chunk.source_file.size:.2f} MB\n"
                result += f"   內容段落：{parent_chunk.content}\n\n"
            
            return result
            
        except Exception as e:
            return f"檔案片段查詢過程中發生錯誤：{str(e)}"

def extract_source_references(tool_output, tool_input, tool_name):
    """提取 SourceFile 參考資料"""
    references = []
    
    if tool_name == 'source_file_retrieval':
        # 從 tool_input 中獲取 reference_id_list (這裡是 Source 的 ID)
        reference_ids = []
        user_id = tool_input.get('user_id')
        
        if 'reference_id_list' in tool_input and tool_input['reference_id_list']:
            try:
                reference_ids = json.loads(tool_input['reference_id_list'])
            except:
                pass
        
        if reference_ids and user_id:
            # 查詢指定 Source 下的所有檔案
            source_files = SourceFile.objects.filter(
                source_id__in=reference_ids,
                user_id=user_id,
                status='completed'
            )
            for source_file in source_files:
                references.append({
                    'type': 'source_file',
                    'id': source_file.id,
                    'title': f"【{source_file.format.upper()}】{source_file.filename}",
                    'content': f"資料源：{source_file.source.name}\n摘要：{source_file.summary[:200] if source_file.summary else '無摘要'}{'...' if source_file.summary and len(source_file.summary) > 200 else ''}",
                    'source': f"自建資料源 (檔案 ID: {source_file.id})"
                })
        elif user_id:
            # 沒有指定 reference_ids，從工具輸出中解析實際使用的檔案
            # 工具輸出格式包含檔案名稱和資料源資訊
            
            import re
            
            # 先嘗試匹配結構化檔案區塊
            structured_section_pattern = r'=== 結構化檔案.*?===(.*?)(?:=== PDF 檔案|$)'
            structured_section_match = re.search(structured_section_pattern, tool_output, re.DOTALL)
            
            if structured_section_match:
                structured_content = structured_section_match.group(1)
                
                # 提取資料源資訊（在檔案列表前面）
                source_pattern = r'資料源：([^\n]+)'
                source_match = re.search(source_pattern, structured_content)
                current_source = source_match.group(1) if source_match else ''
                
                # 匹配檔案：1. 【CSV】filename.csv
                file_pattern = r'(\d+)\.\s*【([^】]+)】([^\n]+)'
                file_matches = re.findall(file_pattern, structured_content)
                
                for match in file_matches:
                    try:
                        index, file_format, filename = match
                        
                        # 通過檔名和格式查找檔案
                        source_file = SourceFile.objects.filter(
                            filename=filename.strip(),
                            format=file_format.lower(),
                            user_id=user_id,
                            status='completed'
                        ).first()
                        
                        if source_file:
                            references.append({
                                'type': 'source_file',
                                'id': source_file.id,
                                'title': f"【{source_file.format.upper()}】{source_file.filename}",
                                'content': f"資料源：{source_file.source.name}\n摘要：{source_file.summary[:200] if source_file.summary else '無摘要'}{'...' if source_file.summary and len(source_file.summary) > 200 else ''}",
                                'source': f"自建資料源 (檔案 ID: {source_file.id})"
                            })
                    except Exception:
                        continue
            
            # 匹配 PDF 檔案區塊
            pdf_section_pattern = r'=== PDF 檔案.*?===(.*?)(?:source_file_id_list|table_info_list|$)'
            pdf_section_match = re.search(pdf_section_pattern, tool_output, re.DOTALL)
            
            if pdf_section_match:
                pdf_content = pdf_section_match.group(1)
                
                # 匹配 PDF 檔案：1. 【PDF】filename.pdf
                pdf_pattern = r'(\d+)\.\s*【PDF】([^\n]+)\n\s*資料源：([^\n]+)'
                pdf_matches = re.findall(pdf_pattern, pdf_content)
                
                for match in pdf_matches:
                    try:
                        index, filename, source_name = match
                        
                        # 通過檔名查找 PDF 檔案
                        source_file = SourceFile.objects.filter(
                            filename=filename.strip(),
                            format='pdf',
                            user_id=user_id,
                            status='completed'
                        ).first()
                        
                        if source_file:
                            references.append({
                                'type': 'source_file',
                                'id': source_file.id,
                                'title': f"【{source_file.format.upper()}】{source_file.filename}",
                                'content': f"資料源：{source_file.source.name}\n摘要：{source_file.summary[:200] if source_file.summary else '無摘要'}{'...' if source_file.summary and len(source_file.summary) > 200 else ''}",
                                'source': f"自建資料源 (檔案 ID: {source_file.id})"
                            })
                    except Exception:
                        continue
                        
            # 如果通過解析工具輸出沒找到檔案，使用備用方案：查詢該用戶的所有檔案
            if not references:
                source_files = SourceFile.objects.filter(
                    user_id=user_id,
                    status='completed'
                ).order_by('-created_at')[:5]  # 取最新的 5 個檔案
                
                for source_file in source_files:
                    references.append({
                        'type': 'source_file',
                        'id': source_file.id,
                        'title': f"【{source_file.format.upper()}】{source_file.filename}",
                        'content': f"資料源：{source_file.source.name}\n摘要：{source_file.summary[:200] if source_file.summary else '無摘要'}{'...' if source_file.summary and len(source_file.summary) > 200 else ''}",
                        'source': f"自建資料源 (檔案 ID: {source_file.id})"
                    })
    
    elif tool_name == 'source_file_chunk_retrieval':
        # 從 tool_input 中獲取 source_file_id_list
        file_ids = []
        if 'source_file_id_list' in tool_input:
            try:
                file_ids = json.loads(tool_input['source_file_id_list'])
            except:
                pass
        
        if file_ids:
            source_files = SourceFile.objects.filter(id__in=file_ids)
            for source_file in source_files:
                references.append({
                    'type': 'source_file',
                    'id': source_file.id,
                    'title': f"【{source_file.format.upper()}】{source_file.filename}",
                    'content': f"資料源：{source_file.source.name}\n摘要：{source_file.summary[:200] if source_file.summary else '無摘要'}{'...' if source_file.summary and len(source_file.summary) > 200 else ''}",
                    'source': f"自建資料源 (檔案 ID: {source_file.id})"
                })
    
    return references