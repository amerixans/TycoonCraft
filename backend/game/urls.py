from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('game-state/', views.game_state, name='game_state'),
    path('craft/', views.craft_objects, name='craft'),
    path('place/', views.place_object, name='place'),
    path('remove/', views.remove_object, name='remove'),
    path('unlock-era/', views.unlock_era, name='unlock_era'),
    path('export/', views.export_game, name='export'),
    path('import/', views.import_game, name='import'),
]
