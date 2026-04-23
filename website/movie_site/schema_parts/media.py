from . import render_schema_template


def build_trailer_node(movie, trailer_id, movie_id, organization_id, person_refs_by_role):
    return render_schema_template(
        'video_object.json',
        trailer_id=trailer_id,
        trailer=movie['trailer'],
        movie_id=movie_id,
        organization_id=organization_id,
        director_refs=person_refs_by_role['directors'],
        actor_refs=person_refs_by_role['actors'],
    )
