from rest_framework.pagination import PageNumberPagination


class BasePagination(PageNumberPagination):
    """
    基礎分頁器，支援從 payload 中讀取分頁參數
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_page_number(self, request, paginator):
        """
        優先從 request._pagination_data 中讀取頁碼，
        如果沒有則使用預設的查詢參數方式
        """
        if hasattr(request, '_pagination_data'):
            return request._pagination_data.get('page', 1)
        return super().get_page_number(request, paginator)
    
    def get_page_size(self, request):
        """
        優先從 request._pagination_data 中讀取頁面大小，
        如果沒有則使用預設的查詢參數方式
        """
        if hasattr(request, '_pagination_data'):
            page_size = request._pagination_data.get('page_size', self.page_size)
            if page_size > self.max_page_size:
                return self.max_page_size
            return page_size
        return super().get_page_size(request) 