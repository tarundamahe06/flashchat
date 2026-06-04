from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    RegisterView,
    LogoutView,
    MyProfileView,
    UserProfileView,
    ChangePasswordView,
    FollowToggleView,
    BlockToggleView,
    FollowersListView,
    FollowingListView,
    BlockedListView,
    UserSearchView,

    AllUsersView
)

urlpatterns = [
    # Auth
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", TokenObtainPairView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),

    # Own profile
    path("me/", MyProfileView.as_view(), name="my_profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),

    # Search
    path("search/", UserSearchView.as_view(), name="user_search"),

    # Blocked list
    path("blocked/", BlockedListView.as_view(), name="blocked_list"),


    path("all/", AllUsersView.as_view(), name="all_users"),

    # Other user profiles
    path("<str:username>/", UserProfileView.as_view(), name="user_profile"),
    path("<str:username>/follow/", FollowToggleView.as_view(), name="follow_toggle"),
    path("<str:username>/block/", BlockToggleView.as_view(), name="block_toggle"),
    path("<str:username>/followers/", FollowersListView.as_view(), name="followers_list"),
    path("<str:username>/following/", FollowingListView.as_view(), name="following_list"),

    
]

