class TestServiceSeparation:
    """Test that routes are correctly separated between website and control room."""

    def test_website_no_admin_routes(self, client):
        """Test that website does not serve admin routes."""
        response = client.get('/admin/')
        assert response.status_code == 404

        response = client.get('/login')
        assert response.status_code == 404

    def test_control_room_has_admin_routes(self, control_room_client):
        """Test that control room serves admin routes."""
        response = control_room_client.get('/login')
        assert response.status_code == 200
        assert b'Login' in response.data

    def test_website_public_routes(self, client):
        """Test that website public routes work."""
        response = client.get('/')
        assert response.status_code == 200

        response = client.get('/film')
        assert response.status_code == 200

    def test_control_room_no_public_frontend_routes(self, control_room_client):
        """Test that control room does not serve public frontend routes."""
        response = control_room_client.get('/')
        assert response.status_code == 200

        response = control_room_client.get('/film')
        assert response.status_code == 404
