from flask import redirect, render_template, url_for
from .admin_utils import REQUIRED_CONTENT_PAGES
from shared.content_store import ContentReadError, ContentWriteError, get_content_reader, get_content_writer
from shared.utils import _build_content_previews, _content_page_form_fields, _validate_content_pages
from .content_common import _ctx


def _render_content_form(*, page_context, save_error, save_success, form_pages, previews):
    return render_template(
        'content.html',
        save_error=save_error,
        save_success=save_success,
        form_pages=form_pages,
        previews=previews,
        **page_context,
    )


def _handle_content_post(request, content_payload, pages_payload, page_context, writer):
    updated_pages = dict(pages_payload)
    for key in REQUIRED_CONTENT_PAGES:
        raw = request.form.get(f'{key}_keywords', '')
        keywords = [item.strip() for item in raw.split(',') if item.strip()]
        updated_pages[key] = {
            'title': request.form.get(f'{key}_title', '').strip(),
            'description': request.form.get(f'{key}_description', '').strip(),
            'keywords': keywords,
            'path': request.form.get(f'{key}_path', '').strip(),
        }

    validation_error = _validate_content_pages(
        updated_pages,
        REQUIRED_CONTENT_PAGES,
    )
    if validation_error:
        form_pages = {
            key: _content_page_form_fields(
                updated_pages.get(key, {}))
            for key in REQUIRED_CONTENT_PAGES
        }
        previews = _build_content_previews(
            updated_pages,
            page_context['movie_title'],
        )
        return _render_content_form(
            page_context=page_context,
            save_error=validation_error,
            save_success=False,
            form_pages=form_pages,
            previews=previews,
        )

    content_payload['pages'] = updated_pages
    try:
        writer.write('content', content_payload)
    except ContentWriteError as exc:
        form_pages = {
            key: _content_page_form_fields(
                updated_pages.get(key, {}))
            for key in REQUIRED_CONTENT_PAGES
        }
        previews = _build_content_previews(
            updated_pages,
            page_context['movie_title'],
        )
        return _render_content_form(
            page_context=page_context,
            save_error=str(exc),
            save_success=False,
            form_pages=form_pages,
            previews=previews,
        )

    return redirect(url_for('content.edit_content', saved='1'))


def _handle_content_request(request):
    reader = get_content_reader()
    writer = get_content_writer()
    page_context = _ctx()

    try:
        content_payload = reader.read('content')
    except ContentReadError as exc:
        return _render_content_form(
            page_context=page_context,
            save_error=str(exc),
            save_success=False,
            form_pages={},
            previews=[],
        )

    pages_payload = content_payload.get('pages', {})
    if not isinstance(pages_payload, dict):
        pages_payload = {}

    if request.method == 'POST':
        return _handle_content_post(request, content_payload, pages_payload, page_context, writer)

    form_pages = {
        key: _content_page_form_fields(
            pages_payload.get(key, {}))
        for key in REQUIRED_CONTENT_PAGES
    }
    previews = _build_content_previews(
        pages_payload,
        page_context['movie_title'],
    )
    save_success = request.args.get('saved') == '1'

    return _render_content_form(
        page_context=page_context,
        save_error=None,
        save_success=save_success,
        form_pages=form_pages,
        previews=previews,
    )
