-- Migration: Add connect_page table for patreon/supporter page metadata
-- Run on live database before deploying code changes

CREATE TABLE IF NOT EXISTS connect_page (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title               TEXT NOT NULL,
    intro               TEXT,
    membership_pitch    TEXT,
    primary_link_label  TEXT,
    primary_link_url    TEXT,
    secondary_link_label TEXT,
    secondary_link_url  TEXT
);

-- Seed with default patreon page data
INSERT INTO connect_page (title, intro, membership_pitch, primary_link_label, primary_link_url, secondary_link_label, secondary_link_url)
SELECT 'Patreon & Supporter Access',
       'Bonus material, closer updates, a community space, and a direct way to back the film financially. Join the journey on Patreon for exclusive content and early access to updates.',
       'Road footage, podcasts, and alternate cuts for a smaller audience that wants more personal updates and a direct way to back the film financially.',
       'Join On Patreon',
       'https://www.patreon.com/openmicodyssey',
       'Start With The Connect Hub',
       'https://www.openmicodyssey.com/connect'
WHERE NOT EXISTS (SELECT 1 FROM connect_page);

-- Seed patreon benefits
INSERT INTO patreon_benefit (title, description, sort_order)
VALUES
    ('Main Movie Access', 'A dedicated place to announce supporter-first access windows and early digital updates.', 0),
    ('Texas Podcast Material', 'A home for road-trip conversations and long-form audio that expands the documentary world.', 1),
    ('Driving Footage & Music Cuts', 'Extended driving sequences, alternate edits, and atmospheric material for fans.', 2)
ON CONFLICT (title) DO NOTHING;

-- Seed patreon tiers (add if your project has tiers defined)
-- INSERT INTO patreon_tier (name, price, description, sort_order) VALUES ...
