from django.urls import path

from .views_sessions import (
    CancelSessionView,
    CreateSessionView,
    EndSessionView,
    GetJoinTokenView,
    MarkReadyView,
    SessionAuditLogsView,
    SessionDetailView,
    SessionListView,
    StartSessionView,
    ValidateJoinTokenView,
)

app_name = 'sessions'

urlpatterns = [
    path('', SessionListView.as_view(), name='list'),
    path('create/', CreateSessionView.as_view(), name='create'),
    path('<int:session_id>/', SessionDetailView.as_view(), name='detail'),
    path('<int:session_id>/start/', StartSessionView.as_view(), name='start'),
    path('<int:session_id>/ready/', MarkReadyView.as_view(), name='ready'),
    path('<int:session_id>/end/', EndSessionView.as_view(), name='end'),
    path('<int:session_id>/cancel/', CancelSessionView.as_view(), name='cancel'),
    path('<int:session_id>/audit-logs/', SessionAuditLogsView.as_view(), name='audit-logs'),
    path('<int:session_id>/join-token/', GetJoinTokenView.as_view(), name='join-token'),
    path('join-token/validate/', ValidateJoinTokenView.as_view(), name='validate-join-token'),
]

