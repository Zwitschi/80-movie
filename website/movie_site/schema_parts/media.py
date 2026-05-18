from . import render_schema_template
from ..db import get_dict_cursor


def build_trailer_node(trailer_id, movie_id, organization_id):
    cursor = get_dict_cursor()

    cursor.execute("SELECT * FROM trailer WHERE movie_id = %s", (movie_id,))
    trailer = cursor.fetchone()

    if not trailer:
        cursor.close()
        return None

    # This is a simplification. A real implementation would query the movie_credit table
    # to get the correct director and actor references.
    director_refs = []
    actor_refs = []

    cursor.close()

    return render_schema_template(
        'video_object.json',
        trailer_id=trailer_id,
        trailer=trailer,
        movie_id=movie_id,
        organization_id=organization_id,
        director_refs=director_refs,
        actor_refs=actor_refs,
    )
