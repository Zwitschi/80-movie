from . import generate_unique_person_id, render_schema_template


def build_person_nodes_and_refs(movie, base_url):
    person_nodes = []
    person_refs_by_role = {}
    slug_counts = {}
    person_records = {}
    person_ids_by_name = {}

    def merge_person(name, job_title, url, same_as):
        person_id = person_ids_by_name.get(name)
        if person_id is None:
            person_id = generate_unique_person_id(base_url, name, slug_counts)
            person_ids_by_name[name] = person_id

        record = person_records.setdefault(
            name,
            {
                'name': name,
                'job_titles': [],
                'url': url,
                'same_as': [],
            },
        )

        if job_title and job_title not in record['job_titles']:
            record['job_titles'].append(job_title)
        if not record['url'] and url:
            record['url'] = url
        for profile_url in same_as or []:
            if profile_url not in record['same_as']:
                record['same_as'].append(profile_url)

        return person_id

    for role_name in ('directors', 'producers', 'actors'):
        refs = []
        for person in movie['contributors'].get(role_name, []):
            person_id = merge_person(
                person['name'],
                person.get('job_title'),
                person.get('url'),
                person.get('same_as', []),
            )
            refs.append({'@id': person_id})
        person_refs_by_role[role_name] = refs

    contributor_refs = []
    for person in movie.get('credits_people', []):
        person_id = merge_person(
            person['name'],
            ', '.join(person.get('roles', [])),
            person.get('primary_url') or person.get('url'),
            person.get('same_as', []),
        )
        contributor_refs.append({'@id': person_id})

    for name, record in person_records.items():
        person_nodes.append(
            render_schema_template(
                'person.json',
                person_id=person_ids_by_name[name],
                person={
                    'name': record['name'],
                    'job_title': ', '.join(record['job_titles']),
                    'url': record['url'],
                    'same_as': record['same_as'],
                },
            )
        )

    return person_nodes, person_refs_by_role, contributor_refs
