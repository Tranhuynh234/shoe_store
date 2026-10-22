from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Vui lòng đăng nhập để tiếp tục."
login_manager.login_message_category = "warning"
login_manager.session_protection = "strong"


@login_manager.user_loader
def load_user(user_id):
    """Nạp tài khoản đăng nhập từ session Flask-Login bằng khóa chính users.id."""
    # Import trễ để tránh vòng lặp khi app/extensions/models được khởi tạo.
    from .models import User
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None
