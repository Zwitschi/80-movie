import pytest
import json
from website.app import create_app
from website.movie_site.movie_data import get_movie_data, get_movie_page_context


class TestMovieData:
    """Test movie data loading from JSON files."""

    def test_get_movie_data_structure(self):
        """Test that get_movie_data returns expected structure."""
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

    def test_get_movie_page_context(self):
        """Test that get_movie_page_context returns proper context."""
        context = get_movie_page_context(2026)

        required_keys = [
            'movie', 'movie_title', 'movie_tagline', 'movie_description',
            'movie_genre', 'movie_runtime', 'release_date', 'release_status',
            'current_year'
        ]

        for key in required_keys:
            assert key in context, f"Missing context key: {key}"

        assert context['current_year'] == 2026

    def test_json_data_integrity(self):
        """Test that JSON files contain valid data."""
        import os
        data_dir = os.path.join(os.path.dirname(
            __file__), '..', 'website', 'data')

        json_files = [
            'movies.json', 'people.json', 'organizations.json',
            'media_assets.json', 'events.json', 'reviews.json',
            'offers.json', 'faq.json', 'gallery.json', 'social.json',
            'connect.json'
        ]

        for json_file in json_files:
            file_path = os.path.join(data_dir, json_file)
            assert os.path.exists(file_path), f"JSON file missing: {json_file}"

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                assert data, f"JSON file is empty: {json_file}"
                assert isinstance(
                    data, dict), f"JSON root should be dict: {json_file}"


class TestFlaskApp:
    """Test Flask application functionality."""

    @pytest.fixture
    def app(self):
        """Create and configure a test app instance."""
        app = create_app()
        app.config['TESTING'] = True
        return app

    @pytest.fixture
    def client(self, app):
        """A test client for the app."""
        return app.test_client()

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
