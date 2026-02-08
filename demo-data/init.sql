CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS stockholm_pois (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL,
    category TEXT DEFAULT 'landmark',
    description TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS stockholm_pois_geom_idx ON stockholm_pois USING GIST (geom);

INSERT INTO stockholm_pois (name, geom, category, description) VALUES
  ('Kungliga slottet',        ST_SetSRID(ST_MakePoint(18.0718, 59.3268), 4326), 'landmark',    'The Royal Palace of Sweden, official residence of the Swedish monarch.'),
  ('Storkyrkan',              ST_SetSRID(ST_MakePoint(18.0709, 59.3260), 4326), 'place_of_worship', 'Stockholm Cathedral, the oldest church in Gamla Stan.'),
  ('Stortorget',              ST_SetSRID(ST_MakePoint(18.0714, 59.3243), 4326), 'landmark',    'The main square of Gamla Stan, site of the Stockholm Bloodbath of 1520.'),
  ('Nobel Museum',            ST_SetSRID(ST_MakePoint(18.0718, 59.3247), 4326), 'museum',      'Museum celebrating the Nobel Prize and its laureates.'),
  ('Riksdagshuset',           ST_SetSRID(ST_MakePoint(18.0674, 59.3275), 4326), 'government',  'The Swedish Parliament building on Helgeandsholmen island.'),
  ('Kungliga Operan',         ST_SetSRID(ST_MakePoint(18.0694, 59.3299), 4326), 'arts',        'The Royal Swedish Opera house.'),
  ('Gustav III:s Antikmuseum',ST_SetSRID(ST_MakePoint(18.0720, 59.3265), 4326), 'museum',      'Collection of classical antiquities in the Royal Palace.'),
  ('Livrustkammaren',         ST_SetSRID(ST_MakePoint(18.0725, 59.3258), 4326), 'museum',      'The Royal Armoury, Sweden''s oldest museum.'),
  ('Tyska kyrkan',            ST_SetSRID(ST_MakePoint(18.0734, 59.3248), 4326), 'place_of_worship', 'The German Church in Gamla Stan, built in the 17th century.'),
  ('Mårten Trotzigs Gränd',   ST_SetSRID(ST_MakePoint(18.0697, 59.3233), 4326), 'landmark',    'Stockholm''s narrowest alley, only 90 cm wide at its tightest.'),
  ('Postmuseum',              ST_SetSRID(ST_MakePoint(18.0700, 59.3238), 4326), 'museum',      'Museum of Swedish postal history.'),
  ('Riddarholmskyrkan',       ST_SetSRID(ST_MakePoint(18.0648, 59.3244), 4326), 'place_of_worship', 'Medieval church, burial site of Swedish royalty.'),
  ('Gamla Stan Tunnelbana',   ST_SetSRID(ST_MakePoint(18.0675, 59.3233), 4326), 'transport',   'Gamla Stan metro station, serving the T-bana green and red lines.'),
  ('Slottsbacken Café',       ST_SetSRID(ST_MakePoint(18.0728, 59.3261), 4326), 'food',        'Cosy café at the foot of the palace hill.'),
  ('Källaren Aurora',         ST_SetSRID(ST_MakePoint(18.0702, 59.3250), 4326), 'food',        'Traditional Swedish restaurant in a 17th century cellar.'),
  ('Gamla Stan Bokhandel',    ST_SetSRID(ST_MakePoint(18.0711, 59.3239), 4326), 'shop',        'Independent bookshop specialising in Swedish history and art.'),
  ('Chokladkoppen',           ST_SetSRID(ST_MakePoint(18.0716, 59.3244), 4326), 'food',        'Iconic hot chocolate and waffle café on Stortorget.'),
  ('Kungliga Myntkabinettet', ST_SetSRID(ST_MakePoint(18.0722, 59.3256), 4326), 'museum',      'The Royal Coin Cabinet, museum of economic and monetary history.'),
  ('Fotografiska Gamla Stan',  ST_SetSRID(ST_MakePoint(18.0690, 59.3235), 4326), 'arts',        'Photography exhibition space in the old town.'),
  ('Slussen Utsiktsplats',    ST_SetSRID(ST_MakePoint(18.0730, 59.3195), 4326), 'landmark',    'Viewpoint over Stockholm''s waterways from Slussen.');
