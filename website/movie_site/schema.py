import json

from flask import current_app, render_template


def render_schema_template(template_name, **context):
    rendered = render_template(f'schema/{template_name}', **context)
    return json.loads(rendered)


def build_movie_schema_graph(movie):
    base_url = current_app.config['SITE_URL'].rstrip('/')
    movie_id = f'{base_url}/#movie'
    organization_id = f'{base_url}/#organization'
    trailer_id = f'{base_url}/#trailer'

    person_nodes = []
    person_refs_by_role = {}
    person_index = 1
    for role_name in ('directors', 'producers', 'actors'):
        refs = []
        for person in movie['contributors'].get(role_name, []):
            person_id = f'{base_url}/#person-{person_index}'
            person_index += 1
            refs.append({'@id': person_id})
            person_nodes.append(
                render_schema_template(
                    'person.json',
                    person_id=person_id,
                    person=person,
                )
            )
        person_refs_by_role[role_name] = refs

    organization_node = render_schema_template(
        'organization.json',
        organization_id=organization_id,
        organization=movie['production_company'],
    )

    trailer_node = render_schema_template(
        'video_object.json',
        trailer_id=trailer_id,
        trailer=movie['trailer'],
        movie_id=movie_id,
        organization_id=organization_id,
        director_refs=person_refs_by_role['directors'],
        actor_refs=person_refs_by_role['actors'],
    )

    review_nodes = []
    for index, review in enumerate(movie.get('reviews', []), start=1):
        review_nodes.append(
            render_schema_template(
                'review.json',
                review_id=f'{base_url}/#review-{index}',
                review=review,
                movie_id=movie_id,
            )
        )

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

    graph = [
        render_schema_template(
            'movie.json',
            movie_id=movie_id,
            movie=movie,
            base_url=base_url,
            organization_id=organization_id,
            trailer_id=trailer_id,
            director_refs=person_refs_by_role['directors'],
            producer_refs=person_refs_by_role['producers'],
            actor_refs=person_refs_by_role['actors'],
            review_refs=[{'@id': node['@id']} for node in review_nodes],
            screening_refs=[{'@id': node['@id']} for node in screening_nodes],
            offer_refs=movie_offer_refs,
            schema_version=current_app.config['SCHEMA_ORG_VERSION_URL'],
        ),
        organization_node,
        trailer_node,
        render_schema_template(
            'aggregate_rating.json',
            rating_id=f'{base_url}/#aggregate-rating',
            aggregate_rating=movie['aggregate_rating'],
            movie_id=movie_id,
        ),
        *person_nodes,
        *review_nodes,
        *screening_nodes,
        *screening_offer_nodes,
        *movie_offer_nodes,
    ]

    if movie.get('faq_items'):
        graph.append(
            render_schema_template(
                'faq_page.json',
                faq_id=f'{base_url}/#faq',
                page_url=f'{base_url}/#faq',
                faq_items=movie['faq_items'],
            )
        )

    return {'@context': 'https://schema.org', '@graph': graph}


def build_movie_schema_json(movie):
    return json.dumps(build_movie_schema_graph(movie), indent=2, sort_keys=False)
