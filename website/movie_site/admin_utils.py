from .utils import _validate_iso_date, _validate_iso_datetime, _validate_schema_org_url


REQUIRED_CONTENT_PAGES = ('index', 'film', 'media', 'connect', 'patreon')
CONTRIBUTOR_SECTIONS = ('directors', 'producers', 'actors')


def _split_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(',') if item.strip()]


def _event_from_form(form) -> tuple[dict, str | None]:
    name = form.get('event_name', '').strip()
    description = form.get('event_description', '').strip()
    start_date = form.get('event_start_date', '').strip()
    end_date = form.get('event_end_date', '').strip()
    event_status = form.get('event_status', '').strip()
    event_attendance_mode = form.get('event_attendance_mode', '').strip()
    location_name = form.get('event_location_name', '').strip()
    location_url = form.get('event_location_url', '').strip()
    street_address = form.get('event_street_address', '').strip()
    address_locality = form.get('event_address_locality', '').strip()
    address_region = form.get('event_address_region', '').strip()
    postal_code = form.get('event_postal_code', '').strip()
    address_country = form.get('event_address_country', '').strip()
    video_format = form.get('event_video_format', '').strip()
    subtitle_language = form.get('event_subtitle_language', '').strip()

    if not name:
        return {}, 'Event name is required.'
    if start_date and not _validate_iso_datetime(start_date):
        return {}, f'Invalid start_date format: {start_date!r}. Use YYYY-MM-DDTHH:MM:SS±HH:MM.'
    if end_date and not _validate_iso_datetime(end_date):
        return {}, f'Invalid end_date format: {end_date!r}. Use YYYY-MM-DDTHH:MM:SS±HH:MM.'
    if event_status and not _validate_schema_org_url(event_status):
        return {}, 'event_status must be a schema.org URL.'
    if event_attendance_mode and not _validate_schema_org_url(event_attendance_mode):
        return {}, 'event_attendance_mode must be a schema.org URL.'

    event = {
        'name': name,
        'description': description,
        'start_date': start_date,
        'end_date': end_date,
        'event_status': event_status,
        'event_attendance_mode': event_attendance_mode,
        'location': {
            'name': location_name,
            'url': location_url,
            'address': {
                'street_address': street_address,
                'address_locality': address_locality,
                'address_region': address_region,
                'postal_code': postal_code,
                'address_country': address_country,
            },
        },
        'video_format': video_format,
        'subtitle_language': subtitle_language,
        'offers': [],
    }
    return event, None


def _offer_from_form(form) -> tuple[dict, str | None]:
    name = form.get('offer_name', '').strip()
    url = form.get('offer_url', '').strip()
    category = form.get('offer_category', '').strip()
    availability = form.get('offer_availability', '').strip()
    price_raw = form.get('offer_price', '0').strip()
    price_currency = form.get('offer_price_currency', 'USD').strip()
    valid_from = form.get('offer_valid_from', '').strip()
    description = form.get('offer_description', '').strip()

    if not name:
        return {}, 'Offer name is required.'
    if availability and not _validate_schema_org_url(availability):
        return {}, 'availability must be a schema.org URL.'
    if valid_from and not _validate_iso_date(valid_from):
        return {}, f'Invalid valid_from format: {valid_from!r}. Use YYYY-MM-DD.'
    try:
        price = float(price_raw) if price_raw else 0
    except ValueError:
        return {}, f'Invalid price value: {price_raw!r}.'

    offer = {
        'name': name,
        'url': url,
        'category': category,
        'availability': availability,
        'price': price,
        'price_currency': price_currency,
        'valid_from': valid_from,
        'description': description,
    }
    return offer, None


def _person_from_form(form, prefix: str = '') -> tuple[dict, str | None]:
    name = form.get(f'{prefix}name', '').strip()
    url = form.get(f'{prefix}url', '').strip()
    same_as = _split_list(form.get(f'{prefix}same_as', ''))
    roles = _split_list(form.get(f'{prefix}roles', ''))
    job_title = form.get(f'{prefix}job_title', '').strip()
    credit_note = form.get(f'{prefix}credit_note', '').strip()
    if not name:
        return {}, 'Name is required.'
    return {
        'name': name,
        'url': url,
        'same_as': same_as,
        'roles': roles,
        'job_title': job_title,
        'credit_note': credit_note,
    }, None


def _contributor_from_form(form, prefix: str = '') -> tuple[dict, str | None]:
    name = form.get(f'{prefix}name', '').strip()
    job_title = form.get(f'{prefix}job_title', '').strip()
    url = form.get(f'{prefix}url', '').strip()
    same_as = _split_list(form.get(f'{prefix}same_as', ''))
    credit_note = form.get(f'{prefix}credit_note', '').strip()
    if not name:
        return {}, 'Name is required.'
    return {
        'name': name,
        'job_title': job_title,
        'url': url,
        'same_as': same_as,
        'credit_note': credit_note,
    }, None


def _credit_from_form(form, prefix: str = '') -> tuple[dict, str | None]:
    name = form.get(f'{prefix}name', '').strip()
    roles = _split_list(form.get(f'{prefix}roles', ''))
    primary_url = form.get(f'{prefix}primary_url', '').strip()
    same_as = _split_list(form.get(f'{prefix}same_as', ''))
    if not name:
        return {}, 'Name is required.'
    return {
        'name': name,
        'roles': roles,
        'primary_url': primary_url,
        'same_as': same_as,
    }, None


def _org_from_form(form, prefix: str = '') -> tuple[dict, str | None]:
    name = form.get(f'{prefix}name', '').strip()
    url = form.get(f'{prefix}url', '').strip()
    same_as = _split_list(form.get(f'{prefix}same_as', ''))
    people = _split_list(form.get(f'{prefix}people', ''))
    if not name:
        return {}, 'Organization name is required.'
    return {
        'name': name,
        'url': url,
        'same_as': same_as,
        'people': people,
    }, None


def _link_from_form(form, prefix: str = '') -> tuple[dict, str | None]:
    label = form.get(f'{prefix}label', '').strip()
    url = form.get(f'{prefix}url', '').strip()
    status = form.get(f'{prefix}status', '').strip()
    description = form.get(f'{prefix}description', '').strip()
    if not label:
        return {}, 'Label is required.'
    return {
        'label': label,
        'url': url,
        'status': status,
        'description': description,
    }, None


def _benefit_from_form(form, prefix: str = '') -> tuple[dict, str | None]:
    title = form.get(f'{prefix}title', '').strip()
    description = form.get(f'{prefix}description', '').strip()
    if not title:
        return {}, 'Benefit title is required.'
    return {'title': title, 'description': description}, None


def _tier_from_form(form, prefix: str = '') -> tuple[dict, str | None]:
    name = form.get(f'{prefix}name', '').strip()
    price = form.get(f'{prefix}price', '').strip()
    description = form.get(f'{prefix}description', '').strip()
    if not name:
        return {}, 'Tier name is required.'
    return {'name': name, 'price': price, 'description': description}, None


def _social_from_form(form, prefix: str = '') -> tuple[dict, str | None]:
    label = form.get(f'{prefix}label', '').strip()
    url = form.get(f'{prefix}url', '').strip()
    description = form.get(f'{prefix}description', '').strip()
    if not label:
        return {}, 'Label is required.'
    return {'label': label, 'url': url, 'description': description}, None


def _review_from_form(form, prefix: str = '') -> tuple[dict, str | None]:
    author_name = form.get(f'{prefix}author_name', '').strip()
    author_url = form.get(f'{prefix}author_url', '').strip()
    date_published = form.get(f'{prefix}date_published', '').strip()
    name = form.get(f'{prefix}name', '').strip()
    review_body = form.get(f'{prefix}review_body', '').strip()
    rating_raw = form.get(f'{prefix}review_rating', '').strip()

    if not author_name:
        return {}, 'Author name is required.'
    if not review_body:
        return {}, 'Review body is required.'
    if date_published and not _validate_iso_date(date_published):
        return {}, f'Invalid date_published format: {date_published!r}. Use YYYY-MM-DD.'
    try:
        review_rating = float(rating_raw) if rating_raw else None
        if review_rating is not None and not (0 <= review_rating <= 5):
            return {}, 'review_rating must be between 0 and 5.'
    except ValueError:
        return {}, f'Invalid review_rating: {rating_raw!r}.'

    return {
        'author_name': author_name,
        'author_url': author_url,
        'date_published': date_published or None,
        'name': name,
        'review_body': review_body,
        'review_rating': review_rating,
    }, None


def _validate_aggregate(payload: dict) -> str | None:
    rating_value = payload.get('rating_value')
    best_rating = payload.get('best_rating')
    worst_rating = payload.get('worst_rating')
    rating_count = payload.get('rating_count')
    review_count = payload.get('review_count')

    for field, val in [
        ('rating_value', rating_value),
        ('best_rating', best_rating),
        ('worst_rating', worst_rating),
    ]:
        if val is not None:
            try:
                v = float(val)
                if not (0 <= v <= 10):
                    return f'{field} must be between 0 and 10.'
            except (TypeError, ValueError):
                return f'Invalid {field}: {val!r}.'

    for field, val in [('rating_count', rating_count), ('review_count', review_count)]:
        if val is not None:
            try:
                v = int(val)
                if v < 0:
                    return f'{field} must be non-negative.'
            except (TypeError, ValueError):
                return f'Invalid {field}: {val!r}.'

    if (best_rating is not None and worst_rating is not None
            and float(best_rating) < float(worst_rating)):
        return 'best_rating must not be less than worst_rating.'

    return None
