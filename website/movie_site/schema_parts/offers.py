from . import render_schema_template


def build_movie_offer_nodes_and_refs(movie, base_url, movie_id, organization_id):
    movie_offer_nodes = []
    movie_offer_refs = []

    for index, offer in enumerate(movie.get('offers', []), start=1):
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

    return movie_offer_nodes, movie_offer_refs
