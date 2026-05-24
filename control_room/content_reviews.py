from flask import redirect, render_template, url_for
from .admin_utils import _review_from_form, _validate_aggregate
from shared.utils import process_list_action, save_json, load_json
from .content_common import _ctx


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
            entry, err = _review_from_form(
                request.form, prefix='review_')
            if err:
                save_error = err
            else:
                reviews = process_list_action(
                    reviews, 'add', '', entry)
                reviews_payload['reviews'] = reviews
                success, err = save_json(
                    'reviews.json', reviews_payload)
                if success:
                    return redirect(url_for('content.edit_reviews', saved='1'))
                save_error = err

        elif action == 'remove_review':
            reviews = process_list_action(
                reviews,
                'remove',
                request.form.get('review_index', ''),
            )
            reviews_payload['reviews'] = reviews
            success, err = save_json(
                'reviews.json', reviews_payload)
            if success:
                return redirect(url_for('content.edit_reviews', saved='1'))
            save_error = err

        elif action == 'save_aggregate':
            def _float_or_none(value):
                value = value.strip() if isinstance(value, str) else value
                return float(value) if value else None

            def _int_or_none(value):
                value = value.strip() if isinstance(value, str) else value
                return int(value) if value else None

            candidate = {
                'rating_value': _float_or_none(request.form.get('agg_rating_value', '')),
                'best_rating': _float_or_none(request.form.get('agg_best_rating', '')),
                'worst_rating': _float_or_none(request.form.get('agg_worst_rating', '')),
                'rating_count': _int_or_none(request.form.get('agg_rating_count', '')),
                'review_count': _int_or_none(request.form.get('agg_review_count', '')),
            }
            err = _validate_aggregate(candidate)
            if err:
                save_error = err
            else:
                reviews_payload['aggregate_rating'] = candidate
                success, err = save_json(
                    'reviews.json', reviews_payload)
                if success:
                    return redirect(url_for('content.edit_reviews', saved='1'))
                save_error = err

    save_success = (save_error is None and request.method == 'POST') or (
        request.args.get('saved') == '1'
    )
    return render_template(
        'reviews.html',
        save_error=save_error,
        save_success=save_success,
        reviews=reviews,
        aggregate=aggregate,
        **_ctx(),
    )
