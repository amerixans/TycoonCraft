from django.urls import path
from django.http import JsonResponse
from . import views

def api_root(request):
    """
    API root endpoint - returns available endpoints and API status.
    This makes /api/ return 200 OK for health checks.
    """
    return JsonResponse({
        'status': 'online',
        'message': 'TycoonCraft Game API',
        'version': '1.0',
        'endpoints': {
            'register': '/api/register/',
            'login': '/api/login/',
            'logout': '/api/logout/',
            'game_state': '/api/game-state/',
            'object_catalog': '/api/object-catalog/',
            'craft': '/api/craft/',
            'place': '/api/place/',
            'remove': '/api/remove/',
            'unlock_era': '/api/unlock-era/',
            'export': '/api/export/',
            'import': '/api/import/',
            'redeem_upgrade_key': '/api/redeem-upgrade-key/',
        }
    })

urlpatterns = [
    path('', api_root, name='api-root'),  # Root endpoint at /api/
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('game-state/', views.game_state, name='game_state'),
    path('object-catalog/', views.get_object_catalog, name='object_catalog'),
    path('craft/', views.craft_objects, name='craft'),
    path('place/', views.place_object, name='place'),
    path('remove/', views.remove_object, name='remove'),
    path('unlock-era/', views.unlock_era, name='unlock_era'),
    path('export/', views.export_game, name='export'),
    path('import/', views.import_game, name='import'),
    path('redeem-upgrade-key/', views.redeem_upgrade_key, name='redeem_upgrade_key'),
]
