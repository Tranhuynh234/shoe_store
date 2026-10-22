def register_blueprints(app):
    from .main import bp as main_bp
    from .auth import bp as auth_bp
    from .account import bp as account_bp
    from .cart import bp as cart_bp, api_orders_bp
    from .admin import bp as admin_bp
    for bp in (main_bp, auth_bp, account_bp, cart_bp, api_orders_bp, admin_bp):
        app.register_blueprint(bp)
