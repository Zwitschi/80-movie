import json
import re

from flask import current_app, render_template


def render_schema_template(template_name, **context):
    rendered = render_template(f'schema/{template_name}', **context)
    return json.loads(rendered)


def slugify_name(name):
    normalized = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return normalized or 'person'


def generate_unique_person_id(base_url, person_name, slug_counts):
    slug = slugify_name(person_name)
    current_count = slug_counts.get(slug, 0) + 1
    slug_counts[slug] = current_count

    if current_count == 1:
        return f'{base_url}/#person-{slug}'

    return f'{base_url}/#person-{slug}-{current_count}'


def build_person_nodes_and_refs(movie, base_url):
    person_nodes = []
    person_refs_by_role = {}
    slug_counts = {}

    for role_name in ('directors', 'producers', 'actors'):
        refs = []
        for person in movie['contributors'].get(role_name, []):
            person_id = generate_unique_person_id(
                base_url,
                person['name'],
                slug_counts,
            )
            refs.append({'@id': person_id})
            person_nodes.append(
                render_schema_template(
                    'person.json',
                    person_id=person_id,
                    person=person,
                )
            )
        person_refs_by_role[role_name] = refs

    contributor_refs = []
    for person in movie.get('credits_people', []):
        person_id = generate_unique_person_id(
            base_url,
            person['name'],
            slug_counts,
        )
        contributor_refs.append({'@id': person_id})
        person_nodes.append(
            render_schema_template(
                'person.json',
                person_id=person_id,
                person={
                    'name': person['name'],
                    'job_title': ', '.join(person.get('roles', [])),
                    'url': person.get('primary_url') or person['same_as'][0],
                    'same_as': person.get('same_as', []),
                },
            )
        )

    return person_nodes, person_refs_by_role, contributor_refs


def build_organization_node(movie, organization_id):
    return render_schema_template(
        'organization.json',
        organization_id=organization_id,
        organization=movie['production_company'],
    )


def build_trailer_node(movie, trailer_id, movie_id, organization_id, person_refs_by_role):
    return render_schema_template(
        'video_object.json',
        trailer_id=trailer_id,
        trailer=movie['trailer'],
        movie_id=movie_id,
        organization_id=organization_id,
        director_refs=person_refs_by_role['directors'],
        actor_refs=person_refs_by_role['actors'],
    )


def build_review_nodes(movie, base_url, movie_id):
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
    return review_nodes


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


def build_aggregate_rating_node(movie, base_url, movie_id):
    return render_schema_template(
        'aggregate_rating.json',
        rating_id=f'{base_url}/#aggregate-rating',
        aggregate_rating=movie['aggregate_rating'],
        movie_id=movie_id,
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


def build_movie_schema_graph(movie):
    base_url = current_app.config['SITE_URL'].rstrip('/')
    movie_id = f'{base_url}/#movie'
    organization_id = f'{base_url}/#organization'
    trailer_id = f'{base_url}/#trailer'

    person_nodes, person_refs_by_role, contributor_refs = build_person_nodes_and_refs(
        movie, base_url)
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
    movie_offer_nodes, movie_offer_refs = build_movie_offer_nodes_and_refs(
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


def build_movie_schema_json(movie):
    return json.dumps(build_movie_schema_graph(movie), indent=2, sort_keys=False)


def build_org_social_schema_json(movie):
    site_url = current_app.config['SITE_URL'].rstrip('/')
    organization = movie['production_company']
    social_profiles = [link['url'] for link in movie.get('social_links', [])]

    organization_schema = {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        '@id': f'{site_url}/#organization-profiles',
        'name': organization['name'],
        'url': organization['url'],
        'logo': movie['poster_image'],
        'sameAs': list(dict.fromkeys(organization.get('same_as', []) + social_profiles)),
        'email': movie.get('contact_email'),
    }

    return json.dumps(organization_schema, indent=2, sort_keys=False)
