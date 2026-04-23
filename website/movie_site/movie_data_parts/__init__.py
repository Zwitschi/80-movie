from .core import build_movie_core_data
from .contributors import build_contributor_data
from .faq import build_faq_data
from .gallery import build_gallery_items_data
from .media import build_media_data
from .offer import build_offer_data
from .organization import build_production_company_data
from .people import build_credits_people_data
from .release import build_movie_release_status_data
from .review import build_review_data
from .screening import build_screening_data
from .social import build_social_links_data
from .support import build_support_links_data, build_supporter_page_data


def get_movie_data():
    movie = {}
    for builder in (
        build_movie_core_data,
        build_movie_release_status_data,
        build_media_data,
        build_production_company_data,
        build_contributor_data,
        build_credits_people_data,
        build_social_links_data,
        build_support_links_data,
        build_supporter_page_data,
        build_gallery_items_data,
        build_review_data,
        build_screening_data,
        build_offer_data,
        build_faq_data,
    ):
        movie.update(builder())

    return movie


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
