from flask import redirect, render_template, url_for
from .content_common import _ctx
from shared.utils import (
    _movie_form_fields,
    load_json,
    _coerce_release_status,
)
from shared.content_store import ContentWriteError, get_content_reader, get_content_writer


def _handle_film_request_post(request):
    writer = get_content_writer()
    reader = get_content_reader()
    payload = reader.read('movies.json')
    movie = payload.get('movie', {})
    update = dict(movie)
    update['title'] = request.form.get('title', '').strip()
    update['tagline'] = request.form.get('tagline', '').strip()
    update['description'] = request.form.get('description', '').strip()
    update['genre'] = request.form.get('genre', '').strip()
    update['runtime'] = request.form.get('runtime', '').strip()
    update['duration_iso'] = request.form.get('duration_iso', '').strip()
    update['release_date'] = request.form.get('release_date', '').strip()

    release_status = _coerce_release_status(update)
    release_status['label'] = request.form.get(
        'release_status_label', '').strip()
    release_status['headline'] = request.form.get(
        'release_status_headline', '').strip()
    release_status['summary'] = request.form.get(
        'release_status_summary', '').strip()
    release_status['detail'] = request.form.get(
        'release_status_detail', '').strip()
    update['release_status'] = release_status

    payload['movie'] = update
    try:
        writer.write('movies.json', payload)
        return redirect(url_for('content.edit_film', saved='1'))
    except ContentWriteError as exc:
        return render_template(
            'edit_film.html',
            save_error=str(exc),
            form_data=_movie_form_fields(update),
            raw_movie_data=update,
            **_ctx(),
        )


def _handle_film_request(request):
    save_error = None
    movies_payload = load_json('movies.json')
    movie_payload = movies_payload.get('movie', {})

    if request.method == 'POST':
        return _handle_film_request_post(request)

    save_success = request.args.get('saved') == '1'
    return render_template(
        'edit_film.html',
        save_error=save_error,
        save_success=save_success,
        form_data=_movie_form_fields(movie_payload),
        raw_movie_data=movie_payload,
        **_ctx(),
    )
