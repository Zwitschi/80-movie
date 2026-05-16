from . import render_schema_template
from ..db import get_dict_cursor


def build_offer_nodes_and_refs(movie_id, base_url, organization_id):
    movie_offer_nodes = []
    movie_offer_refs = []
    cursor = get_dict_cursor()

    cursor.execute(
        "SELECT o.* FROM offer o JOIN movie_offer mo ON o.id = mo.offer_id WHERE mo.movie_id = %s", (movie_id,))
    offers = cursor.fetchall()

    for index, offer in enumerate(offers, start=1):
        offer_id = f'{base_url}/#offer-{index}'
        movie_offer_refs.append({'@id': offer_id})
        movie_offer_nodes.append(
            render_schema_template(
                'offer.json',
                offer_id=offer_id,
                offer=offer,
                offered_by={'@id': organization_id},
                item_offered={'@id': movie_id},
            )
        )

    cursor.close()
    return movie_offer_nodes, movie_offer_refs
