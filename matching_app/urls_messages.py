from django.urls import path

from .views_messages import (
    AllMessagesView,
    ConversationsListView,
    ConversationThreadView,
    MarkMessageReadView,
    SendMessageView,
)

app_name = 'messages'

urlpatterns = [
    path('send/', SendMessageView.as_view(), name='send'),
    path('all/', AllMessagesView.as_view(), name='all-messages'),
    path('conversations/', ConversationsListView.as_view(), name='conversations'),
    path('conversations/<int:user_id>/', ConversationThreadView.as_view(), name='thread'),
    path('mark-read/', MarkMessageReadView.as_view(), name='mark-read'),
]

