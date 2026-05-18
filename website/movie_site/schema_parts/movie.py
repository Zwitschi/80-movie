from flask import current_app

from . import render_schema_template
from ..db import get_dict_cursor


def build_movie_node(
    movie_id,
    base_url,
    organization_id,
    trailer_id,
    person_refs_by_role,
    contributor_refs,
    review_nodes,
    screening_nodes,
    movie_offer_refs,
):
    cursor = get_dict_cursor()

    cursor.execute("SELECT * FROM movie WHERE id = %s", (movie_id,))
    movie = cursor.fetchone()

    if not movie:
        cursor.close()
        return None

    cursor.close()

    return render_schema_template(
        'movie.json',
        movie_id=movie_id,
        movie=movie,
        base_url=base_url,
        organization_id=organization_id,
        trailer_id=trailer_id,
        director_refs=person_refs_by_role.get('directors', []),
        producer_refs=person_refs_by_role.get('producers', []),
        actor_refs=person_refs_by_role.get('actors', []),
        contributor_refs=contributor_refs,
        review_refs=[{'@id': node['@id']} for node in review_nodes],
        screening_refs=[{'@id': node['@id']} for node in screening_nodes],
        offer_refs=movie_offer_refs,
        schema_version=current_app.config['SCHEMA_ORG_VERSION_URL'],
    )

def build_faq_node(movie_id, base_url):
    cursor = get_dict_cursor()

    cursor.execute(
        "SELECT * FROM faq_item WHERE movie_id = %s ORDER BY sort_order", (movie_id,))
    faq_items = cursor.fetchall()

    cursor.close()

    if not faq_items:
        return None

    return render_schema_template(
        'faq_page.json',
        faq_id=f'{base_url}/#faq',
        page_url=f'{base_url}/#faq',
        faq_items=faq_items,
    )
