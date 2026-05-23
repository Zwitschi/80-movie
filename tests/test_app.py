import pytest
from flask import url_for
from werkzeug.security import generate_password_hash

from website.app import create_app
from website.movie_site import views
from shared import movie_data
from shared.movie_data import get_movie_data, get_movie_page_context
from shared.content_store import get_content_reader
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


class TestServiceSeparation:
    """Test that routes are correctly separated between website and control room."""

    def test_website_no_admin_routes(self, client):
        """Test that website does not serve admin routes."""
        # Flask-Login might redirect to login if not authenticated,
        # but we want to ensure the routes aren't even registered or behave as public-only.
        # In our new structure, /admin isn't registered in website.
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


class TestMovieData:
    """Test movie data loading from configured content store."""

    def test_get_movie_data_structure(self, app):
        """Test that get_movie_data returns expected structure."""
        with app.app_context():
            data = get_movie_data()

        # Check core movie fields
        required_fields = [
            'title', 'tagline', 'description', 'genre', 'keywords',
            'runtime', 'duration_iso', 'release_date', 'release_status'
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
            assert data[field], f"Field {field} should not be empty"

        # Check data types
        assert isinstance(data['keywords'], list), "keywords should be a list"
        assert isinstance(data['title'], str), "title should be a string"

    def test_get_movie_page_context(self, app):
        """Test that get_movie_page_context returns proper context."""
        with app.app_context():
            context = get_movie_page_context(2026)

        required_keys = [
            'movie', 'movie_title', 'movie_tagline', 'movie_description',
            'movie_genre', 'movie_runtime', 'release_date', 'release_status',
            'current_year'
        ]

        for key in required_keys:
            assert key in context, f"Missing context key: {key}"

        assert context['current_year'] == 2026

    def test_content_store_payload_integrity(self, app):
        """Test that content store exposes expected logical payloads."""
        logical_files = [
            'movies.json', 'people.json', 'organizations.json',
            'media_assets.json', 'events.json', 'reviews.json',
            'offers.json', 'faq.json', 'gallery.json', 'social.json',
            'connect.json'
        ]

        with app.app_context():
            payloads = get_content_reader().read_all()

        for logical_file in logical_files:
            assert logical_file in payloads, f"Missing content payload: {logical_file}"
            assert isinstance(payloads[logical_file], dict), (
                f"Payload root should be dict: {logical_file}"
            )

    def test_db_content_reader_exposes_movie_payload(self, app):
        """Test DB-backed content reader returns the expected movie payload shape."""
        with app.app_context():
            payload = get_content_reader().read('movies.json')

        assert 'movie' in payload
        assert isinstance(payload['movie'], dict)
        assert payload['movie']['title']

    def test_get_movie_data_builds_distinct_cast_entries(self, app, monkeypatch):
        class FakeReader:
            def read_all(self):
                return {
                    'movies.json': {'movie': {'title': 'Open Mic Odyssey'}},
                    'media_assets.json': {'media': {}},
                    'reviews.json': {},
                    'offers.json': {},
                    'people.json': {
                        'people': {
                            'Alpha': {
                                'name': 'Alpha',
                                'credit_note': 'A touring comic finding her voice.',
                            },
                            'Beta': {
                                'name': 'Beta',
                                'credit_note': '',
                            },
                        },
                        'contributors': {},
                        'credits_people': [
                            {'name': 'Alpha', 'role': 'actor'},
                            {'name': 'Alpha', 'role': 'producer'},
                            {'name': 'Alpha', 'role': 'actor'},
                            {'name': 'Beta', 'role': 'actor'},
                        ],
                    },
                    'organizations.json': {'organizations': {}},
                    'events.json': {'events': []},
                    'faq.json': {'faq': []},
                    'gallery.json': {'gallery': []},
                    'social.json': {'social': []},
                    'connect.json': {'connect': {'page': {}, 'links': {}}},
                    'content.json': {'pages': {}},
                }

        monkeypatch.setattr(
            movie_data, 'get_content_reader', lambda _=None: FakeReader())

        with app.app_context():
            data = get_movie_data()

        assert data['cast_section_visible'] is True
        assert data['cast_people'] == [
            {
                'name': 'Alpha',
                'roles': ['actor', 'producer'],
                'description': 'A touring comic finding her voice.',
            },
            {
                'name': 'Beta',
                'roles': ['actor'],
                'description': '',
            },
        ]


class TestFlaskApp:
    """Test Flask application functionality."""

    def test_index_page(self, client):
        """Test that index page loads successfully."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Open Mic Odyssey' in response.data

    def test_film_page(self, client):
        """Test that film page loads successfully."""
        response = client.get('/film')
        assert response.status_code == 200
        assert b'Open Mic Odyssey' in response.data

    def test_film_page_renders_distinct_cast_entries_with_descriptions(self, app, monkeypatch):
        with app.app_context():
            context = views.build_page_context('film')

        context['movie'] = dict(context['movie'])
        context['movie']['cast_section_visible'] = True
        context['movie']['cast_people'] = [
            {
                'name': 'Alpha',
                'roles': ['actor', 'producer'],
                'description': 'A touring comic finding her voice.',
            },
            {
                'name': 'Beta',
                'roles': ['actor'],
                'description': '',
            },
        ]

        monkeypatch.setattr(views, 'build_page_context',
                            lambda page_key='film': context)
        client = app.test_client()

        response = client.get('/film')

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert '<h2>Cast</h2>' in body
        assert body.count('<h3>Alpha</h3>') == 1
        assert 'actor, producer' in body
        assert 'A touring comic finding her voice.' in body

    def test_film_page_hides_cast_section_when_no_descriptions_are_available(self, app, monkeypatch):
        with app.app_context():
            context = views.build_page_context('film')

        context['movie'] = dict(context['movie'])
        context['movie']['cast_section_visible'] = False
        context['movie']['cast_people'] = [
            {
                'name': 'Alpha',
                'roles': ['actor'],
                'description': '',
            },
        ]

        monkeypatch.setattr(views, 'build_page_context',
                            lambda page_key='film': context)
        client = app.test_client()

        response = client.get('/film')

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert '<h2>Cast</h2>' not in body

    def test_media_page(self, client):
        """Test that media page loads successfully."""
        response = client.get('/media')
        assert response.status_code == 200

    def test_connect_page(self, client):
        """Test that connect page loads successfully."""
        response = client.get('/connect')
        assert response.status_code == 200

    def test_patreon_page(self, client):
        """Test that patreon page loads successfully."""
        response = client.get('/patreon')
        assert response.status_code == 200

    def test_schema_json_generation(self, client):
        """Test that schema JSON is generated and valid."""
        response = client.get('/film')
        assert response.status_code == 200

        # Check that schema JSON is present in the HTML
        assert b'@context' in response.data
        assert b'@type' in response.data

    def test_static_files(self, client):
        """Test that static files are served."""
        response = client.get('/static/css/site.css')
        assert response.status_code == 200
        assert b'body' in response.data  # Basic CSS check

    def test_404_page(self, client):
        """Test 404 error handling."""
        response = client.get('/nonexistent')
        assert response.status_code == 404

    def test_robots_txt_allows_indexing(self, client):
        """Test robots.txt allows indexing."""
        response = client.get('/robots.txt')
        assert response.status_code == 200
        assert response.mimetype == 'text/plain'
        assert b'User-agent: *' in response.data
        assert b'Allow: /' in response.data

    def test_sitemap_xml_includes_pages_and_media_assets(self, app):
        """Test sitemap.xml includes static pages and media assets with SITE_URL base."""
        app.config['SITE_URL'] = 'https://example.com/'
        client = app.test_client()

        response = client.get('/sitemap.xml')
        assert response.status_code == 200
        assert response.mimetype == 'application/xml'

        body = response.get_data(as_text=True)
        assert '<?xml version="1.0" encoding="UTF-8"?>' in body
        assert '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' in body

        # Static pages
        assert '<loc>https://example.com/</loc>' in body
        assert '<loc>https://example.com/film</loc>' in body
        assert '<loc>https://example.com/media</loc>' in body
        assert '<loc>https://example.com/connect</loc>' in body
        assert '<loc>https://example.com/patreon</loc>' in body
        assert '<loc>https://example.com/watch</loc>' in body
        assert '<loc>https://example.com/credits</loc>' in body

        # Media assets
        assert '<loc>https://example.com/static/images/poster.jpg</loc>' in body
        assert '<loc>https://example.com/static/images/trailer_thumbnail.png</loc>' in body


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
