from flask import current_app

from .events import build_screening_nodes_and_offer_nodes
from .media import build_trailer_node
from .movie import build_faq_node, build_movie_node
from .offers import build_offer_nodes_and_refs
from .organization import build_organization_node
from .people import build_person_nodes_and_refs
from .reviews import build_aggregate_rating_node, build_review_nodes


def build_movie_schema_graph(movie):
    base_url = current_app.config['SITE_URL'].rstrip('/')
    movie_id = f'{base_url}/#movie'
    organization_id = f'{base_url}/#organization'
    trailer_id = f'{base_url}/#trailer'

    person_nodes, person_refs_by_role, contributor_refs = build_person_nodes_and_refs(
        movie,
        base_url,
    )
    organization_node = build_organization_node(movie, organization_id)
    trailer_node = build_trailer_node(
        movie,
        trailer_id,
        movie_id,
        organization_id,
        person_refs_by_role,
    )
    review_nodes = build_review_nodes(movie, base_url, movie_id)
    screening_nodes, screening_offer_nodes = build_screening_nodes_and_offer_nodes(
        movie,
        base_url,
        movie_id,
        organization_id,
    )
    movie_offer_nodes, movie_offer_refs = build_offer_nodes_and_refs(
        movie,
        base_url,
        movie_id,
        organization_id,
    )

    graph = [
        build_movie_node(
            movie,
            base_url,
            movie_id,
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
        build_aggregate_rating_node(movie, base_url, movie_id),
        *person_nodes,
        *review_nodes,
        *screening_nodes,
        *screening_offer_nodes,
        *movie_offer_nodes,
    ]

    faq_node = build_faq_node(movie, base_url)
    if faq_node:
        graph.append(faq_node)

    return {'@context': 'https://schema.org', '@graph': graph}
