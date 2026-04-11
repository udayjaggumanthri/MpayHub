"""Pagination for contacts (bounded client page_size to limit abuse)."""

from rest_framework.pagination import PageNumberPagination


class ContactPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
