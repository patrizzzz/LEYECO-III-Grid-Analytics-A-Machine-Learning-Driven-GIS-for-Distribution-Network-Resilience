from .asset_routes import asset_api_bp
from .import_routes import import_api_bp
from .analysis_routes import analysis_api_bp
from .user_routes import user_api_bp

# These can be registered individually in app.py or as a collection
__all__ = ['asset_api_bp', 'import_api_bp', 'analysis_api_bp', 'user_api_bp']
