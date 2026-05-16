from .content_store import get_content_reader

PRODUCTION_COMPANY_NAME = 'Open Mic Odyssey Productions'


def get_movie_data():
    reader = get_content_reader()
    all_data = reader.read_all()

    organizations = all_data['organizations.json']['organizations']

    return {
        **all_data['movies.json']['movie'],
        **all_data['media_assets.json']['media'],
        **all_data['reviews.json'],
        **all_data['offers.json'],
        'people': all_data['people.json']['people'],
        'contributors': all_data['people.json']['contributors'],
        'credits_people': all_data['people.json']['credits_people'],
        'organizations': organizations,
        'production_company': organizations[PRODUCTION_COMPANY_NAME],
        'screenings': all_data['events.json']['events'],
        'faq_items': all_data['faq.json']['faq'],
        'gallery_items': all_data['gallery.json']['gallery'],
        'social_links': all_data['social.json']['social'],
        'connect_links': all_data['connect.json']['connect']['links'],
        'connect_page': all_data['connect.json']['connect']['page'],
        'page_metadata': all_data['content.json']['pages'],
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
