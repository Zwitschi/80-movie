from website.movie_site.db import get_conn
from website.movie_site.content_store import JsonContentReader
from website.app import create_app
import uuid
import os
import json
import sys
from pathlib import Path

# --- Data Insertion Functions ---


def insert_organizations(cursor, organizations_data):
    print("Inserting organizations...")
    orgs = organizations_data.get('organizations', {})
    for name, data in orgs.items():
        try:
            cursor.execute(
                """
                INSERT INTO organization (name, url, same_as, logo, contact_email)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (name) DO NOTHING;
                """,
                (
                    name,
                    data.get('url'),
                    json.dumps(data.get('same_as')),
                    data.get('logo'),
                    data.get('contact_email')
                )
            )
        except Exception as e:
            print(
                f"Error inserting organization '{name}': {e}", file=sys.stderr)
    print(f"{cursor.rowcount} new organizations inserted.")


def insert_people(cursor, people_data):
    print("Inserting people...")
    people = people_data.get('people', {})
    for name, data in people.items():
        cursor.execute(
            """
            INSERT INTO person (name, job_title, url, same_as, credit_note, roles)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO NOTHING;
            """,
            (
                name,
                data.get('job_title'),
                data.get('url'),
                json.dumps(data.get('same_as')),
                data.get('credit_note'),
                data.get('roles')
            )
        )
    print(f"{cursor.rowcount} new people inserted.")


def insert_movie(cursor, movie_data):
    print("Inserting movie...")
    cursor.execute("SELECT id FROM movie LIMIT 1;")
    if cursor.fetchone():
        print("Movie already exists. Skipping.")
        return

    movie = movie_data.get('movie', {})
    if not movie:
        print("No movie data found.")
        return

    cursor.execute(
        """
        INSERT INTO movie (title, tagline, description, genre, keywords, duration_iso, date_published, in_language, poster_image, content_rating, release_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
        """,
        (
            movie.get('title'),
            movie.get('tagline'),
            movie.get('description'),
            movie.get('genre'),
            movie.get('keywords'),
            movie.get('duration_iso'),
            movie.get('date_published'),
            movie.get('in_language', 'en'),
            movie.get('poster_image'),
            movie.get('content_rating'),
            movie.get('release_date')
        )
    )
    movie_id = cursor.fetchone()[0]
    print("Movie inserted.")

    # Insert 1:1 release status
    release_status = movie.get('release_status', {})
    if release_status:
        cursor.execute(
            """
            INSERT INTO movie_release_status (movie_id, label, headline, summary, detail)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (
                movie_id,
                release_status.get('label'),
                release_status.get('headline'),
                release_status.get('summary'),
                release_status.get('detail')
            )
        )
        print("Movie release status inserted.")


def insert_reviews(cursor, reviews_data, movie_id):
    print("Inserting reviews...")
    reviews = reviews_data.get('reviews', [])
    for review in reviews:
        # Simple check to avoid duplicates based on author and name
        cursor.execute(
            "SELECT id FROM review WHERE author_name = %s AND name = %s;",
            (review.get('author_name'), review.get('name'))
        )
        if cursor.fetchone():
            continue

        cursor.execute(
            """
            INSERT INTO review (movie_id, author_name, author_url, date_published, name, review_body, review_rating)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
            """,
            (
                movie_id,
                review.get('author_name'),
                review.get('author_url'),
                review.get('date_published'),
                review.get('name'),
                review.get('review_body'),
                review.get('review_rating')
            )
        )
    print(f"{len(reviews)} reviews processed.")


def insert_aggregate_rating(cursor, reviews_data, movie_id):
    print("Inserting aggregate rating...")
    agg_rating = reviews_data.get('aggregate_rating', {})
    if not agg_rating:
        print("No aggregate rating data found.")
        return

    cursor.execute(
        "SELECT id FROM aggregate_rating WHERE movie_id = %s;", (movie_id,))
    if cursor.fetchone():
        print("Aggregate rating already exists. Skipping.")
        return

    cursor.execute(
        """
        INSERT INTO aggregate_rating (movie_id, rating_value, best_rating, worst_rating, rating_count, review_count)
        VALUES (%s, %s, %s, %s, %s, %s);
        """,
        (
            movie_id,
            agg_rating.get('rating_value'),
            agg_rating.get('best_rating'),
            agg_rating.get('worst_rating'),
            agg_rating.get('rating_count'),
            agg_rating.get('review_count')
        )
    )
    print("Aggregate rating inserted.")


def insert_events_and_offers(cursor, events_data, movie_id, organization_id):
    print("Inserting screening events and offers...")
    events = events_data.get('events', [])
    for event in events:
        # Simple check to avoid duplicates based on name and start_date
        cursor.execute(
            "SELECT id FROM screening_event WHERE name = %s AND start_date = %s;",
            (event.get('name'), event.get('start_date'))
        )
        if cursor.fetchone():
            continue

        location = event.get('location', {})
        address = location.get('address', {})
        cursor.execute(
            """
            INSERT INTO screening_event (movie_id, name, description, start_date, end_date, event_status, event_attendance_mode, video_format, subtitle_language, location_name, location_url, location_street_address, location_locality, location_region, location_postal_code, location_country)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                movie_id,
                event.get('name'),
                event.get('description'),
                event.get('start_date'),
                event.get('end_date'),
                event.get('event_status'),
                event.get('event_attendance_mode'),
                event.get('video_format'),
                event.get('subtitle_language'),
                location.get('name'),
                location.get('url'),
                address.get('street_address'),
                address.get('address_locality'),
                address.get('address_region'),
                address.get('postal_code'),
                address.get('address_country')
            )
        )
        event_id = cursor.fetchone()[0]

        # Insert associated offers
        offers = event.get('offers', [])
        for offer_data in offers:
            cursor.execute(
                """
                INSERT INTO offer (name, url, description, category, availability, price, price_currency, valid_from)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (name, url) DO NOTHING
                RETURNING id;
                """,
                (
                    offer_data.get('name'),
                    offer_data.get('url'),
                    offer_data.get('description'),
                    offer_data.get('category'),
                    offer_data.get('availability'),
                    offer_data.get('price'),
                    offer_data.get('price_currency'),
                    offer_data.get('valid_from')
                )
            )
            offer_row = cursor.fetchone()
            if offer_row:
                offer_id = offer_row[0]
            else:
                cursor.execute(
                    "SELECT id FROM offer WHERE name = %s AND url = %s;",
                    (offer_data.get('name'), offer_data.get('url'))
                )
                offer_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO screening_offer (screening_event_id, offer_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
                (event_id, offer_id)
            )

    print(f"{len(events)} events processed.")


def insert_faq_items(cursor, faq_data, movie_id):
    print("Inserting FAQ items...")
    faq_items = faq_data.get('faq', [])
    for i, item in enumerate(faq_items):
        cursor.execute(
            "SELECT id FROM faq_item WHERE question = %s;",
            (item.get('question'),)
        )
        if cursor.fetchone():
            continue
        cursor.execute(
            "INSERT INTO faq_item (movie_id, question, answer, sort_order) VALUES (%s, %s, %s, %s);",
            (movie_id, item.get('question'), item.get('answer'), i)
        )
    print(f"{len(faq_items)} FAQ items processed.")


def insert_gallery_items(cursor, gallery_data, movie_id):
    print("Inserting gallery items...")
    gallery_items = gallery_data.get('gallery', [])
    for i, item in enumerate(gallery_items):
        cursor.execute(
            "SELECT id FROM gallery_item WHERE image_url = %s;",
            (item.get('image_url'),)
        )
        if cursor.fetchone():
            continue
        cursor.execute(
            "INSERT INTO gallery_item (movie_id, title, category, image_url, alt, description, sort_order) VALUES (%s, %s, %s, %s, %s, %s, %s);",
            (movie_id, item.get('title'), item.get('category'), item.get(
                'image_url'), item.get('alt'), item.get('description'), i)
        )
    print(f"{len(gallery_items)} gallery items processed.")


def insert_social_links(cursor, social_data):
    print("Inserting social links...")
    social_links = social_data.get('social', [])
    for i, link in enumerate(social_links):
        cursor.execute(
            "INSERT INTO social_link (label, url, description, sort_order) VALUES (%s, %s, %s, %s) ON CONFLICT (url) DO NOTHING;",
            (link.get('label'), link.get('url'), link.get('description'), i)
        )
    print(f"{len(social_links)} social links processed.")


def insert_connect_channels(cursor, connect_data):
    print("Inserting connect channels...")
    channels = connect_data.get('connect', {}).get(
        'links', {}).get('channels', [])
    for i, channel in enumerate(channels):
        cursor.execute(
            "INSERT INTO connect_channel (label, url, status, description, sort_order) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (url) DO NOTHING;",
            (channel.get('label'), channel.get('url'), channel.get(
                'status'), channel.get('description'), i)
        )
    print(f"{len(channels)} connect channels processed.")


def insert_patreon_info(cursor, connect_data):
    print("Inserting Patreon info...")
    page_data = connect_data.get('connect', {}).get('page', {})
    benefits = page_data.get('benefits', [])
    tiers = page_data.get('tiers', [])
    for i, benefit in enumerate(benefits):
        cursor.execute(
            "INSERT INTO patreon_benefit (title, description, sort_order) VALUES (%s, %s, %s) ON CONFLICT (title) DO NOTHING;",
            (benefit.get('title'), benefit.get('description'), i)
        )
    for i, tier in enumerate(tiers):
        cursor.execute(
            "INSERT INTO patreon_tier (name, price, description, sort_order) VALUES (%s, %s, %s, %s) ON CONFLICT (name) DO NOTHING;",
            (tier.get('name'), tier.get('price'), tier.get('description'), i)
        )
    print(f"{len(benefits)} benefits and {len(tiers)} tiers processed.")


def insert_pages(cursor, content_data):
    print("Inserting page content...")
    pages = content_data.get('pages', {})
    for route_name, page_data in pages.items():
        cursor.execute(
            """
            INSERT INTO page (route_name, path, title, description, keywords, content)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (route_name) DO UPDATE SET
                path = EXCLUDED.path,
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                keywords = EXCLUDED.keywords,
                content = EXCLUDED.content,
                updated_at = now();
            """,
            (
                route_name,
                page_data.get('path'),
                page_data.get('title'),
                page_data.get('description'),
                page_data.get('keywords'),
                json.dumps(page_data.get('content'))
            )
        )
    print(f"{len(pages)} pages processed.")


# --- Main Execution ---

def main():
    """
    Main function to initialize the database.
    Connects to the DB, reads JSON data, and inserts it into the tables.
    This script is designed to be idempotent.
    """
    print("Starting database initialization...")
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        print("Reading all JSON data files...")
        reader = JsonContentReader()
        all_content = reader.read_all()
        print("Data loaded.")

        # Insert data in order of dependency
        insert_organizations(cursor, all_content.get('organizations.json', {}))
        insert_people(cursor, all_content.get('people.json', {}))
        insert_movie(cursor, all_content.get('movies.json', {}))

        # Get the movie_id to link other data
        cursor.execute("SELECT id FROM movie LIMIT 1;")
        movie_row = cursor.fetchone()
        movie_id = movie_row[0] if movie_row else None

        if movie_id:
            print("Movie ID:", movie_id)
            insert_reviews(cursor, all_content.get('reviews.json', {}), movie_id)
            insert_aggregate_rating(
                cursor, all_content.get('reviews.json', {}), movie_id)

            # Get the organization_id to link events and offers
            cursor.execute("SELECT id FROM organization WHERE name = %s;",
                           ('Open Mic Odyssey Productions',))
            org_row = cursor.fetchone()
            organization_id = org_row[0] if org_row else None

            if movie_id and organization_id:
                insert_events_and_offers(cursor, all_content.get(
                    'events.json', {}), movie_id, organization_id)
            else:
                print(
                    "Cannot insert events without movie_id and organization_id.", file=sys.stderr)

            # Insert FAQ and gallery items for the movie
            insert_faq_items(cursor, all_content.get('faq.json', {}), movie_id)
            insert_gallery_items(cursor, all_content.get(
                'gallery.json', {}), movie_id)

        insert_social_links(cursor, all_content.get('social.json', {}))
        insert_connect_channels(cursor, all_content.get('connect.json', {}))
        insert_patreon_info(cursor, all_content.get('connect.json', {}))
        insert_pages(cursor, all_content.get('content.json', {}))

        conn.commit()
        print("Database initialization committed successfully.")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"An error occurred: {e}", file=sys.stderr)
        print("Transaction rolled back.", file=sys.stderr)
        sys.exit(1)
    finally:
        if conn:
            cursor.close()
            conn.close()
            print("Database connection closed.")


if __name__ == "__main__":
    # The script needs the Flask app context to get the DB config
    app = create_app()
    with app.app_context():
        main()
