from flask import url_for

from website.movie_site import views
from shared import movie_data
from shared.movie_data import get_movie_data, get_movie_page_context
from shared.content_store import get_content_reader


class TestMovieData:
    """Test movie data loading from configured content store."""

    def test_get_movie_data_structure(self, app):
        with app.app_context():
            data = get_movie_data()

        required_fields = [
            'title', 'tagline', 'description', 'genre', 'keywords',
            'runtime', 'duration_iso', 'release_date', 'release_status'
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
            assert data[field], f"Field {field} should not be empty"

        assert isinstance(data['keywords'], list)
        assert isinstance(data['title'], str)

    def test_get_movie_page_context(self, app):
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
        response = client.get('/')
        assert response.status_code == 200
        assert b'Open Mic Odyssey' in response.data

    def test_film_page(self, client):
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
        response = client.get('/media')
        assert response.status_code == 200

    def test_connect_page(self, client):
        response = client.get('/connect')
        assert response.status_code == 200

    def test_patreon_page(self, client):
        response = client.get('/patreon')
        assert response.status_code == 200

    def test_schema_json_generation(self, client):
        response = client.get('/film')
        assert response.status_code == 200

        assert b'@context' in response.data
        assert b'@type' in response.data

    def test_static_files(self, client):
        response = client.get('/static/css/site.css')
        assert response.status_code == 200
        assert b'body' in response.data

    def test_404_page(self, client):
        response = client.get('/nonexistent')
        assert response.status_code == 404

    def test_robots_txt_allows_indexing(self, client):
        response = client.get('/robots.txt')
        assert response.status_code == 200
        assert response.mimetype == 'text/plain'
        assert b'User-agent: *' in response.data
        assert b'Allow: /' in response.data

    def test_sitemap_xml_includes_pages_and_media_assets(self, app):
        app.config['SITE_URL'] = 'https://example.com/'
        client = app.test_client()

        response = client.get('/sitemap.xml')
        assert response.status_code == 200
        assert response.mimetype == 'application/xml'

        body = response.get_data(as_text=True)
        assert '<?xml version="1.0" encoding="UTF-8"?>' in body
        assert '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' in body

        assert '<loc>https://example.com/</loc>' in body
        assert '<loc>https://example.com/film</loc>' in body
        assert '<loc>https://example.com/media</loc>' in body
        assert '<loc>https://example.com/connect</loc>' in body
        assert '<loc>https://example.com/patreon</loc>' in body
        assert '<loc>https://example.com/watch</loc>' in body
        assert '<loc>https://example.com/credits</loc>' in body

        assert '<loc>https://example.com/static/images/poster.jpg</loc>' in body
        assert '<loc>https://example.com/static/images/trailer_thumbnail.png</loc>' in body
