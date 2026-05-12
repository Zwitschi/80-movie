from flask import Blueprint, current_app, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash

from .admin_utils import (
    CONTRIBUTOR_SECTIONS,
    REQUIRED_CONTENT_PAGES,
    _benefit_from_form,
    _contributor_from_form,
    _credit_from_form,
    _event_from_form,
    _link_from_form,
    _offer_from_form,
    _org_from_form,
    _person_from_form,
    _review_from_form,
    _social_from_form,
    _tier_from_form,
    _validate_aggregate,
)
from .auth import AdminUser
from .content_store import ContentReadError, ContentWriteError, get_content_reader, get_content_writer
from .utils import (
    _ctx,
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


admin_blueprint = Blueprint('admin', __name__, url_prefix='/admin')


@admin_blueprint.before_request
def require_login():
    if current_app.config.get('TESTING'):
        return None

    if request.endpoint != 'admin.login' and not current_user.is_authenticated:
        return redirect(url_for('admin.login', next=request.url))


@admin_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        valid_username = current_app.config.get('ADMIN_USERNAME')
        valid_hash = current_app.config.get('ADMIN_PASSWORD_HASH')

        if (
            username == valid_username
            and isinstance(valid_hash, str)
            and check_password_hash(valid_hash, password)
        ):
            user = AdminUser(username)
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin.dashboard'))
        else:
            error = 'Invalid credentials'

    return render_template('admin/login.html', error=error)


@admin_blueprint.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.index'))


@admin_blueprint.get('/')
def dashboard():
    return render_template('admin/admin.html', **_ctx())


def update_movie(request):
    movies_payload = load_json('movies.json')
    movie_payload = movies_payload.get('movie', {})
    updated_movie = dict(movie_payload)
    updated_movie['title'] = request.form.get('title', '').strip()
    updated_movie['tagline'] = request.form.get('tagline', '').strip()
    updated_movie['description'] = request.form.get(
        'description', '').strip()
    updated_movie['genre'] = request.form.get('genre', '').strip()
    updated_movie['runtime'] = request.form.get('runtime', '').strip()
    updated_movie['duration_iso'] = request.form.get(
        'duration_iso', '').strip()
    updated_movie['release_date'] = request.form.get(
        'release_date', '').strip()

    release_status = _coerce_release_status(updated_movie)
    release_status['label'] = request.form.get(
        'release_status_label', '').strip()
    release_status['headline'] = request.form.get(
        'release_status_headline', '').strip()
    release_status['summary'] = request.form.get(
        'release_status_summary', '').strip()
    release_status['detail'] = request.form.get(
        'release_status_detail', '').strip()
    updated_movie['release_status'] = release_status

    movies_payload['movie'] = updated_movie
    success, save_error = save_json('movies.json', movies_payload)
    return success, save_error


@admin_blueprint.route('/film', methods=['GET', 'POST'])
def edit_film():
    save_error = None
    movies_payload = load_json('movies.json')
    movie_payload = movies_payload.get('movie', {})

    if request.method == 'POST':
        success, save_error = update_movie(request)
        if success:
            return redirect(url_for('admin.edit_film', saved='1'))

    save_success = request.args.get('saved') == '1'
    return render_template(
        'admin/edit_film.html',
        save_error=save_error,
        save_success=save_success,
        form_data=_movie_form_fields(movie_payload),
        raw_movie_data=movie_payload,
        **_ctx(),
    )


@admin_blueprint.route('/media', methods=['GET', 'POST'])
def manage_media():
    save_error = None
    gallery_payload = load_json('gallery.json')
    gallery_items = gallery_payload.get('gallery', [])
    if not isinstance(gallery_items, list):
        gallery_items = []

    if request.method == 'POST':
        action = request.form.get('action', '').strip().lower()

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

        # Remap empty action from form to 'add' for backwards compatibility
        if not action and candidate:
            action = 'add'

        updated_items = process_list_action(
            gallery_items,
            action,
            request.form.get('index', '').strip(),
            candidate
        )

        gallery_payload['gallery'] = updated_items

        success, save_error = save_json('gallery.json', gallery_payload)
        if success:
            return redirect(url_for('admin.manage_media', saved='1'))

    save_success = request.args.get('saved') == '1'
    return render_template(
        'admin/manage_media.html',
        save_error=save_error,
        save_success=save_success,
        gallery_items=gallery_items,
        form_data=_gallery_form_fields(),
        **_ctx(),
    )


@admin_blueprint.route('/content', methods=['GET', 'POST'])
def edit_content():
    reader = get_content_reader()
    writer = get_content_writer()
    page_context = _ctx()

    try:
        content_payload = reader.read('content.json')
    except ContentReadError as exc:
        return render_template(
            'admin/content.html',
            save_error=str(exc),
            save_success=False,
            form_pages={},
            previews=[],
            **page_context,
        )

    pages_payload = content_payload.get('pages', {})
    if not isinstance(pages_payload, dict):
        pages_payload = {}

    if request.method == 'POST':
        updated_pages = dict(pages_payload)
        for key in REQUIRED_CONTENT_PAGES:
            keywords_raw = request.form.get(f'{key}_keywords', '')
            keywords = [item.strip()
                        for item in keywords_raw.split(',') if item.strip()]
            updated_pages[key] = {
                'title': request.form.get(f'{key}_title', '').strip(),
                'description': request.form.get(f'{key}_description', '').strip(),
                'keywords': keywords,
                'path': request.form.get(f'{key}_path', '').strip(),
            }

        validation_error = _validate_content_pages(
            updated_pages, REQUIRED_CONTENT_PAGES)
        if validation_error:
            form_pages = {
                key: _content_page_form_fields(updated_pages.get(key, {}))
                for key in REQUIRED_CONTENT_PAGES
            }
            previews = _build_content_previews(
                updated_pages, page_context['movie_title'])
            return render_template(
                'admin/content.html',
                save_error=validation_error,
                save_success=False,
                form_pages=form_pages,
                previews=previews,
                **page_context,
            )

        content_payload['pages'] = updated_pages
        try:
            writer.write('content.json', content_payload)
        except ContentWriteError as exc:
            form_pages = {
                key: _content_page_form_fields(updated_pages.get(key, {}))
                for key in REQUIRED_CONTENT_PAGES
            }
            previews = _build_content_previews(
                updated_pages, page_context['movie_title'])
            return render_template(
                'admin/content.html',
                save_error=str(exc),
                save_success=False,
                form_pages=form_pages,
                previews=previews,
                **page_context,
            )

        return redirect(url_for('admin.edit_content', saved='1'))

    form_pages = {
        key: _content_page_form_fields(pages_payload.get(key, {}))
        for key in REQUIRED_CONTENT_PAGES
    }
    previews = _build_content_previews(
        pages_payload, page_context['movie_title'])
    save_success = request.args.get('saved') == '1'

    return render_template(
        'admin/content.html',
        save_error=None,
        save_success=save_success,
        form_pages=form_pages,
        previews=previews,
        **page_context,
    )


@admin_blueprint.route('/events', methods=['GET', 'POST'])
def edit_events():
    events_payload = load_json('events.json')
    offers_payload = load_json('offers.json')
    events = events_payload.get('events', [])
    if not isinstance(events, list):
        events = []
    offers = offers_payload.get('offers', [])
    if not isinstance(offers, list):
        offers = []

    save_error = None
    save_success = False

    if request.method == 'POST':
        action = request.form.get('action', '').strip().lower()

        if action == 'remove_event':
            events = process_list_action(
                events, 'remove', request.form.get('event_index', ''))
            events_payload['events'] = events
            success, err = save_json('events.json', events_payload)
            if success:
                return redirect(url_for('admin.edit_events', saved='1'))
            save_error = err

        elif action == 'remove_offer':
            offers = process_list_action(
                offers, 'remove', request.form.get('offer_index', ''))
            offers_payload['offers'] = offers
            success, err = save_json('offers.json', offers_payload)
            if success:
                return redirect(url_for('admin.edit_events', saved='1'))
            save_error = err

        elif action == 'add_event':
            new_event, err = _event_from_form(request.form)
            if err:
                save_error = err
            else:
                events = process_list_action(events, 'add', '', new_event)
                events_payload['events'] = events
                success, err = save_json('events.json', events_payload)
                if success:
                    return redirect(url_for('admin.edit_events', saved='1'))
                save_error = err

        elif action == 'add_offer':
            new_offer, err = _offer_from_form(request.form)
            if err:
                save_error = err
            else:
                offers = process_list_action(offers, 'add', '', new_offer)
                offers_payload['offers'] = offers
                success, err = save_json('offers.json', offers_payload)
                if success:
                    return redirect(url_for('admin.edit_events', saved='1'))
                save_error = err

        if save_error is None:
            save_success = True

    save_success = save_success or (request.args.get('saved') == '1')
    return render_template(
        'admin/events.html',
        save_error=save_error,
        save_success=save_success,
        events=events,
        offers=offers,
        event_statuses=EVENT_STATUSES,
        event_attendance_modes=EVENT_ATTENDANCE_MODES,
        offer_availabilities=OFFER_AVAILABILITIES,
        **_ctx(),
    )


@admin_blueprint.route('/faq', methods=['GET', 'POST'])
def edit_faq():
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
                candidate
            )
            faq_payload['faq'] = updated
            success, save_error = save_json('faq.json', faq_payload)
            if success:
                return redirect(url_for('admin.edit_faq', saved='1'))

    save_success = (save_error is None and request.method == 'POST') or (
        request.args.get('saved') == '1')
    return render_template(
        'admin/faq.html',
        save_error=save_error,
        save_success=save_success,
        faq_items=faq_items,
        **_ctx(),
    )


@admin_blueprint.route('/people', methods=['GET', 'POST'])
def edit_people():
    people_payload = load_json('people.json')
    orgs_payload = load_json('organizations.json')

    people = people_payload.get('people', {})
    if not isinstance(people, dict):
        people = {}
    contributors = people_payload.get('contributors', {})
    if not isinstance(contributors, dict):
        contributors = {}
    credits_people = people_payload.get('credits_people', [])
    if not isinstance(credits_people, list):
        credits_people = []
    organizations = orgs_payload.get('organizations', {})
    if not isinstance(organizations, dict):
        organizations = {}

    save_error = None

    if request.method == 'POST':
        action = request.form.get('action', '').strip().lower()

        if action == 'add_person':
            entry, err = _person_from_form(request.form, prefix='person_')
            if err:
                save_error = err
            else:
                people = dict(people)
                people[entry['name']] = entry
                people_payload['people'] = people
                success, save_error = save_json('people.json', people_payload)
                if success:
                    return redirect(url_for('admin.edit_people', saved='1'))

        elif action == 'remove_person':
            key = request.form.get('person_key', '').strip()
            if key in people:
                people = dict(people)
                del people[key]
                people_payload['people'] = people
                success, save_error = save_json('people.json', people_payload)
                if success:
                    return redirect(url_for('admin.edit_people', saved='1'))

        elif action == 'add_contributor':
            section = request.form.get(
                'contributor_section', '').strip().lower()
            if section not in CONTRIBUTOR_SECTIONS:
                save_error = f'Invalid contributor section: {section!r}.'
            else:
                entry, err = _contributor_from_form(
                    request.form, prefix='contributor_')
                if err:
                    save_error = err
                else:
                    contributors = dict(contributors)
                    contributors[section] = process_list_action(
                        contributors.get(section, []), 'add', '', entry)
                    people_payload['contributors'] = contributors
                    success, save_error = save_json(
                        'people.json', people_payload)
                    if success:
                        return redirect(url_for('admin.edit_people', saved='1'))

        elif action == 'remove_contributor':
            section = request.form.get(
                'contributor_section', '').strip().lower()
            idx_str = request.form.get('contributor_index', '')
            contributors = dict(contributors)
            contributors[section] = process_list_action(
                contributors.get(section, []), 'remove', idx_str)
            people_payload['contributors'] = contributors
            success, save_error = save_json('people.json', people_payload)
            if success:
                return redirect(url_for('admin.edit_people', saved='1'))

        elif action == 'add_credit':
            entry, err = _credit_from_form(request.form, prefix='credit_')
            if err:
                save_error = err
            else:
                credits_people = process_list_action(
                    credits_people, 'add', '', entry)
                people_payload['credits_people'] = credits_people
                success, save_error = save_json('people.json', people_payload)
                if success:
                    return redirect(url_for('admin.edit_people', saved='1'))

        elif action == 'remove_credit':
            credits_people = process_list_action(
                credits_people, 'remove', request.form.get('credit_index', ''))
            people_payload['credits_people'] = credits_people
            success, save_error = save_json('people.json', people_payload)
            if success:
                return redirect(url_for('admin.edit_people', saved='1'))

        elif action == 'add_org':
            entry, err = _org_from_form(request.form, prefix='org_')
            if err:
                save_error = err
            else:
                organizations = dict(organizations)
                organizations[entry['name']] = entry
                orgs_payload['organizations'] = organizations
                success, save_error = save_json(
                    'organizations.json', orgs_payload)
                if success:
                    return redirect(url_for('admin.edit_people', saved='1'))

        elif action == 'remove_org':
            key = request.form.get('org_key', '').strip()
            if key in organizations:
                organizations = dict(organizations)
                del organizations[key]
                orgs_payload['organizations'] = organizations
                success, save_error = save_json(
                    'organizations.json', orgs_payload)
                if success:
                    return redirect(url_for('admin.edit_people', saved='1'))

    save_success = (save_error is None and request.method ==
                    'POST') or (request.args.get('saved') == '1')
    return render_template(
        'admin/people.html',
        save_error=save_error,
        save_success=save_success,
        people=people,
        contributors=contributors,
        credits_people=credits_people,
        organizations=organizations,
        contributor_sections=CONTRIBUTOR_SECTIONS,
        **_ctx(),
    )


@admin_blueprint.route('/connect', methods=['GET', 'POST'])
def edit_connect():
    reader = get_content_reader()
    writer = get_content_writer()

    try:
        social_payload = reader.read('social.json')
        connect_payload = reader.read('connect.json')
    except ContentReadError as exc:
        return render_template(
            'admin/connect.html',
            save_error=str(exc),
            save_success=False,
            social=[],
            campaigns=[],
            channels=[],
            page={},
            benefits=[],
            tiers=[],
            **_ctx(),
        )

    social = social_payload.get('social', [])
    if not isinstance(social, list):
        social = []

    connect = connect_payload.get('connect', {})
    links = connect.get('links', {})
    campaigns = links.get('campaigns', [])
    if not isinstance(campaigns, list):
        campaigns = []
    channels = links.get('channels', [])
    if not isinstance(channels, list):
        channels = []
    page = connect.get('page', {})
    if not isinstance(page, dict):
        page = {}
    benefits = page.get('benefits', [])
    if not isinstance(benefits, list):
        benefits = []
    tiers = page.get('tiers', [])
    if not isinstance(tiers, list):
        tiers = []

    save_error = None

    if request.method == 'POST':
        action = request.form.get('action', '').strip().lower()

        # ── Social links ──────────────────────────────────────────────
        if action == 'add_social':
            entry, err = _social_from_form(request.form, prefix='social_')
            if err:
                save_error = err
            else:
                social_payload['social'] = list(social) + [entry]
                try:
                    writer.write('social.json', social_payload)
                    return redirect(url_for('admin.edit_connect', saved='1'))
                except ContentWriteError as exc:
                    save_error = str(exc)

        elif action == 'remove_social':
            try:
                idx = int(request.form.get('social_index', ''))
                updated = list(social)
                if 0 <= idx < len(updated):
                    updated.pop(idx)
                    social_payload['social'] = updated
                    writer.write('social.json', social_payload)
                    return redirect(url_for('admin.edit_connect', saved='1'))
            except (ValueError, ContentWriteError) as exc:
                save_error = str(exc)

        # ── Campaign links ────────────────────────────────────────────
        elif action == 'add_campaign':
            entry, err = _link_from_form(request.form, prefix='campaign_')
            if err:
                save_error = err
            else:
                updated = list(campaigns) + [entry]
                connect.setdefault('links', {})['campaigns'] = updated
                connect_payload['connect'] = connect
                try:
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('admin.edit_connect', saved='1'))
                except ContentWriteError as exc:
                    save_error = str(exc)

        elif action == 'remove_campaign':
            try:
                idx = int(request.form.get('campaign_index', ''))
                updated = list(campaigns)
                if 0 <= idx < len(updated):
                    updated.pop(idx)
                    connect.setdefault('links', {})['campaigns'] = updated
                    connect_payload['connect'] = connect
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('admin.edit_connect', saved='1'))
            except (ValueError, ContentWriteError) as exc:
                save_error = str(exc)

        # ── Supporter links ───────────────────────────────────────────
        elif action == 'add_supporter':
            entry, err = _link_from_form(request.form, prefix='supporter_')
            if err:
                save_error = err
            else:
                updated = list(channels) + [entry]
                connect.setdefault('links', {})['channels'] = updated
                connect_payload['connect'] = connect
                try:
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('admin.edit_connect', saved='1'))
                except ContentWriteError as exc:
                    save_error = str(exc)

        elif action == 'remove_supporter':
            try:
                idx = int(request.form.get('supporter_index', ''))
                updated = list(channels)
                if 0 <= idx < len(updated):
                    updated.pop(idx)
                    connect.setdefault('links', {})['channels'] = updated
                    connect_payload['connect'] = connect
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('admin.edit_connect', saved='1'))
            except (ValueError, ContentWriteError) as exc:
                save_error = str(exc)

        # ── Page copy ─────────────────────────────────────────────────
        elif action == 'save_page':
            page['title'] = request.form.get('page_title', '').strip()
            page['intro'] = request.form.get('page_intro', '').strip()
            page['membership_pitch'] = request.form.get(
                'page_membership_pitch', '').strip()
            page.setdefault('primary_link', {})['label'] = request.form.get(
                'page_primary_label', '').strip()
            page['primary_link']['url'] = request.form.get(
                'page_primary_url', '').strip()
            page.setdefault('secondary_link', {})['label'] = request.form.get(
                'page_secondary_label', '').strip()
            page['secondary_link']['url'] = request.form.get(
                'page_secondary_url', '').strip()
            connect['page'] = page
            connect_payload['connect'] = connect
            try:
                writer.write('connect.json', connect_payload)
                return redirect(url_for('admin.edit_connect', saved='1'))
            except ContentWriteError as exc:
                save_error = str(exc)

        # ── Benefits ──────────────────────────────────────────────────
        elif action == 'add_benefit':
            entry, err = _benefit_from_form(request.form, prefix='benefit_')
            if err:
                save_error = err
            else:
                page['benefits'] = list(benefits) + [entry]
                connect['page'] = page
                connect_payload['connect'] = connect
                try:
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('admin.edit_connect', saved='1'))
                except ContentWriteError as exc:
                    save_error = str(exc)

        elif action == 'remove_benefit':
            try:
                idx = int(request.form.get('benefit_index', ''))
                updated = list(benefits)
                if 0 <= idx < len(updated):
                    updated.pop(idx)
                    page['benefits'] = updated
                    connect['page'] = page
                    connect_payload['connect'] = connect
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('admin.edit_connect', saved='1'))
            except (ValueError, ContentWriteError) as exc:
                save_error = str(exc)

        # ── Tiers ─────────────────────────────────────────────────────
        elif action == 'add_tier':
            entry, err = _tier_from_form(request.form, prefix='tier_')
            if err:
                save_error = err
            else:
                page['tiers'] = list(tiers) + [entry]
                connect['page'] = page
                connect_payload['connect'] = connect
                try:
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('admin.edit_connect', saved='1'))
                except ContentWriteError as exc:
                    save_error = str(exc)

        elif action == 'remove_tier':
            try:
                idx = int(request.form.get('tier_index', ''))
                updated = list(tiers)
                if 0 <= idx < len(updated):
                    updated.pop(idx)
                    page['tiers'] = updated
                    connect['page'] = page
                    connect_payload['connect'] = connect
                    writer.write('connect.json', connect_payload)
                    return redirect(url_for('admin.edit_connect', saved='1'))
            except (ValueError, ContentWriteError) as exc:
                save_error = str(exc)

    save_success = (save_error is None and request.method == 'POST') or (
        request.args.get('saved') == '1')
    return render_template(
        'admin/connect.html',
        save_error=save_error,
        save_success=save_success,
        social=social,
        campaigns=campaigns,
        channels=channels,
        page=page,
        benefits=benefits,
        tiers=tiers,
        **_ctx(),
    )


@admin_blueprint.route('/media-assets', methods=['GET', 'POST'])
def edit_media_assets():
    reader = get_content_reader()
    writer = get_content_writer()

    try:
        assets_payload = reader.read('media_assets.json')
    except ContentReadError as exc:
        return render_template(
            'admin/media_assets.html',
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
            media['in_language'] = request.form.get(
                'in_language', '').strip()
            media['content_rating'] = request.form.get(
                'content_rating', '').strip()
            media['contact_email'] = request.form.get(
                'contact_email', '').strip()
            poster = request.form.get('poster_image', '').strip()
            media['poster_image'] = poster or None

            assets_payload['media'] = media
            try:
                writer.write('media_assets.json', assets_payload)
                return redirect(url_for('admin.edit_media_assets', saved='1'))
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
                return redirect(url_for('admin.edit_media_assets', saved='1'))
            except ContentWriteError as exc:
                save_error = str(exc)

    save_success = (save_error is None and request.method == 'POST') or (
        request.args.get('saved') == '1')
    return render_template(
        'admin/media_assets.html',
        save_error=save_error,
        save_success=save_success,
        media=media,
        trailer=trailer,
        **_ctx(),
    )


@admin_blueprint.route('/reviews', methods=['GET', 'POST'])
def edit_reviews():
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
                    return redirect(url_for('admin.edit_reviews', saved='1'))
                save_error = err

        elif action == 'remove_review':
            reviews = process_list_action(
                reviews, 'remove', request.form.get('review_index', ''))
            reviews_payload['reviews'] = reviews
            success, err = save_json('reviews.json', reviews_payload)
            if success:
                return redirect(url_for('admin.edit_reviews', saved='1'))
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
                    return redirect(url_for('admin.edit_reviews', saved='1'))
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


@admin_blueprint.get('/submissions')
def view_submissions():
    return render_template('admin/view_submissions.html', **_ctx())
