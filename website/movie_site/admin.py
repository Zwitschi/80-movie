from flask import Blueprint, redirect

# Redirect /admin to `https://admin.openmicodyssey.com`
admin_blueprint = Blueprint('admin', __name__)


@admin_blueprint.route('/')
def admin_redirect():
    return redirect('https://admin.openmicodyssey.com')
