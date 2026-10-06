"""Pagination for bank accounts only. Does not change the global PAGE_SIZE."""

from rest_framework.pagination import PageNumberPagination


class BankAccountPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
