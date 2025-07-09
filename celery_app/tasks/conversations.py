import json
import re
import traceback
from django.contrib.auth import get_user_model
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from RAGPilot.celery import app
from utils.nl_to_sql import CustomNL2SQLQueryTool
from sources.models import Source, SourceFile
from sources.prompts import SOURCE_SYSTEM_PROMPT
from sources.tools import SourceFileQueryTool, SourceFileChunkQueryTool
from conversations.models import Session, Message, SenderChoices, MessageStatusChoices
User = get_user_model()


def get_chat_history(session, limit=10):
    """
    獲取對話歷史記錄，返回 LangChain 消息格式
    Args:
        session: Session 對象
        limit: 限制返回的消息數量（預設10條）
    """
    # 獲取該 session 下最近的對話記錄，排除 Tool 類型的消息
    messages = Message.objects.filter(
        session=session,
        is_deleted=False,
        sender__in=[SenderChoices.USER, SenderChoices.AI]
    ).order_by('-updated_at')[:limit]
    
    # 將消息轉換為 LangChain 格式並按時間順序排列
    chat_history = []
    for message in reversed(messages):
        if message.sender == SenderChoices.USER:
            chat_history.append(HumanMessage(content=message.text))
        elif message.sender == SenderChoices.AI:
            chat_history.append(AIMessage(content=message.text))
    
    return chat_history


def extract_references_from_tool_results(tool_results, data_type):
    reference_extractor_factory = {
        Source.__name__: {
            'module': 'sources.tools',
            'function': 'extract_source_references',
            'tool_names': ['source_file_retrieval', 'source_file_chunk_retrieval']
        }
    }
    
    references = []
    
    # 獲取對應的提取器配置
    extractor_config = reference_extractor_factory.get(data_type)
    if not extractor_config:
        return references
    
    # 動態導入對應的模組和函數
    try:
        import importlib
        module = importlib.import_module(extractor_config['module'])
        extract_function = getattr(module, extractor_config['function'])
    except (ImportError, AttributeError) as e:
        print(f"無法導入參考資料提取函數: {e}")
        return references
    
    for tool_result in tool_results:
        tool_name = tool_result['tool_name']
        tool_output = tool_result['tool_output']
        tool_input = tool_result['tool_input']
        
        if tool_name in extractor_config['tool_names']:
            try:
                # 調用對應的提取函數
                if data_type == Source.__name__:
                    # Source 類型需要額外的 tool_name 參數
                    refs = extract_function(tool_output, tool_input, tool_name)
                else:
                    refs = extract_function(tool_output, tool_input)
                references.extend(refs)
            except Exception as e:
                print(f"提取參考資料時發生錯誤: {e}")
                continue
    
    return references




@app.task()
def process_conversation_async(user_id, user_question, ai_message_id, reference_id_list=None, data_type="Mixed"):
    user = User.objects.get(id=user_id)
    session = Session.get_or_create_user_session(user)    
    
    # 使用已存在的 AI 訊息或創建新的
    try:
        ai_message = Message.objects.get(id=ai_message_id)
        # 更新狀態為 PROCESSING
        ai_message.status = MessageStatusChoices.PROCESSING
        ai_message.save()
    except Message.DoesNotExist:
        ai_message = Message.create_ai_message(session, user, "正在思考中...")
    
    
    try:
        if reference_id_list:
            user_question_with_refs = f"請使用我指定的參考資料ID：\n{reference_id_list}\n我的問題是：\n{user_question}"
        else:
            user_question_with_refs = user_question
            
        tool_factory = {}
        
        system_prompt_factory = {
            Source.__name__: SOURCE_SYSTEM_PROMPT,
        }
        
        llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
        
        # 獲取歷史對話記錄
        chat_history = get_chat_history(session)
        
        # 根據資料類型配置工具和系統提示
        if data_type == Source.__name__:
            # 自建資料源需要特殊處理，告訴 AI 當前用戶 ID
            system_prompt = f"{system_prompt_factory[data_type]}\n\n重要提醒：當前用戶 ID 是 {user_id}，在使用 source_file_retrieval 工具時請務必傳入此 user_id。"
            
            source_file_tool = SourceFileQueryTool()
            source_chunk_tool = SourceFileChunkQueryTool()
            nl2sql_tool = CustomNL2SQLQueryTool()
            tools = [source_file_tool, source_chunk_tool, nl2sql_tool]
        else:
            # 其他資料類型使用原本的邏輯
            system_prompt = system_prompt_factory[data_type]
            tool = tool_factory[data_type]()
            tools = [tool]
        
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_openai_functions_agent(
            llm=llm,
            tools=tools,
            prompt=prompt
        )
        
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
            max_iterations=3
        )
        
        result = agent_executor.invoke({
            "input": user_question_with_refs,
            "chat_history": chat_history
        })
        
        # 記錄 Tool 執行結果到資料庫（但不顯示在前端）
        tool_results = []
        if 'intermediate_steps' in result and result['intermediate_steps']:
            for i, (action, observation) in enumerate(result['intermediate_steps']):
                # 寫入資料庫，並關聯到 AI Message
                tool_message = Message.create_tool_message_with_parent(
                    session=session,
                    user=user,
                    parent_message=ai_message,
                    tool_name=action.tool,
                    tool_params=action.tool_input,
                    tool_result=str(observation)
                )
                
                # 收集工具結果
                tool_results.append({
                    'tool_name': action.tool,
                    'tool_input': action.tool_input,
                    'tool_output': str(observation),
                    'index': i,
                    'message_id': tool_message.id,
                    'parent_message_id': ai_message.id
                })
        
        # 提取參考資料並處理引用
        references = extract_references_from_tool_results(tool_results, data_type)
        
        # 最後更新 AI 訊息，確保它的 updated_at 是最新的
        final_output = result.get('output', '')
        if final_output:
            # 直接使用原始回答，不添加引用標記
            ai_message.text = final_output
            ai_message.references = references if references else None
            ai_message.status = MessageStatusChoices.COMPLETED
            ai_message.save()
        
        return f"成功完成對話，請在後端查看對話記錄。"
    except Exception as e:
        # 獲取完整的錯誤堆棧信息
        error_traceback = traceback.format_exc()
        
        # 保存錯誤信息到 AI 訊息中
        ai_message.text = "對話過程中發生錯誤，請稍後再試。"
        ai_message.traceback = error_traceback
        ai_message.status = MessageStatusChoices.FAILED
        ai_message.save()
        
        return {
            'status': 'error',
            'error': str(e),
            'ai_message_id': ai_message.id,
            'traceback': error_traceback
        }


