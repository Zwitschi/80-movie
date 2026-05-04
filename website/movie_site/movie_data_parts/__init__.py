import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[2] / 'data'
PRODUCTION_COMPANY_NAME = 'Open Mic Odyssey Productions'


def load_json_file(filename):
    with (DATA_DIR / filename).open('r', encoding='utf-8') as file:
        return json.load(file)


def get_movie_data():
    movies_data = load_json_file('movies.json')
    people_data = load_json_file('people.json')
    organizations_data = load_json_file('organizations.json')
    media_data = load_json_file('media_assets.json')
    events_data = load_json_file('events.json')
    reviews_data = load_json_file('reviews.json')
    offers_data = load_json_file('offers.json')
    faq_data = load_json_file('faq.json')
    gallery_data = load_json_file('gallery.json')
    social_data = load_json_file('social.json')
    connect_data = load_json_file('connect.json')
    content_data = load_json_file('content.json')

    organizations = organizations_data['organizations']

    return {
        **movies_data['movie'],
        **media_data['media'],
        **reviews_data,
        **offers_data,
        'people': people_data['people'],
        'contributors': people_data['contributors'],
        'credits_people': people_data['credits_people'],
        'organizations': organizations,
        'production_company': organizations[PRODUCTION_COMPANY_NAME],
        'screenings': events_data['events'],
        'faq_items': faq_data['faq'],
        'gallery_items': gallery_data['gallery'],
        'social_links': social_data['social'],
        'connect_links': connect_data['connect']['links'],
        'connect_page': connect_data['connect']['page'],
        'page_metadata': content_data['pages'],
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
