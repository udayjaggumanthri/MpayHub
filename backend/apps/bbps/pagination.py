"""DRF pagination helpers for BBPS admin APIs."""
from rest_framework.pagination import PageNumberPagination


class AdminPageNumberPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response_data(self, results):
        return {
            'page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'total': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'results': results,
        }
