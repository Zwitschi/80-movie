from . import generate_unique_person_id, render_schema_template


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
