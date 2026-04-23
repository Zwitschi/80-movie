from . import render_schema_template


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


def build_aggregate_rating_node(movie, base_url, movie_id):
    return render_schema_template(
        'aggregate_rating.json',
        rating_id=f'{base_url}/#aggregate-rating',
        aggregate_rating=movie['aggregate_rating'],
        movie_id=movie_id,
    )
