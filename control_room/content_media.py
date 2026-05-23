from flask import redirect, render_template, url_for
from shared.utils import _gallery_form_fields, process_list_action, save_json, load_json
from .content_common import _ctx


def _render_media_error(save_error, gallery_items, categories=None):
    if categories is None:
        categories = []
    return render_template(
        'admin/manage_media.html',
        save_error=save_error,
        save_success=False,
        gallery_items=gallery_items,
        categories=categories,
        form_data=_gallery_form_fields(),
        **_ctx(),
    )


def _handle_media_request_post(request, gallery_payload, gallery_items):
    action = request.form.get('action', '').strip().lower()
    categories = gallery_payload.get('categories', [])
    if not isinstance(categories, list):
        categories = []

    if action == 'add_category':
        category_name = request.form.get('category_name', '').strip()
        if category_name:
            categories = gallery_payload.get('categories', [])
            if not isinstance(categories, list):
                categories = []
            if category_name not in categories:
                categories.append(category_name)
                gallery_payload['categories'] = categories
                success, save_error = save_json(
                    'gallery.json', gallery_payload)
                if success:
                    return redirect(url_for('content.manage_media', saved='1'))
                return _render_media_error(save_error, gallery_items, categories)
        return redirect(url_for('content.manage_media'))

    if action == 'remove_category':
        category_name = request.form.get('category_name', '').strip()
        categories = gallery_payload.get('categories', [])
        if not isinstance(categories, list):
            categories = []
        if category_name in categories:
            categories.remove(category_name)
            gallery_payload['categories'] = categories
            for item in gallery_items:
                if item.get('category') == category_name:
                    item['category'] = ''
            gallery_payload['gallery'] = gallery_items
            success, save_error = save_json('gallery.json', gallery_payload)
            if success:
                return redirect(url_for('content.manage_media', saved='1'))
            return _render_media_error(save_error, gallery_items, categories)
        return redirect(url_for('content.manage_media'))

    if action == 'rename_category':
        old_name = request.form.get('old_category_name', '').strip()
        new_name = request.form.get('new_category_name', '').strip()
        categories = gallery_payload.get('categories', [])
        if not isinstance(categories, list):
            categories = []
        if old_name in categories and new_name and new_name not in categories:
            categories = [new_name if category ==
                          old_name else category for category in categories]
            gallery_payload['categories'] = categories
            for item in gallery_items:
                if item.get('category') == old_name:
                    item['category'] = new_name
            gallery_payload['gallery'] = gallery_items
            success, save_error = save_json('gallery.json', gallery_payload)
            if success:
                return redirect(url_for('content.manage_media', saved='1'))
            return _render_media_error(save_error, gallery_items, categories)
        return redirect(url_for('content.manage_media'))

    if action == 'reorder':
        order_str = request.form.get('order', '').strip()
        if order_str:
            try:
                order = [int(value)
                         for value in order_str.split(',') if value.strip()]
                if len(order) == len(gallery_items):
                    gallery_items = [gallery_items[index] for index in order]
                    gallery_payload['gallery'] = gallery_items
                    success, _save_error = save_json(
                        'gallery.json', gallery_payload)
                    if success:
                        return redirect(url_for('content.manage_media', saved='1'))
            except (ValueError, IndexError):
                pass
        return redirect(url_for('content.manage_media'))

    if action == 'update':
        idx_str = request.form.get('index', '').strip()
        try:
            idx = int(idx_str)
            if 0 <= idx < len(gallery_items):
                gallery_items[idx]['title'] = request.form.get(
                    'title', '').strip()
                gallery_items[idx]['category'] = request.form.get(
                    'category', '').strip()
                gallery_items[idx]['image_url'] = request.form.get(
                    'image_url', '').strip()
                gallery_items[idx]['alt'] = request.form.get('alt', '').strip()
                gallery_items[idx]['description'] = request.form.get(
                    'description', '').strip()
                gallery_payload['gallery'] = gallery_items
                success, save_error = save_json(
                    'gallery.json', gallery_payload)
                if success:
                    return redirect(url_for('content.manage_media', saved='1'))
                return _render_media_error(save_error, gallery_items, categories)
        except ValueError:
            pass
        return redirect(url_for('content.manage_media'))

    candidate = None
    if action == 'add' or not action:
        candidate = {
            'title': request.form.get('title', '').strip(),
            'category': request.form.get('category', '').strip(),
            'image_url': request.form.get('image_url', '').strip(),
            'alt': request.form.get('alt', '').strip(),
            'description': request.form.get('description', '').strip(),
        }
        if not (candidate['title'] and candidate['image_url']):
            candidate = None

    if not action and candidate:
        action = 'add'

    updated_items = process_list_action(
        gallery_items,
        action,
        request.form.get('index', '').strip(),
        candidate,
    )

    gallery_payload['gallery'] = updated_items

    success, save_error = save_json('gallery.json', gallery_payload)
    if success:
        return redirect(url_for('content.manage_media', saved='1'))
    return _render_media_error(save_error, gallery_items, categories)


def _handle_media_request(request):
    save_error = None
    gallery_payload = load_json('gallery.json')
    gallery_items = gallery_payload.get('gallery', [])
    if not isinstance(gallery_items, list):
        gallery_items = []
    categories = gallery_payload.get('categories', [])
    if not isinstance(categories, list):
        categories = []

    if request.method == 'POST':
        return _handle_media_request_post(request, gallery_payload, gallery_items)

    save_success = request.args.get('saved') == '1'
    return render_template(
        'admin/manage_media.html',
        save_error=save_error,
        save_success=save_success,
        gallery_items=gallery_items,
        categories=categories,
        form_data=_gallery_form_fields(),
        **_ctx(),
    )
