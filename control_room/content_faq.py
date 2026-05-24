from flask import redirect, render_template, url_for
from shared.utils import (
    load_json,
    save_json,
    process_list_action,
)
from .content_common import _ctx


def _handle_faq_request(request):
    save_error = None
    faq_payload = load_json('faq.json')
    faq_items = faq_payload.get('faq', [])
    if not isinstance(faq_items, list):
        faq_items = []

    if request.method == 'POST':
        action = request.form.get('action', '').strip().lower()

        candidate = None
        if action == 'add':
            question = request.form.get('question', '').strip()
            answer = request.form.get('answer', '').strip()
            if not question:
                save_error = 'Question is required.'
            elif not answer:
                save_error = 'Answer is required.'
            else:
                candidate = {'question': question, 'answer': answer}

        if not save_error:
            updated = process_list_action(
                faq_items,
                action,
                request.form.get('index', '').strip(),
                candidate,
            )
            faq_payload['faq'] = updated
            success, save_error = save_json('faq.json', faq_payload)
            if success:
                return redirect(url_for('content.edit_faq', saved='1'))

    save_success = (save_error is None and request.method == 'POST') or (
        request.args.get('saved') == '1'
    )
    return render_template(
        'faq.html',
        save_error=save_error,
        save_success=save_success,
        faq_items=faq_items,
        **_ctx(),
    )
