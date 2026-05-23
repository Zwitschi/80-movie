import pytest

from website.app import create_app
from control_room.app import create_app as create_control_room_app


@pytest.fixture
def app():
    """Create and configure a test app instance."""
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def control_room_app():
    """Create and configure a test control room app instance."""
    app = create_control_room_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def control_room_client(control_room_app):
    """A test client for the control room app."""
    return control_room_app.test_client()
