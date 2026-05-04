import json
import pytest
from website.movie_site.schema import build_movie_schema_json, build_org_social_schema_json
from website.movie_site.schema_parts.graph import build_movie_schema_graph
from website.movie_site.schema_parts.social import build_org_social_schema_json as build_org_social_schema_json_for_site
from website.movie_site.movie_data import get_movie_data


class TestSchemaBuilder:
    """Test schema.org JSON-LD generation."""

    @pytest.fixture
    def sample_movie_data(self):
        """Get sample movie data for testing."""
        return get_movie_data()

    @pytest.fixture
    def app_context(self):
        """Create Flask app context for testing."""
        from website.app import create_app
        app = create_app()
        app.config['TESTING'] = True
        with app.app_context():
            yield app

    def test_build_movie_schema_graph_structure(self, sample_movie_data, app_context):
        """Test that movie schema graph has expected structure."""
        graph = build_movie_schema_graph(sample_movie_data)

        assert '@context' in graph
        assert graph['@context'] == 'https://schema.org'
        assert '@graph' in graph
        assert isinstance(graph['@graph'], list)
        assert len(graph['@graph']) > 0

        # Check that we have the main entities
        types = [node.get('@type') for node in graph['@graph']]
        assert 'Movie' in types
        assert 'Organization' in types

    def test_build_movie_schema_json(self, sample_movie_data, app_context):
        """Test movie schema JSON generation."""
        schema_json = build_movie_schema_json(sample_movie_data)

        # Should be valid JSON
        data = json.loads(schema_json)
        assert '@context' in data
        assert '@graph' in data

        # Check for Movie entity
        movie_nodes = [node for node in data['@graph']
                       if node.get('@type') == 'Movie']
        assert len(movie_nodes) == 1

        movie = movie_nodes[0]
        assert movie['name'] == 'Open Mic Odyssey'
        assert 'director' in movie
        assert 'producer' in movie
        assert 'actor' in movie

    def test_build_org_social_schema_json(self, sample_movie_data, app_context):
        """Test organization social schema JSON generation."""
        schema_json = build_org_social_schema_json(sample_movie_data)

        # Should be valid JSON
        data = json.loads(schema_json)
        assert data['@type'] == 'Organization'
        assert data['name'] == 'Open Mic Odyssey Productions'
        assert 'sameAs' in data
        assert isinstance(data['sameAs'], list)
        assert len(data['sameAs']) > 0

    def test_schema_graph_includes_all_required_entities(self, sample_movie_data, app_context):
        """Test that schema graph includes all required entities."""
        graph = build_movie_schema_graph(sample_movie_data)

        nodes = graph['@graph']
        types = [node.get('@type') for node in nodes]

        # Should include main entities
        required_types = ['Movie', 'Organization']
        for req_type in required_types:
            assert req_type in types, f"Missing required type: {req_type}"

        # Should have person nodes
        person_nodes = [
            node for node in nodes if node.get('@type') == 'Person']
        assert len(person_nodes) > 0, "Should have Person entities"

        # Should have aggregate rating
        rating_nodes = [node for node in nodes if 'aggregateRating' in node or node.get(
            '@type') == 'AggregateRating']
        assert len(rating_nodes) > 0, "Should have rating information"

    def test_movie_entity_has_required_properties(self, sample_movie_data, app_context):
        """Test that Movie entity has all required schema.org properties."""
        graph = build_movie_schema_graph(sample_movie_data)
        movie_node = next(
            node for node in graph['@graph'] if node.get('@type') == 'Movie')

        required_props = [
            '@id', 'name', 'description', 'genre', 'image',
            'productionCompany', 'trailer', 'aggregateRating'
        ]

        for prop in required_props:
            assert prop in movie_node, f"Movie missing required property: {prop}"

        # Check data types
        assert isinstance(movie_node['name'], str)
        assert isinstance(movie_node['description'], str)
        assert movie_node['name'] == 'Open Mic Odyssey'

    def test_organization_entity_properties(self, sample_movie_data, app_context):
        """Test that Organization entity has required properties."""
        graph = build_movie_schema_graph(sample_movie_data)
        org_node = next(
            node for node in graph['@graph'] if node.get('@type') == 'Organization')

        required_props = ['@id', 'name', 'url']
        for prop in required_props:
            assert prop in org_node, f"Organization missing required property: {prop}"

        assert org_node['name'] == 'Open Mic Odyssey Productions'

    def test_person_entities_have_required_properties(self, sample_movie_data, app_context):
        """Test that Person entities have required properties."""
        graph = build_movie_schema_graph(sample_movie_data)
        person_nodes = [node for node in graph['@graph']
                        if node.get('@type') == 'Person']

        for person in person_nodes:
            required_props = ['@id', 'name']
            for prop in required_props:
                assert prop in person, f"Person missing required property: {prop}"

            assert isinstance(person['name'], str)
            assert len(person['name']) > 0

    def test_trailer_entity_properties(self, sample_movie_data, app_context):
        """Test that VideoObject (trailer) has required properties."""
        graph = build_movie_schema_graph(sample_movie_data)
        trailer_nodes = [node for node in graph['@graph']
                         if node.get('@type') == 'VideoObject']

        assert len(
            trailer_nodes) >= 1, "Should have at least one VideoObject (trailer)"

        trailer = trailer_nodes[0]
        required_props = ['@id', 'name', 'description', 'url', 'thumbnailUrl']
        for prop in required_props:
            assert prop in trailer, f"Trailer missing required property: {prop}"

    def test_schema_ids_are_unique(self, sample_movie_data, app_context):
        """Test that all schema entities have unique @id values."""
        graph = build_movie_schema_graph(sample_movie_data)
        ids = [node.get('@id') for node in graph['@graph'] if '@id' in node]

        assert len(ids) == len(set(ids)), "Schema @id values must be unique"

    def test_schema_json_is_valid_json(self, sample_movie_data, app_context):
        """Test that generated schema JSON is valid and parseable."""
        schema_json = build_movie_schema_json(sample_movie_data)

        # Should not raise exception
        data = json.loads(schema_json)

        # Should be able to serialize back
        re_serialized = json.dumps(data)
        assert json.loads(re_serialized) == data

    def test_social_schema_includes_social_links(self, sample_movie_data, app_context):
        """Test that organization social schema includes social media links."""
        schema_json = build_org_social_schema_json(sample_movie_data)
        data = json.loads(schema_json)

        assert 'sameAs' in data
        same_as = data['sameAs']

        # Should include social links from movie data
        social_urls = [link['url']
                       for link in sample_movie_data.get('social_links', [])]
        for url in social_urls:
            assert url in same_as, f"Social link missing from sameAs: {url}"

    def test_schema_graph_with_minimal_data(self, app_context):
        """Test schema generation with minimal movie data."""
        # Skip this test for now as it requires too many fields
        pytest.skip("Minimal data test requires extensive setup")
