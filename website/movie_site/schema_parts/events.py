from . import render_schema_template
from ..db import get_dict_cursor


def build_screening_nodes_and_offer_nodes(movie_id, base_url, organization_id):
    screening_nodes = []
    screening_offer_nodes = []
    cursor = get_dict_cursor()

    cursor.execute(
        "SELECT * FROM screening_event WHERE movie_id = %s", (movie_id,))
    screenings = cursor.fetchall()

    for index, screening in enumerate(screenings, start=1):
        screening_id = f'{base_url}/#screening-{index}'
        offer_refs = []

        cursor.execute(
            "SELECT o.* FROM offer o JOIN screening_offer so ON o.id = so.offer_id WHERE so.screening_event_id = %s", (screening['id'],))
        offers = cursor.fetchall()

        for offer_index, offer in enumerate(offers, start=1):
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
        screening['location'] = {
            'name': screening.get('location_name'),
            'url': screening.get('location_url'),
            'address': {
                'street_address': screening.get('location_street_address'),
                'address_locality': screening.get('location_locality'),
                'address_region': screening.get('location_region'),
                'postal_code': screening.get('location_postal_code'),
                'address_country': screening.get('location_country'),
            },
        }
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

    cursor.close()
    return screening_nodes, screening_offer_nodes
