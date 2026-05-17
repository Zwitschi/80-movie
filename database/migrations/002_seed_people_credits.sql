-- Migration: Seed people, credits, organizations from original JSON data
-- Run on live database

-- People
INSERT INTO person (name, url, same_as, roles, job_title, credit_note)
VALUES
    ('Bobby Ludlam', 'https://www.bobbyludlam.com', '["https://www.bobbyludlam.com", "https://www.instagram.com/bobbyludlam/"]', '{"Comedian","Security","Self"}', 'Self', 'One of the three best friends at the heart of the documentary, a comedian chasing stage time and a bigger creative dream.'),
    ('Corey Pellizzi', 'https://instagram.com/owlmovement', '["https://instagram.com/owlmovement"]', '{"Comedian","Director","Producer","Security","Self"}', 'Director, Producer', 'Directing, filming, and drawn to places of his childhood, creativity and freedom.'),
    ('Georg Sinn', 'https://zwitschi.net', '["https://zwitschi.net", "https://allucanget.biz", "https://www.instagram.com/allucanget"]', '{"Manager","Driver","Traveler","Security","Self","Producer"}', 'Producer', 'From far away, driving across America and keeping the crew rolling toward the next place to film, perform, and connect with the comedy world. Infrastructure, logistics, IT, development, finance.'),
    ('Open Mic Odyssey Team', 'https://www.openmicodyssey.com', '["https://www.openmicodyssey.com"]', '{"Director","Producer"}', 'Director', 'Shapes the documentary point of view and guides the on-the-road narrative structure. Coordinates production, release planning, and how the film reaches audiences.')
ON CONFLICT (name) DO NOTHING;

-- Movie credits (link people to movie with roles)
-- First get the movie ID
DO $$
DECLARE
    movie_id UUID;
    person_id UUID;
BEGIN
    SELECT id INTO movie_id FROM movie LIMIT 1;
    IF movie_id IS NULL THEN
        RAISE EXCEPTION 'No movie record found';
    END IF;

    -- Directors
    SELECT id INTO person_id FROM person WHERE name = 'Corey Pellizzi';
    IF person_id IS NOT NULL THEN
        INSERT INTO movie_credit (movie_id, person_id, role, sort_order) VALUES (movie_id, person_id, 'director', 0) ON CONFLICT DO NOTHING;
    END IF;
    SELECT id INTO person_id FROM person WHERE name = 'Open Mic Odyssey Team';
    IF person_id IS NOT NULL THEN
        INSERT INTO movie_credit (movie_id, person_id, role, sort_order) VALUES (movie_id, person_id, 'director', 1) ON CONFLICT DO NOTHING;
    END IF;

    -- Producers
    SELECT id INTO person_id FROM person WHERE name = 'Corey Pellizzi';
    IF person_id IS NOT NULL THEN
        INSERT INTO movie_credit (movie_id, person_id, role, sort_order) VALUES (movie_id, person_id, 'producer', 0) ON CONFLICT DO NOTHING;
    END IF;
    SELECT id INTO person_id FROM person WHERE name = 'Georg Sinn';
    IF person_id IS NOT NULL THEN
        INSERT INTO movie_credit (movie_id, person_id, role, sort_order) VALUES (movie_id, person_id, 'producer', 1) ON CONFLICT DO NOTHING;
    END IF;

    -- Actors
    SELECT id INTO person_id FROM person WHERE name = 'Bobby Ludlam';
    IF person_id IS NOT NULL THEN
        INSERT INTO movie_credit (movie_id, person_id, role, sort_order) VALUES (movie_id, person_id, 'actor', 0) ON CONFLICT DO NOTHING;
    END IF;
    SELECT id INTO person_id FROM person WHERE name = 'Corey Pellizzi';
    IF person_id IS NOT NULL THEN
        INSERT INTO movie_credit (movie_id, person_id, role, sort_order) VALUES (movie_id, person_id, 'actor', 1) ON CONFLICT DO NOTHING;
    END IF;
    SELECT id INTO person_id FROM person WHERE name = 'Georg Sinn';
    IF person_id IS NOT NULL THEN
        INSERT INTO movie_credit (movie_id, person_id, role, sort_order) VALUES (movie_id, person_id, 'actor', 2) ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Organizations
INSERT INTO organization (name, url, same_as)
VALUES
    ('Open Mic Odyssey Productions', 'https://www.openmicodyssey.com', '["https://www.openmicodyssey.com", "https://www.youtube.com/@openmicodyssey", "https://www.instagram.com/openmicodyssey", "https://www.tiktok.com/@openmicodyssey", "https://www.patreon.com/openmicodyssey"]')
ON CONFLICT (name) DO NOTHING;

-- Organization members
DO $$
DECLARE
    org_id UUID;
    person_id UUID;
BEGIN
    SELECT id INTO org_id FROM organization WHERE name = 'Open Mic Odyssey Productions';
    IF org_id IS NOT NULL THEN
        SELECT id INTO person_id FROM person WHERE name = 'Corey Pellizzi';
        IF person_id IS NOT NULL THEN
            INSERT INTO organization_member (organization_id, person_id) VALUES (org_id, person_id) ON CONFLICT DO NOTHING;
        END IF;
        SELECT id INTO person_id FROM person WHERE name = 'Georg Sinn';
        IF person_id IS NOT NULL THEN
            INSERT INTO organization_member (organization_id, person_id) VALUES (org_id, person_id) ON CONFLICT DO NOTHING;
        END IF;
    END IF;
END $$;
