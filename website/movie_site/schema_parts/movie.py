from flask import current_app

from . import render_schema_template


def build_movie_node(
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
):
    return render_schema_template(
        'movie.json',
        movie_id=movie_id,
        movie=movie,
        base_url=base_url,
        organization_id=organization_id,
        trailer_id=trailer_id,
        director_refs=person_refs_by_role['directors'],
        producer_refs=person_refs_by_role['producers'],
        actor_refs=person_refs_by_role['actors'],
        contributor_refs=contributor_refs,
        review_refs=[{'@id': node['@id']} for node in review_nodes],
        screening_refs=[{'@id': node['@id']} for node in screening_nodes],
        offer_refs=movie_offer_refs,
        schema_version=current_app.config['SCHEMA_ORG_VERSION_URL'],
    )


def build_faq_node(movie, base_url):
    if not movie.get('faq_items'):
        return None

    return render_schema_template(
        'faq_page.json',
        faq_id=f'{base_url}/#faq',
        page_url=f'{base_url}/#faq',
        faq_items=movie['faq_items'],
    )
