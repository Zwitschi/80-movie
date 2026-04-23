from . import render_schema_template


def build_screening_nodes_and_offer_nodes(movie, base_url, movie_id, organization_id):
    screening_nodes = []
    screening_offer_nodes = []

    for index, screening in enumerate(movie.get('screenings', []), start=1):
        screening_id = f'{base_url}/#screening-{index}'
        offer_refs = []
        for offer_index, offer in enumerate(screening.get('offers', []), start=1):
            offer_id = f'{screening_id}-offer-{offer_index}'
            offer_refs.append({'@id': offer_id})
            screening_offer_nodes.append(
                render_schema_template(
                    'offer.json',
                    offer_id=offer_id,
                    offer=offer,
                    offered_by={'@id': organization_id},
                    item_offered={'@id': screening_id},
                )
            )
        screening_nodes.append(
            render_schema_template(
                'screening_event.json',
                screening_id=screening_id,
                screening=screening,
                movie_id=movie_id,
                organization_id=organization_id,
                offer_refs=offer_refs,
            )
        )

    return screening_nodes, screening_offer_nodes
