import json


def build_org_social_schema_json(movie, site_url):
    organization = movie['production_company']
    social_profiles = [link['url'] for link in movie.get('social_links', [])]

    organization_schema = {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        '@id': f'{site_url}/#organization',
        'name': organization['name'],
        'url': organization['url'],
        'logo': movie['poster_image'],
        'sameAs': list(dict.fromkeys(organization.get('same_as', []) + social_profiles)),
        'email': movie.get('contact_email'),
    }

    return json.dumps(organization_schema, indent=2, sort_keys=False)
