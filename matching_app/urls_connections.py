from django.urls import path

from .views_connections import (
    ConnectionAcceptView,
    ConnectionCancelView,
    ConnectionRejectView,
    ConnectionRemoveView,
    ConnectionRequestView,
    FriendsListView,
    PendingReceivedListView,
    PendingSentListView,
)

app_name = 'connections'

urlpatterns = [
    path('request/', ConnectionRequestView.as_view(), name='request'),
    path('accept/', ConnectionAcceptView.as_view(), name='accept'),
    path('reject/', ConnectionRejectView.as_view(), name='reject'),
    path('cancel/', ConnectionCancelView.as_view(), name='cancel'),
    path('remove/', ConnectionRemoveView.as_view(), name='remove'),
    path('friends/', FriendsListView.as_view(), name='friends'),
    path('pending/sent/', PendingSentListView.as_view(), name='pending-sent'),
    path('pending/received/', PendingReceivedListView.as_view(), name='pending-received'),
]


