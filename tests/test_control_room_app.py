import pytest
from werkzeug.security import generate_password_hash

from control_room.app import create_app as create_control_room_app


class TestAdminFlows:
    """Test admin auth and representative save flows."""

    @staticmethod
    def _admin_app():
        app = create_control_room_app()
        app.config.update(
            TESTING=False,
            ADMIN_USERNAME='editor',
            ADMIN_PASSWORD_HASH=generate_password_hash('secret-pass'),
        )
        return app

    @staticmethod
    def _login(client, next_path: str | None = None):
        login_path = '/login'
        if next_path:
            login_path = f'/login?next={next_path}'
        return client.post(
            login_path,
            data={'username': 'editor', 'password': 'secret-pass'},
            follow_redirects=False,
        )

    def test_admin_protected_route_redirects_to_login(self):
        app = self._admin_app()
        client = app.test_client()

        response = client.get('/content/film')

        assert response.status_code == 302
        assert '/login?next=' in response.headers['Location']

    def test_admin_login_rejects_invalid_credentials(self):
        app = self._admin_app()
        client = app.test_client()

        response = client.post(
            '/login',
            data={'username': 'editor', 'password': 'wrong-pass'},
        )

        assert response.status_code == 200
        assert b'Invalid credentials' in response.data

    def test_admin_login_redirects_to_requested_page(self):
        app = self._admin_app()
        client = app.test_client()

        response = self._login(client, '/content/film')

        assert response.status_code == 302
        assert response.headers['Location'].endswith('/content/film')

    def test_admin_login_accepts_plaintext_password_env(self):
        app = self._admin_app()
        app.config.update(
            ADMIN_PASSWORD='secret-pass',
            ADMIN_PASSWORD_HASH='not-a-valid-hash',
        )
        client = app.test_client()

        response = self._login(client)

        assert response.status_code == 302
        assert response.headers['Location'].endswith('/')

    def test_admin_login_falls_back_when_db_hash_is_invalid(self, monkeypatch):
        app = self._admin_app()
        client = app.test_client()

        from control_room import user_repo

        monkeypatch.setattr(
            user_repo,
            'get_user_by_username',
            lambda username: {
                'id': 1,
                'username': username,
                'password_hash': 'invalid-hash-format',
            },
        )

        response = self._login(client)

        assert response.status_code == 302
        assert response.headers['Location'].endswith('/')

    def test_admin_dashboard_links_to_bot_control_room(self):
        app = self._admin_app()
        client = app.test_client()

        login_response = self._login(client)
        assert login_response.status_code == 302

        response = client.get('/')

        assert response.status_code == 200
        assert b'Discord Bot' in response.data
        assert b'api.openmicodyssey.com' in response.data

    def test_admin_media_page_renders(self):
        app = self._admin_app()
        client = app.test_client()

        with client.session_transaction() as session:
            session['_user_id'] = 'editor'
            session['_fresh'] = True

        response = client.get('/content/media')

        assert response.status_code == 200
        assert b'Manage Media Gallery' in response.data

    @pytest.mark.parametrize(
        ('path', 'marker'),
        [
            ('/content/content', b'Manage per-page SEO content'),
            ('/content/faq', b'Add FAQ Entry'),
            ('/content/people', b'Manage People'),
            ('/content/connect/social', b'Social Links'),
            ('/content/connect/supporters', b'Supporter Links'),
            ('/content/connect/patreon', b'Page Copy'),
            ('/content/media-assets', b'Poster image URL'),
            ('/content/reviews', b'Manage Reviews'),
        ],
    )
    def test_admin_extracted_content_pages_render(self, path, marker):
        app = self._admin_app()
        client = app.test_client()

        login_response = self._login(client)
        assert login_response.status_code == 302

        response = client.get(path)

        assert response.status_code == 200
        assert marker in response.data

    def test_admin_connect_root_redirects_to_social(self):
        app = self._admin_app()
        client = app.test_client()

        login_response = self._login(client)
        assert login_response.status_code == 302

        response = client.get('/content/connect', follow_redirects=False)

        assert response.status_code == 302
        assert response.headers['Location'].endswith('/content/connect/social')

    def test_admin_film_post_writes_updated_movie_payload(self, monkeypatch):
        app = self._admin_app()
        client = app.test_client()

        class FakeReader:
            def read(self, logical_file: str):
                assert logical_file == 'movies.json'
                return {
                    'movie': {
                        'title': 'Old Title',
                        'tagline': 'Old Tagline',
                        'description': 'Old Description',
                        'genre': 'Documentary',
                        'runtime': '80 min',
                        'duration_iso': 'PT80M',
                        'release_date': '2026-01-01',
                        'release_status': {
                            'label': 'Old Label',
                            'headline': 'Old Headline',
                            'summary': 'Old Summary',
                            'detail': 'Old Detail',
                        },
                    }
                }

        class FakeWriter:
            def __init__(self):
                self.calls: list[tuple[str, dict]] = []

            def write(self, logical_file: str, payload: dict):
                self.calls.append((logical_file, payload))

        fake_writer = FakeWriter()
        from control_room import admin_content as cr_admin_content
        monkeypatch.setattr(
            cr_admin_content, 'get_content_reader', lambda: FakeReader())
        monkeypatch.setattr(
            cr_admin_content, 'get_content_writer', lambda: fake_writer)

        login_response = self._login(client)
        assert login_response.status_code == 302

        response = client.post(
            '/content/film',
            data={
                'title': 'Open Mic Odyssey: The Movie',
                'tagline': 'Three best friends embark on an outrageous journey.',
                'description': 'A documentary road story about stand-up stages, hotel suites, long drives, and the emotional math of trying to make a creative life real.',
                'genre': 'Documentary',
                'runtime': '180 min',
                'duration_iso': 'PT180M',
                'release_date': '2026-08-18',
                'release_status_label': 'Post-Production',
                'release_status_headline': 'Trailer streaming now',
                'release_status_summary': 'Fresh summary',
                'release_status_detail': 'Fresh detail',
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers['Location'].endswith('/content/film?saved=1')
        assert len(fake_writer.calls) == 1

        logical_file, payload = fake_writer.calls[0]
        assert logical_file == 'movies.json'
        assert payload['movie']['title'] == 'Open Mic Odyssey: The Movie'
        assert payload['movie']['release_status']['label'] == 'Post-Production'
        assert payload['movie']['release_status']['headline'] == 'Trailer streaming now'
