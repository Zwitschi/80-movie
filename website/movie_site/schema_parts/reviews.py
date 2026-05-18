from . import render_schema_template
from ..db import get_dict_cursor


def build_review_nodes(movie_id, base_url):
    review_nodes = []
    cursor = get_dict_cursor()

    cursor.execute("SELECT * FROM review WHERE movie_id = %s", (movie_id,))
    reviews = cursor.fetchall()

    for index, review in enumerate(reviews, start=1):
        review_nodes.append(
            render_schema_template(
                'review.json',
                review_id=f'{base_url}/#review-{index}',
                review=review,
                movie_id=movie_id,
            )
        )
    cursor.close()
    return review_nodes


def build_aggregate_rating_node(movie_id, base_url):
    cursor = get_dict_cursor()

    cursor.execute(
        "SELECT * FROM aggregate_rating WHERE movie_id = %s", (movie_id,))
    aggregate_rating = cursor.fetchone()

    cursor.close()

    if not aggregate_rating:
        return None

    return render_schema_template(
        'aggregate_rating.json',
        rating_id=f'{base_url}/#aggregate-rating',
        aggregate_rating=aggregate_rating,
        movie_id=movie_id,
    )
