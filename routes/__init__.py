from flask import Blueprint

# Define blueprints
auth_bp = Blueprint('auth', __name__)
main_bp = Blueprint('main', __name__)
api_bp = Blueprint('api', __name__)

from . import auth_routes, main_routes, api_routes
