from .db import get_conn, get_dict_cursor
import json
from uuid import uuid4


def _get_movie_id(cursor):
    """Get the single movie ID, or create one if none exists."""
    cursor.execute("SELECT id FROM movie LIMIT 1")
    row = cursor.fetchone()
    if row:
        return row['id']
    movie_id = uuid4()
    cursor.execute(
        "INSERT INTO movie (id, title, tagline, description, genre, duration_iso, release_date) "
        "VALUES (%s, '', '', '', '', '', '')",
        (str(movie_id),)
    )
    return movie_id


class DbContentReader:
    def read(self, filename: str):
        cursor = get_dict_cursor()
        try:
            return self._read_file(cursor, filename)
        finally:
            cursor.close()

    def _read_file(self, cursor, filename: str):
        readers = {
            'movies.json': self._read_movies,
            'gallery.json': self._read_gallery,
            'events.json': self._read_events,
            'faq.json': self._read_faq,
            'reviews.json': self._read_reviews,
            'people.json': self._read_people,
            'organizations.json': self._read_organizations,
            'offers.json': self._read_offers,
            'social.json': self._read_social,
            'connect.json': self._read_connect,
            'content.json': self._read_content,
            'media_assets.json': self._read_media_assets,
        }
        handler = readers.get(filename)
        if handler:
            return handler(cursor)
        return {}

    def _read_movies(self, cursor):
        cursor.execute("SELECT * FROM movie LIMIT 1")
        movie = cursor.fetchone()
        if not movie:
            return {'movie': {}}
        cursor.execute(
            "SELECT * FROM movie_release_status WHERE movie_id = %s", (movie['id'],))
        rs = cursor.fetchone()
        result = {
            'movie': {
                'title': movie.get('title', ''),
                'tagline': movie.get('tagline', ''),
                'description': movie.get('description', ''),
                'genre': movie.get('genre', ''),
                'keywords': movie.get('keywords', []) or [],
                'runtime': movie.get('duration_iso', ''),
                'duration_iso': movie.get('duration_iso', ''),
                'release_date': movie.get('release_date', ''),
                'release_status': {
                    'label': rs.get('label', '') if rs else '',
                    'headline': rs.get('headline', '') if rs else '',
                    'summary': rs.get('summary', '') if rs else '',
                    'detail': rs.get('detail', '') if rs else '',
                } if rs else {},
            }
        }
        return result

    def _read_gallery(self, cursor):
        cursor.execute("SELECT * FROM gallery_item ORDER BY sort_order, id")
        items = []
        for row in cursor.fetchall():
            items.append({
                'title': row.get('title', ''),
                'category': row.get('category', ''),
                'image_url': row.get('image_url', ''),
                'alt': row.get('alt', ''),
                'description': row.get('description', ''),
            })
        # Read categories from gallery_item distinct values
        cursor.execute(
            "SELECT DISTINCT category FROM gallery_item WHERE category IS NOT NULL AND category != '' ORDER BY category")
        categories = [r['category'] for r in cursor.fetchall()]
        return {'gallery': items, 'categories': categories}

    def _read_events(self, cursor):
        cursor.execute("SELECT * FROM screening_event ORDER BY start_date")
        events = []
        for row in cursor.fetchall():
            event = {
                'name': row.get('name', ''),
                'description': row.get('description', ''),
                'start_date': str(row.get('start_date', '')) if row.get('start_date') else '',
                'end_date': str(row.get('end_date', '')) if row.get('end_date') else '',
                'event_status': row.get('event_status', ''),
                'event_attendance_mode': row.get('event_attendance_mode', ''),
                'location': {
                    'name': row.get('location_name', ''),
                    'url': row.get('location_url', ''),
                    'address': {
                        'street_address': row.get('location_street_address', ''),
                        'address_locality': row.get('location_locality', ''),
                        'address_region': row.get('location_region', ''),
                        'postal_code': row.get('location_postal_code', ''),
                        'address_country': row.get('location_country', ''),
                    }
                },
                'video_format': row.get('video_format', ''),
                'subtitle_language': row.get('subtitle_language', ''),
                'offers': [],
            }
            # Get offers for this event
            cursor.execute(
                "SELECT o.* FROM offer o "
                "JOIN screening_offer so ON o.id = so.offer_id "
                "WHERE so.screening_event_id = %s",
                (row['id'],)
            )
            for offer_row in cursor.fetchall():
                event['offers'].append({
                    'name': offer_row.get('name', ''),
                    'url': offer_row.get('url', ''),
                    'price': float(offer_row.get('price', 0) or 0),
                    'price_currency': offer_row.get('price_currency', 'USD'),
                    'availability': offer_row.get('availability', ''),
                    'valid_from': str(offer_row.get('valid_from', '')) if offer_row.get('valid_from') else '',
                })
            events.append(event)
        return {'events': events}

    def _read_faq(self, cursor):
        cursor.execute("SELECT * FROM faq_item ORDER BY sort_order, id")
        items = [{'question': r['question'], 'answer': r['answer']}
                 for r in cursor.fetchall()]
        return {'faq': items}

    def _read_reviews(self, cursor):
        movie_id = _get_movie_id(cursor)
        cursor.execute(
            "SELECT * FROM review WHERE movie_id = %s ORDER BY date_published DESC", (movie_id,))
        reviews = []
        for row in cursor.fetchall():
            reviews.append({
                'author_name': row.get('author_name', ''),
                'author_url': row.get('author_url', ''),
                'date_published': str(row.get('date_published', '')) if row.get('date_published') else '',
                'name': row.get('name', ''),
                'review_body': row.get('review_body', ''),
                'review_rating': float(row.get('review_rating', 0) or 0),
            })
        cursor.execute(
            "SELECT * FROM aggregate_rating WHERE movie_id = %s", (movie_id,))
        agg = cursor.fetchone()
        aggregate = {}
        if agg:
            aggregate = {
                'rating_value': float(agg.get('rating_value', 0) or 0),
                'best_rating': float(agg.get('best_rating', 5) or 5),
                'worst_rating': float(agg.get('worst_rating', 1) or 1),
                'rating_count': agg.get('rating_count', 0) or 0,
                'review_count': agg.get('review_count', 0) or 0,
            }
        return {'reviews': reviews, 'aggregate_rating': aggregate}

    def _read_people(self, cursor):
        cursor.execute("SELECT * FROM person ORDER BY name")
        people = {}
        for row in cursor.fetchall():
            people[row['name']] = {
                'name': row['name'],
                'url': row.get('url', ''),
                'same_as': row.get('same_as', []) or [],
                'roles': row.get('roles', []) or [],
                'job_title': row.get('job_title', ''),
                'credit_note': row.get('credit_note', ''),
            }
        # Contributors by role
        cursor.execute("""
            SELECT p.name, p.job_title, p.url, p.same_as, p.credit_note, mc.role
            FROM movie_credit mc
            JOIN person p ON p.id = mc.person_id
            ORDER BY mc.role, mc.sort_order, p.name
        """)
        contributors = {'directors': [], 'producers': [], 'actors': []}
        for row in cursor.fetchall():
            entry = {
                'name': row['name'],
                'job_title': row.get('job_title', ''),
                'url': row.get('url', ''),
                'same_as': row.get('same_as', []) or [],
                'credit_note': row.get('credit_note', ''),
            }
            role_key = row['role'] + 's'  # director -> directors
            if role_key in contributors:
                contributors[role_key].append(entry)
        # Credits people (all credits)
        cursor.execute("""
            SELECT p.name, mc.role, mc.sort_order
            FROM movie_credit mc
            JOIN person p ON p.id = mc.person_id
            ORDER BY mc.sort_order, p.name
        """)
        credits_people = [{'name': r['name'], 'role': r['role']}
                          for r in cursor.fetchall()]
        return {'people': people, 'contributors': contributors, 'credits_people': credits_people}

    def _read_organizations(self, cursor):
        cursor.execute("SELECT * FROM organization ORDER BY name")
        orgs = {}
        for row in cursor.fetchall():
            # Get members
            cursor.execute(
                "SELECT p.name FROM person p "
                "JOIN organization_member om ON om.person_id = p.id "
                "WHERE om.organization_id = %s",
                (row['id'],)
            )
            members = [r['name'] for r in cursor.fetchall()]
            orgs[row['name']] = {
                'name': row['name'],
                'url': row.get('url', ''),
                'same_as': row.get('same_as', []) or [],
                'people': members,
            }
        return {'organizations': orgs}

    def _read_offers(self, cursor):
        cursor.execute("SELECT * FROM offer ORDER BY name")
        offers = []
        for row in cursor.fetchall():
            offers.append({
                'name': row.get('name', ''),
                'url': row.get('url', ''),
                'description': row.get('description', ''),
                'category': row.get('category', ''),
                'availability': row.get('availability', ''),
                'price': float(row.get('price', 0) or 0),
                'price_currency': row.get('price_currency', 'USD'),
                'valid_from': str(row.get('valid_from', '')) if row.get('valid_from') else '',
            })
        return {'offers': offers}

    def _read_social(self, cursor):
        cursor.execute("SELECT * FROM social_link ORDER BY sort_order, id")
        items = [
            {
                'label': r['label'],
                'url': r['url'],
                'description': r.get('description', ''),
            }
            for r in cursor.fetchall()
        ]
        return {'social': items}

    def _read_connect(self, cursor):
        cursor.execute("SELECT * FROM connect_channel ORDER BY sort_order, id")
        channels = []
        for row in cursor.fetchall():
            channels.append({
                'label': row['label'],
                'url': row['url'],
                'status': row.get('status', ''),
                'description': row.get('description', ''),
            })
        return {'connect': {'links': {'channels': channels}}}

    def _read_content(self, cursor):
        cursor.execute("SELECT * FROM page ORDER BY route_name")
        pages = {}
        for row in cursor.fetchall():
            content = row.get('content', {})
            if isinstance(content, str):
                content = json.loads(content)
            pages[row['route_name']] = {
                'title': row['title'],
                'description': row.get('description', ''),
                'keywords': row.get('keywords', []) or [],
                'path': row['path'],
                'content': content,
            }
        return {'pages': pages}

    def _read_media_assets(self, cursor):
        cursor.execute("SELECT * FROM movie LIMIT 1")
        movie = cursor.fetchone()
        if not movie:
            return {'media': {}}
        result = {
            'media': {
                'date_published': str(movie.get('date_published', '')) if movie.get('date_published') else None,
                'in_language': movie.get('in_language', 'en'),
                'content_rating': movie.get('content_rating', ''),
                'poster_image': movie.get('poster_image', ''),
            }
        }
        # Contact email from organization
        cursor.execute("SELECT contact_email FROM organization LIMIT 1")
        org = cursor.fetchone()
        if org:
            result['media']['contact_email'] = org.get('contact_email', '')
        # Trailer info - would need a trailer table, for now use movie fields
        result['media']['trailer'] = {
            'name': '',
            'description': '',
            'url': '',
            'embed_url': '',
            'thumbnail_url': '',
            'upload_date': '',
            'duration_iso': '',
            'encoding_format': '',
            'is_family_friendly': True,
        }
        return result

    def read_all(self) -> dict:
        result = {}
        for filename in [
            'movies.json', 'gallery.json', 'events.json', 'faq.json',
            'reviews.json', 'people.json', 'organizations.json',
            'offers.json', 'social.json', 'connect.json',
            'content.json', 'media_assets.json',
        ]:
            result[filename] = self.read(filename)
        return result


class DbContentWriter:
    def write(self, filename: str, payload) -> None:
        cursor = get_dict_cursor()
        conn = get_conn()
        try:
            self._write_file(cursor, conn, filename, payload)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def _write_file(self, cursor, conn, filename: str, payload):
        writers = {
            'movies.json': self._write_movies,
            'gallery.json': self._write_gallery,
            'events.json': self._write_events,
            'faq.json': self._write_faq,
            'reviews.json': self._write_reviews,
            'people.json': self._write_people,
            'organizations.json': self._write_organizations,
            'offers.json': self._write_offers,
            'social.json': self._write_social,
            'connect.json': self._write_connect,
            'content.json': self._write_content,
            'media_assets.json': self._write_media_assets,
        }
        handler = writers.get(filename)
        if handler:
            handler(cursor, payload)

    def _write_movies(self, cursor, payload):
        movie = payload.get('movie', {})
        movie_id = _get_movie_id(cursor)
        cursor.execute(
            "UPDATE movie SET title=%s, tagline=%s, description=%s, genre=%s, "
            "keywords=%s, duration_iso=%s, release_date=%s WHERE id=%s",
            (
                movie.get('title', ''),
                movie.get('tagline', ''),
                movie.get('description', ''),
                movie.get('genre', ''),
                movie.get('keywords', []),
                movie.get('duration_iso', ''),
                movie.get('release_date', ''),
                str(movie_id),
            )
        )
        rs = movie.get('release_status', {})
        if rs:
            cursor.execute(
                "SELECT id FROM movie_release_status WHERE movie_id = %s", (str(movie_id),))
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    "UPDATE movie_release_status SET label=%s, headline=%s, summary=%s, detail=%s WHERE movie_id=%s",
                    (rs.get('label', ''), rs.get('headline', ''), rs.get(
                        'summary', ''), rs.get('detail', ''), str(movie_id))
                )
            else:
                cursor.execute(
                    "INSERT INTO movie_release_status (movie_id, label, headline, summary, detail) VALUES (%s, %s, %s, %s, %s)",
                    (str(movie_id), rs.get('label', ''), rs.get(
                        'headline', ''), rs.get('summary', ''), rs.get('detail', ''))
                )

    def _write_gallery(self, cursor, payload):
        # Clear existing
        cursor.execute("DELETE FROM gallery_item")
        items = payload.get('gallery', [])
        for idx, item in enumerate(items):
            cursor.execute(
                "INSERT INTO gallery_item (movie_id, title, category, image_url, alt, description, sort_order) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    str(_get_movie_id(cursor)),
                    item.get('title', ''),
                    item.get('category', ''),
                    item.get('image_url', ''),
                    item.get('alt', ''),
                    item.get('description', ''),
                    idx,
                )
            )

    def _write_events(self, cursor, payload):
        # Clear existing events and their offers
        cursor.execute("DELETE FROM screening_offer")
        cursor.execute("DELETE FROM screening_event")
        events = payload.get('events', [])
        for event in events:
            loc = event.get('location', {})
            addr = loc.get('address', {})
            cursor.execute(
                "INSERT INTO screening_event (movie_id, name, description, start_date, end_date, "
                "event_status, event_attendance_mode, location_name, location_url, "
                "location_street_address, location_locality, location_region, location_postal_code, location_country, "
                "video_format, subtitle_language) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (
                    str(_get_movie_id(cursor)),
                    event.get('name', ''),
                    event.get('description', ''),
                    event.get('start_date') or None,
                    event.get('end_date') or None,
                    event.get('event_status', ''),
                    event.get('event_attendance_mode', ''),
                    loc.get('name', ''),
                    loc.get('url', ''),
                    addr.get('street_address', ''),
                    addr.get('address_locality', ''),
                    addr.get('address_region', ''),
                    addr.get('postal_code', ''),
                    addr.get('address_country', ''),
                    event.get('video_format', ''),
                    event.get('subtitle_language', ''),
                )
            )
            event_id = cursor.fetchone()['id']
            for offer in event.get('offers', []):
                cursor.execute(
                    "INSERT INTO offer (name, url, description, category, availability, price, price_currency, valid_from) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (
                        offer.get('name', ''),
                        offer.get('url', ''),
                        offer.get('description', ''),
                        offer.get('category', ''),
                        offer.get('availability', ''),
                        offer.get('price', 0),
                        offer.get('price_currency', 'USD'),
                        offer.get('valid_from') or None,
                    )
                )
                offer_id = cursor.fetchone()['id']
                cursor.execute(
                    "INSERT INTO screening_offer (screening_event_id, offer_id) VALUES (%s, %s)",
                    (str(event_id), str(offer_id))
                )

    def _write_faq(self, cursor, payload):
        cursor.execute("DELETE FROM faq_item")
        items = payload.get('faq', [])
        for idx, item in enumerate(items):
            cursor.execute(
                "INSERT INTO faq_item (movie_id, question, answer, sort_order) VALUES (%s, %s, %s, %s)",
                (str(_get_movie_id(cursor)), item.get(
                    'question', ''), item.get('answer', ''), idx)
            )

    def _write_reviews(self, cursor, payload):
        movie_id = _get_movie_id(cursor)
        cursor.execute("DELETE FROM review WHERE movie_id = %s",
                       (str(movie_id),))
        reviews = payload.get('reviews', [])
        for review in reviews:
            cursor.execute(
                "INSERT INTO review (movie_id, author_name, author_url, date_published, name, review_body, review_rating) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    str(movie_id),
                    review.get('author_name', ''),
                    review.get('author_url', ''),
                    review.get('date_published') or None,
                    review.get('name', ''),
                    review.get('review_body', ''),
                    review.get('review_rating', 0),
                )
            )
        agg = payload.get('aggregate_rating', {})
        if agg:
            cursor.execute(
                "SELECT id FROM aggregate_rating WHERE movie_id = %s", (str(movie_id),))
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    "UPDATE aggregate_rating SET rating_value=%s, best_rating=%s, worst_rating=%s, rating_count=%s, review_count=%s WHERE movie_id=%s",
                    (agg.get('rating_value', 0), agg.get('best_rating', 5), agg.get('worst_rating', 1),
                     agg.get('rating_count', 0), agg.get('review_count', 0), str(movie_id))
                )
            else:
                cursor.execute(
                    "INSERT INTO aggregate_rating (movie_id, rating_value, best_rating, worst_rating, rating_count, review_count) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (str(movie_id), agg.get('rating_value', 0), agg.get('best_rating', 5), agg.get('worst_rating', 1),
                     agg.get('rating_count', 0), agg.get('review_count', 0))
                )

    def _write_people(self, cursor, payload):
        # Clear and rebuild
        cursor.execute("DELETE FROM movie_credit")
        cursor.execute("DELETE FROM person")
        people = payload.get('people', {})
        for name, person in people.items():
            cursor.execute(
                "INSERT INTO person (name, url, same_as, roles, job_title, credit_note) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    person.get('name', name),
                    person.get('url', ''),
                    json.dumps(person.get('same_as', [])),
                    person.get('roles', []),
                    person.get('job_title', ''),
                    person.get('credit_note', ''),
                )
            )
        # Contributors → movie_credit
        contributors = payload.get('contributors', {})
        for role_plural, entries in contributors.items():
            role = role_plural.rstrip('s')  # directors -> director
            for entry in entries:
                cursor.execute(
                    "SELECT id FROM person WHERE name = %s", (entry.get('name', ''),))
                person_row = cursor.fetchone()
                if person_row:
                    cursor.execute(
                        "INSERT INTO movie_credit (movie_id, person_id, role) VALUES (%s, %s, %s)",
                        (str(_get_movie_id(cursor)),
                         str(person_row['id']), role)
                    )
        # Credits people
        credits_people = payload.get('credits_people', [])
        for idx, credit in enumerate(credits_people):
            cursor.execute("SELECT id FROM person WHERE name = %s",
                           (credit.get('name', ''),))
            person_row = cursor.fetchone()
            if person_row:
                cursor.execute(
                    "UPDATE movie_credit SET sort_order=%s WHERE movie_id=%s AND person_id=%s AND role=%s",
                    (idx, str(_get_movie_id(cursor)), str(
                        person_row['id']), credit.get('role', ''))
                )

    def _write_organizations(self, cursor, payload):
        cursor.execute("DELETE FROM organization_member")
        cursor.execute("DELETE FROM organization")
        orgs = payload.get('organizations', {})
        for name, org in orgs.items():
            cursor.execute(
                "INSERT INTO organization (name, url, same_as) VALUES (%s, %s, %s) RETURNING id",
                (org.get('name', name), org.get('url', ''),
                 json.dumps(org.get('same_as', [])))
            )
            org_id = cursor.fetchone()['id']
            for person_name in org.get('people', []):
                cursor.execute(
                    "SELECT id FROM person WHERE name = %s", (person_name,))
                person_row = cursor.fetchone()
                if person_row:
                    cursor.execute(
                        "INSERT INTO organization_member (organization_id, person_id) VALUES (%s, %s)",
                        (str(org_id), str(person_row['id']))
                    )

    def _write_offers(self, cursor, payload):
        cursor.execute("DELETE FROM movie_offer")
        cursor.execute("DELETE FROM offer")
        offers = payload.get('offers', [])
        for offer in offers:
            cursor.execute(
                "INSERT INTO offer (name, url, description, category, availability, price, price_currency, valid_from) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (
                    offer.get('name', ''),
                    offer.get('url', ''),
                    offer.get('description', ''),
                    offer.get('category', ''),
                    offer.get('availability', ''),
                    offer.get('price', 0),
                    offer.get('price_currency', 'USD'),
                    offer.get('valid_from') or None,
                )
            )
            offer_id = cursor.fetchone()['id']
            cursor.execute(
                "INSERT INTO movie_offer (movie_id, offer_id) VALUES (%s, %s)",
                (str(_get_movie_id(cursor)), str(offer_id))
            )

    def _write_social(self, cursor, payload):
        cursor.execute("DELETE FROM social_link")
        items = payload.get('social', [])
        for idx, item in enumerate(items):
            cursor.execute(
                "INSERT INTO social_link (label, url, description, sort_order) VALUES (%s, %s, %s, %s)",
                (item.get('label', ''), item.get('url', ''),
                 item.get('description', ''), idx)
            )

    def _write_connect(self, cursor, payload):
        cursor.execute("DELETE FROM connect_channel")
        channels = payload.get('connect', {}).get(
            'links', {}).get('channels', [])
        for idx, ch in enumerate(channels):
            cursor.execute(
                "INSERT INTO connect_channel (label, url, status, description, sort_order) VALUES (%s, %s, %s, %s, %s)",
                (ch.get('label', ''), ch.get('url', ''), ch.get(
                    'status', ''), ch.get('description', ''), idx)
            )

    def _write_content(self, cursor, payload):
        pages = payload.get('pages', {})
        for route_name, page in pages.items():
            content = page.get('content', {})
            cursor.execute(
                "SELECT id FROM page WHERE route_name = %s", (route_name,))
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    "UPDATE page SET title=%s, description=%s, keywords=%s, path=%s, content=%s WHERE route_name=%s",
                    (
                        page.get('title', ''),
                        page.get('description', ''),
                        page.get('keywords', []),
                        page.get('path', ''),
                        json.dumps(content),
                        route_name,
                    )
                )
            else:
                cursor.execute(
                    "INSERT INTO page (route_name, path, title, description, keywords, content) VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        route_name,
                        page.get('path', ''),
                        page.get('title', ''),
                        page.get('description', ''),
                        page.get('keywords', []),
                        json.dumps(content),
                    )
                )

    def _write_media_assets(self, cursor, payload):
        media = payload.get('media', {})
        movie_id = _get_movie_id(cursor)
        cursor.execute(
            "UPDATE movie SET date_published=%s, in_language=%s, content_rating=%s, poster_image=%s WHERE id=%s",
            (
                media.get('date_published') or None,
                media.get('in_language', 'en'),
                media.get('content_rating', ''),
                media.get('poster_image', ''),
                str(movie_id),
            )
        )
        # Update org contact email
        contact_email = media.get('contact_email', '')
        if contact_email:
            cursor.execute("SELECT id FROM organization LIMIT 1")
            org = cursor.fetchone()
            if org:
                cursor.execute(
                    "UPDATE organization SET contact_email=%s WHERE id=%s", (contact_email, str(org['id'])))


def get_content_reader() -> DbContentReader:
    return DbContentReader()


def get_content_writer() -> DbContentWriter:
    return DbContentWriter()
