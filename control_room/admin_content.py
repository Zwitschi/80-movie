from flask import redirect, render_template, url_for
from .admin_utils import (
    REQUIRED_CONTENT_PAGES,
    _event_from_form,
    _offer_from_form,
    _review_from_form,
    _validate_aggregate,
)
from shared.content_store import ContentReadError, ContentWriteError, get_content_reader, get_content_writer
from shared.utils import (
    load_json,
    save_json,
    process_list_action,
    _coerce_release_status,
    _movie_form_fields,
    _gallery_form_fields,
    _content_page_form_fields,
    _validate_content_pages,
    _build_content_previews,
    EVENT_STATUSES,
    EVENT_ATTENDANCE_MODES,
    OFFER_AVAILABILITIES,
)
from .content_common import _ctx
from .content_connect import (
    _handle_connect_patreon_request,
    _handle_connect_request,
    _handle_connect_social_request,
    _handle_connect_supporters_request,
)
from .content_events import _handle_events_request
from .content_faq import _handle_faq_request
from .content_film import _handle_film_request, _handle_film_request_post
from .content_media import _handle_media_request, _handle_media_request_post
from .content_media_assets import _handle_media_assets_request
from .content_pages import _handle_content_request, _handle_content_post
from .content_people import _handle_people_request


def _handle_reviews_request(request):
    reviews_payload = load_json('reviews.json')
    reviews = reviews_payload.get('reviews', [])
    if not isinstance(reviews, list):
        reviews = []
    aggregate = reviews_payload.get('aggregate_rating', {})
    if not isinstance(aggregate, dict):
        aggregate = {}

    save_error = None

    if request.method == 'POST':
        action = request.form.get('action', '').strip().lower()

        if action == 'add_review':
            entry, err = _review_from_form(request.form, prefix='review_')
            if err:
                save_error = err
            else:
                reviews = process_list_action(reviews, 'add', '', entry)
                reviews_payload['reviews'] = reviews
                success, err = save_json('reviews.json', reviews_payload)
                if success:
                    return redirect(url_for('content.edit_reviews', saved='1'))
                save_error = err

        elif action == 'remove_review':
            reviews = process_list_action(
                reviews, 'remove', request.form.get('review_index', ''))
            reviews_payload['reviews'] = reviews
            success, err = save_json('reviews.json', reviews_payload)
            if success:
                return redirect(url_for('content.edit_reviews', saved='1'))
            save_error = err

        elif action == 'save_aggregate':
            def _float_or_none(v):
                v = v.strip() if isinstance(v, str) else v
                return float(v) if v else None

            def _int_or_none(v):
                v = v.strip() if isinstance(v, str) else v
                return int(v) if v else None

            candidate = {
                'rating_value': _float_or_none(
                    request.form.get('agg_rating_value', '')),
                'best_rating': _float_or_none(
                    request.form.get('agg_best_rating', '')),
                'worst_rating': _float_or_none(
                    request.form.get('agg_worst_rating', '')),
                'rating_count': _int_or_none(
                    request.form.get('agg_rating_count', '')),
                'review_count': _int_or_none(
                    request.form.get('agg_review_count', '')),
            }
            err = _validate_aggregate(candidate)
            if err:
                save_error = err
            else:
                reviews_payload['aggregate_rating'] = candidate
                success, err = save_json('reviews.json', reviews_payload)
                if success:
                    return redirect(url_for('content.edit_reviews', saved='1'))
                save_error = err

    save_success = (save_error is None and request.method == 'POST') or (
        request.args.get('saved') == '1')
    return render_template(
        'admin/reviews.html',
        save_error=save_error,
        save_success=save_success,
        reviews=reviews,
        aggregate=aggregate,
        **_ctx(),
    )
