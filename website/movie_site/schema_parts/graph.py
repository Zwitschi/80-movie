from ..db import get_dict_cursor
from ..movie_data import PRODUCTION_COMPANY_NAME
from flask import current_app

from .events import build_screening_nodes_and_offer_nodes
from .media import build_trailer_node
from .movie import build_faq_node, build_movie_node
from .offers import build_offer_nodes_and_refs
from .organization import build_organization_node
from .people import build_person_nodes_and_refs
from .reviews import build_aggregate_rating_node, build_review_nodes


def _resolve_movie_id(movie):
    if isinstance(movie, str):
        return movie
    if isinstance(movie, dict) and movie.get('id'):
        return movie['id']

    cursor = get_dict_cursor()
    if isinstance(movie, dict) and movie.get('title'):
        cursor.execute("SELECT id FROM movie WHERE title = %s", (movie['title'],))
    else:
        cursor.execute("SELECT id FROM movie ORDER BY created_at LIMIT 1")
    row = cursor.fetchone()
    cursor.close()
    return row['id'] if row else None


def build_movie_schema_graph(movie):
    base_url = current_app.config['SITE_URL'].rstrip('/')
    movie_id = _resolve_movie_id(movie)
    if not movie_id:
        return {'@context': 'https://schema.org', '@graph': []}

    organization_id = f'{base_url}/#organization'
    trailer_id = f'{base_url}/#trailer'
    organization_name = PRODUCTION_COMPANY_NAME
    if isinstance(movie, dict):
        organization_name = movie.get(
            'production_company', {}).get('name', PRODUCTION_COMPANY_NAME)
        person_nodes, person_refs_by_role, contributor_refs = build_person_nodes_and_refs(
            movie, base_url)
    else:
        person_nodes, person_refs_by_role, contributor_refs = [], {}, []

    organization_node = build_organization_node(organization_id, organization_name)
    trailer_node = build_trailer_node(
        trailer_id,
        movie_id,
        organization_id,
    )
    review_nodes = build_review_nodes(movie_id, base_url)
    screening_nodes, screening_offer_nodes = build_screening_nodes_and_offer_nodes(
        movie_id,
        base_url,
        organization_id,
    )
    movie_offer_nodes, movie_offer_refs = build_offer_nodes_and_refs(
        movie_id,
        base_url,
        organization_id,
    )

    graph = [
        build_movie_node(
            movie_id,
            base_url,
            organization_id,
            trailer_id,
            person_refs_by_role,
            contributor_refs,
            review_nodes,
            screening_nodes,
            movie_offer_refs,
        ),
        organization_node,
        trailer_node,
        build_aggregate_rating_node(movie_id, base_url),
        *person_nodes,
        *review_nodes,
        *screening_nodes,
        *screening_offer_nodes,
        *movie_offer_nodes,
    ]

    faq_node = build_faq_node(movie_id, base_url)
    if faq_node:
        graph.append(faq_node)

    return {
        '@context': 'https://schema.org',
        '@graph': [node for node in graph if node is not None],
    }
