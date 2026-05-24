from flask import redirect, render_template, url_for
from shared.content_store import ContentReadError, ContentWriteError, get_content_reader, get_content_writer
from .content_common import _ctx


def _handle_media_assets_request(request):
    reader = get_content_reader()
    writer = get_content_writer()

    try:
        assets_payload = reader.read('media_assets.json')
    except ContentReadError as exc:
        return render_template(
            'media_assets.html',
            save_error=str(exc),
            save_success=False,
            media={},
            trailer={},
            **_ctx(),
        )

    media = assets_payload.get('media', {})
    if not isinstance(media, dict):
        media = {}
    trailer = media.get('trailer', {})
    if not isinstance(trailer, dict):
        trailer = {}

    save_error = None

    if request.method == 'POST':
        action = request.form.get('action', '').strip().lower()

        if action == 'save_media':
            media['date_published'] = request.form.get(
                'date_published', '').strip() or None
            media['in_language'] = request.form.get('in_language', '').strip()
            media['content_rating'] = request.form.get(
                'content_rating', '').strip()
            media['contact_email'] = request.form.get(
                'contact_email', '').strip()
            poster = request.form.get('poster_image', '').strip()
            media['poster_image'] = poster or None

            assets_payload['media'] = media
            try:
                writer.write('media_assets.json', assets_payload)
                return redirect(url_for('content.edit_media_assets', saved='1'))
            except ContentWriteError as exc:
                save_error = str(exc)

        elif action == 'save_trailer':
            trailer['name'] = request.form.get('trailer_name', '').strip()
            trailer['description'] = request.form.get(
                'trailer_description', '').strip()
            trailer['url'] = request.form.get('trailer_url', '').strip()
            embed_url = request.form.get('trailer_embed_url', '').strip()
            trailer['embed_url'] = embed_url or None
            trailer['thumbnail_url'] = request.form.get(
                'trailer_thumbnail_url', '').strip() or None
            trailer['upload_date'] = request.form.get(
                'trailer_upload_date', '').strip() or None
            trailer['duration_iso'] = request.form.get(
                'trailer_duration_iso', '').strip()
            trailer['encoding_format'] = request.form.get(
                'trailer_encoding_format', '').strip()
            is_family = request.form.get('trailer_is_family_friendly', '')
            trailer['is_family_friendly'] = is_family.lower() in (
                '1', 'true', 'yes', 'on')

            media['trailer'] = trailer
            assets_payload['media'] = media
            try:
                writer.write('media_assets.json', assets_payload)
                return redirect(url_for('content.edit_media_assets', saved='1'))
            except ContentWriteError as exc:
                save_error = str(exc)

    save_success = (save_error is None and request.method == 'POST') or (
        request.args.get('saved') == '1'
    )
    return render_template(
        'media_assets.html',
        save_error=save_error,
        save_success=save_success,
        media=media,
        trailer=trailer,
        **_ctx(),
    )
