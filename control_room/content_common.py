from flask import current_app

from shared.content_store import get_content_reader


def _ctx():
    """Build admin page context for control room templates."""
    reader = get_content_reader()
    movies = reader.read('movies')
    movie = movies.get('movie', {})
    return {
        'movie_title': movie.get('title', ''),
        'movie_tagline': movie.get('tagline', ''),
        'movie_description': movie.get('description', ''),
        'movie_genre': movie.get('genre', ''),
        'movie_runtime': movie.get('runtime', ''),
        'release_date': movie.get('release_date', ''),
        'release_status': movie.get('release_status', {}),
        'current_year': current_app.config.get('CURRENT_YEAR', ''),
    }