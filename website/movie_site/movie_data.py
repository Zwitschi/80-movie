from .content_store import get_content_reader

PRODUCTION_COMPANY_NAME = 'Open Mic Odyssey Productions'


def get_movie_data():
    reader = get_content_reader()
    all_data = reader.read_all()

    organizations = all_data.get('organizations.json', {}).get('organizations', {})
    connect_payload = all_data.get('connect.json', {}).get('connect', {})
    connect_page = connect_payload.get('page', {})
    if not isinstance(connect_page, dict):
        connect_page = {}
    connect_page.setdefault('primary_link', {'label': '', 'url': ''})
    connect_page.setdefault('secondary_link', {'label': '', 'url': ''})
    connect_page.setdefault('benefits', [])
    connect_page.setdefault('tiers', [])
    production_company = organizations.get(PRODUCTION_COMPANY_NAME, {})

    return {
        **all_data.get('movies.json', {}).get('movie', {}),
        **all_data.get('media_assets.json', {}).get('media', {}),
        **all_data.get('reviews.json', {}),
        **all_data.get('offers.json', {}),
        'people': all_data.get('people.json', {}).get('people', {}),
        'contributors': all_data.get('people.json', {}).get('contributors', {}),
        'credits_people': all_data.get('people.json', {}).get('credits_people', []),
        'organizations': organizations,
        'production_company': production_company,
        'screenings': all_data.get('events.json', {}).get('events', []),
        'faq_items': all_data.get('faq.json', {}).get('faq', []),
        'gallery_items': all_data.get('gallery.json', {}).get('gallery', []),
        'social_links': all_data.get('social.json', {}).get('social', []),
        'connect_links': connect_payload.get('links', {}),
        'connect_page': connect_page,
        'page_metadata': all_data.get('content.json', {}).get('pages', {}),
    }


def get_movie_page_context(current_year):
    movie = get_movie_data()
    return {
        'movie': movie,
        'movie_title': movie['title'],
        'movie_tagline': movie['tagline'],
        'movie_description': movie['description'],
        'movie_genre': movie['genre'],
        'movie_runtime': movie['runtime'],
        'release_date': movie['release_date'],
        'release_status': movie['release_status'],
        'current_year': current_year,
    }
