"""
建議問題生成的通用工具模組
提取三個API中的共同流程和方法
"""

import random
from typing import List, Dict, Any, Optional
from django.http import JsonResponse
from langchain_openai import ChatOpenAI


class QuestionSuggestionGenerator:
    """建議問題生成器"""
    
    def __init__(self, 
                 model: str = "gpt-4o-mini",
                 temperature: float = 0.8,
                 max_question_count: int = 4,
                 max_question_length: int = 60):
        """
        初始化生成器
        
        Args:
            model: OpenAI 模型名稱
            temperature: 生成溫度
            max_question_count: 最大問題數量
            max_question_length: 最大問題長度
        """
        self.model = model
        self.temperature = temperature
        self.max_question_count = max_question_count
        self.max_question_length = max_question_length
    
    def generate_suggestions(self,
                           prompt_template: str,
                           variety_prompts: List[str],
                           context_data: str,
                           context_key: str = 'context') -> JsonResponse:
        """
        生成建議問題的主要方法
        
        Args:
            prompt_template: Prompt 模板字符串
            variety_prompts: 多樣化提示詞列表
            context_data: 上下文數據
            context_key: 上下文數據在模板中的鍵名
            
        Returns:
            JsonResponse: 包含建議問題的響應
        """
        try:
            if not context_data:
                return JsonResponse({
                    'success': False,
                    'message': '目前無法生成建議問題'
                })
            
            # 隨機選擇提示詞
            selected_prompt = random.choice(variety_prompts)
            
            # 構建完整的 prompt
            prompt = prompt_template.format(
                selected_prompt=selected_prompt,
                **{context_key: context_data}
            )
            
            # 調用 OpenAI API
            response = self._call_openai(prompt)
            
            # 解析和處理問題
            questions = self._parse_questions(response.content)
            
            # 去重處理
            unique_questions = self._remove_similar_questions(questions)
            
            # 限制問題數量
            final_questions = unique_questions[:self.max_question_count]
            
            if final_questions:
                return JsonResponse({
                    'success': True,
                    'suggestions': final_questions
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': '目前無法生成建議問題'
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': '建議問題生成失敗'
            })
    
    def _call_openai(self, prompt: str) -> Any:
        """調用 OpenAI API"""
        llm = ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            seed=random.randint(1, 10000)
        )
        return llm.invoke(prompt)
    
    def _parse_questions(self, content: str) -> List[str]:
        """解析 AI 回應中的問題"""
        questions = []
        for line in content.strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('#') and len(line) <= self.max_question_length:
                # 移除可能的編號或符號
                line = line.lstrip('0123456789.-) ')
                if line:
                    questions.append(line)
        return questions
    
    def _remove_similar_questions(self, questions: List[str]) -> List[str]:
        """去重類似問題"""
        unique_questions = []
        for q in questions:
            is_similar = False
            for existing in unique_questions:
                if self._calculate_similarity(q, existing) > 0.5:
                    is_similar = True
                    break
            
            if not is_similar:
                unique_questions.append(q)
        
        return unique_questions
    
    def _calculate_similarity(self, q1: str, q2: str) -> float:
        """計算兩個問題的相似度"""
        q1_words = set(q1.replace('？', '').replace('?', '').split())
        q2_words = set(q2.replace('？', '').replace('?', '').split())
        
        if not q1_words or not q2_words:
            return 0.0
        
        intersection = len(q1_words & q2_words)
        union = max(len(q1_words), len(q2_words))
        
        return intersection / union


# 數據收集器基類
class DataCollector:
    """數據收集器基類"""
    
    def collect_data(self, **kwargs) -> Optional[str]:
        """收集數據的抽象方法，由子類實現"""
        raise NotImplementedError("子類必須實現 collect_data 方法")


class SourceDataCollector(DataCollector):
    """自建資料源數據收集器"""
    
    def collect_data(self, user, **kwargs) -> Optional[str]:
        """收集自建資料源數據"""
        from sources.models import SourceFile
        
        # 獲取用戶的已完成檔案
        user_files = SourceFile.objects.filter(
            user=user,
            status='completed'
        ).order_by('-created_at')
        
        if not user_files.exists():
            return None
        
        # 從最近的檔案中隨機選取樣本
        sample_size = min(user_files.count(), random.randint(3, 6))
        selected_files = random.sample(list(user_files[:10]), sample_size)
        
        # 組織檔案資訊
        file_info_list = []
        for file_obj in selected_files:
            file_info = f"檔案：{file_obj.filename} ({file_obj.get_format_display()})"
            if file_obj.summary:
                file_info += f"\n摘要：{file_obj.summary}"
            file_info_list.append(file_info)
        
        files_text = "\n\n".join(file_info_list)
        return files_text


# 建議問題生成的便利函數
def generate_source_suggestions(user) -> JsonResponse:
    """生成自建資料源建議問題"""
    from sources.prompts import SOURCE_VARIETY_PROMPTS, SOURCE_SUGGESTION_PROMPT_TEMPLATE
    
    generator = QuestionSuggestionGenerator()
    collector = SourceDataCollector()
    
    context_data = collector.collect_data(user=user)
    
    if context_data is None:
        return JsonResponse({
            'success': False,
            'message': '您尚未上傳任何檔案，無法生成建議問題'
        })
    
    return generator.generate_suggestions(
        prompt_template=SOURCE_SUGGESTION_PROMPT_TEMPLATE,
        variety_prompts=SOURCE_VARIETY_PROMPTS,
        context_data=context_data,
        context_key='files_text'
    ) 