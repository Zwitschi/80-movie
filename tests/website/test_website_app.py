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
            'movies', 'people', 'organizations',
            'media_assets', 'events', 'reviews',
            'offers', 'faq', 'gallery', 'social',
            'connect'
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
            payload = get_content_reader().read('movies')

        assert 'movie' in payload
        assert isinstance(payload['movie'], dict)
        assert payload['movie']['title']

    def test_get_movie_data_builds_distinct_cast_entries(self, app, monkeypatch):
        class FakeReader:
            def read_all(self):
                return {
                    'movies': {'movie': {'title': 'Open Mic Odyssey'}},
                    'media_assets': {'media': {}},
                    'reviews': {},
                    'offers': {},
                    'people': {
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
                    'organizations': {'organizations': {}},
                    'events': {'events': []},
                    'faq': {'faq': []},
                    'gallery': {'gallery': []},
                    'social': {'social': []},
                    'connect': {'connect': {'page': {}, 'links': {}}},
                    'content': {'pages': {}},
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

    def test_get_movie_data_builds_social_gallery_items(self, app, monkeypatch):
        class FakeReader:
            def read_all(self):
                return {
                    'movies': {'movie': {'title': 'Open Mic Odyssey'}},
                    'media_assets': {'media': {}},
                    'reviews': {},
                    'offers': {},
                    'people': {
                        'people': {},
                        'contributors': {},
                        'credits_people': [],
                    },
                    'organizations': {'organizations': {}},
                    'events': {'events': []},
                    'faq': {'faq': []},
                    'gallery': {'gallery': []},
                    'social': {
                        'social': [
                            {
                                'label': 'Instagram Post',
                                'url': 'https://www.instagram.com/p/C0FFEE123/',
                                'description': 'A still from the road.',
                            },
                            {
                                'label': 'TikTok Clip',
                                'url': 'https://www.tiktok.com/@openmicodyssey/video/7450123456789012345',
                                'description': 'Behind-the-scenes clip.',
                            },
                            {
                                'label': 'Instagram',
                                'url': 'https://www.instagram.com/openmicodyssey/',
                                'description': 'Official profile.',
                            },
                            {
                                'label': 'TikTok',
                                'url': 'https://www.tiktok.com/@openmicodyssey',
                                'description': 'Official TikTok account.',
                            },
                            {
                                'label': 'YouTube',
                                'url': 'https://www.youtube.com/@openmicodyssey',
                                'description': 'Channel link.',
                            },
                        ]
                    },
                    'connect': {'connect': {'page': {}, 'links': {}}},
                    'content': {'pages': {}},
                }

        monkeypatch.setattr(
            movie_data, 'get_content_reader', lambda _=None: FakeReader())

        with app.app_context():
            data = get_movie_data()

        assert len(data['social_gallery_items']) == 4
        assert len(data['social_gallery_embed_items']) == 2
        assert len(data['social_gallery_profile_items']) == 2
        assert data['social_gallery_embed_items'][0]['embed_url'] == (
            'https://www.instagram.com/p/C0FFEE123/embed/captioned/'
        )
        assert data['social_gallery_embed_items'][1]['embed_url'] == (
            'https://www.tiktok.com/embed/v2/7450123456789012345'
        )


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
