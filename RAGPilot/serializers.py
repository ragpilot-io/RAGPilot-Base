from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, IntegerField
import json


class BaseSerializer(ModelSerializer):
    """
    基礎 Serializer，提供通用的分頁參數和 JSON 解析功能
    """
    # 通用搜尋參數
    page = IntegerField(
        required=False, 
        write_only=True, 
        min_value=1, 
        default=1,
        help_text="頁碼，從 1 開始"
    )
    page_size = IntegerField(
        required=False, 
        write_only=True, 
        min_value=1, 
        max_value=100, 
        default=10,
        help_text="每頁資料筆數，最大 100 筆"
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.get('context', {}).get('request')
        
        # 處理 JSON 解析
        if 'data' in kwargs:
            data = kwargs['data']
            if isinstance(data, (bytes, str)):
                try:
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')
                    kwargs['data'] = json.loads(data)
                except json.JSONDecodeError as e:
                    kwargs['data'] = {}
                    self._json_decode_error = f"JSON 格式錯誤：{str(e)}"
                except UnicodeDecodeError as e:
                    kwargs['data'] = {}
                    self._json_decode_error = f"編碼錯誤：{str(e)}"
        
        super().__init__(*args, **kwargs)

    def validate(self, attrs):
        # JSON 解析錯誤檢查
        if hasattr(self, '_json_decode_error'):
            raise serializers.ValidationError({
                'json_format': self._json_decode_error
            })
        
        # Content-Type 檢查
        if self.request and self._has_search_params(attrs):
            if self.request.content_type != 'application/json':
                raise serializers.ValidationError({
                    'request_format': f'API 請求必須使用 application/json 格式，收到的格式：{self.request.content_type or "None"}'
                })
        
        return super().validate(attrs)
    
    def _has_search_params(self, attrs):
        """
        檢查是否包含搜尋參數，子類別可以重寫此方法
        """
        search_fields = getattr(self, 'search_fields', [])
        return any(key in attrs for key in search_fields)

    class Meta:
        abstract = True
