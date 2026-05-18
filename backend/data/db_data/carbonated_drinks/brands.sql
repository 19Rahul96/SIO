CREATE TABLE brands (
    brand_id INTEGER,
    brand_name TEXT,
    parent_company TEXT,
    headquarters_country TEXT,
    founded_year INTEGER,
    sustainability_score REAL,
    website TEXT,
    created_at TEXT,
    PRIMARY KEY (brand_id)
);

INSERT INTO brands (brand_id, brand_name, parent_company, headquarters_country, founded_year, sustainability_score, website, created_at) VALUES
(1, 'Bubble Soda', 'Summit Foods Ltd', 'USA', 1977, 94.85, 'https://www.bubblesoda.com', '2026-09-28 14:05:42'),
(2, 'Viva Drinks', 'Summit Foods Ltd', 'UK', 2007, 78.11, 'https://www.vivadrinks.com', '2023-07-15 19:53:11'),
(3, 'Nova Cola', 'HydroTaste Corp', 'USA', 1977, 88.56, 'https://www.novacola.com', '2025-03-26 01:30:04'),
(4, 'Fizz Refresh', 'Global Beverage Group', 'Brazil', 1950, 69.57, 'https://www.fizzrefresh.com', '2022-11-19 05:39:51'),
(5, 'River Drinks', 'Summit Foods Ltd', 'India', 1958, 82.58, 'https://www.riverdrinks.com', '2024-07-13 14:18:35'),
(6, 'Arctic Refresh', 'Summit Foods Ltd', 'USA', 1958, 59.3, 'https://www.arcticrefresh.com', '2026-08-27 01:46:21'),
(7, 'Sun Drinks', 'Blue Mountain Holdings', 'Japan', 1997, 57.28, 'https://www.sundrinks.com', '2026-12-18 09:38:10'),
(8, 'Spark Refresh', 'Blue Mountain Holdings', 'Australia', 2003, 93.72, 'https://www.sparkrefresh.com', '2022-06-27 08:33:50'),
(9, 'Spark Cola', 'HydroTaste Corp', 'India', 2005, 71.41, 'https://www.sparkcola.com', '2025-10-05 16:59:51'),
(10, 'Spark Refresh', 'Urban Sip International', 'USA', 1989, 61.02, 'https://www.sparkrefresh.com', '2024-06-21 09:04:03'),
(11, 'Citra Beverages', 'Blue Mountain Holdings', 'Australia', 1951, 73.37, 'https://www.citrabeverages.com', '2025-05-14 21:24:25'),
(12, 'Bubble Cola', 'HydroTaste Corp', 'Canada', 1996, 56.42, 'https://www.bubblecola.com', '2022-07-04 17:33:03'),
(13, 'Nova Beverages', 'HydroTaste Corp', 'Brazil', 2017, 82.82, 'https://www.novabeverages.com', '2026-05-01 08:47:52'),
(14, 'Viva Cola', 'HydroTaste Corp', 'Canada', 1958, 80.94, 'https://www.vivacola.com', '2022-07-27 04:03:30'),
(15, 'Citra Refresh', 'Urban Sip International', 'Mexico', 2004, 88.37, 'https://www.citrarefresh.com', '2025-04-14 23:07:41'),
(16, 'Nova Cola', 'HydroTaste Corp', 'Japan', 1984, 94.39, 'https://www.novacola.com', '2024-11-20 08:12:56'),
(17, 'Arctic Cola', 'Urban Sip International', 'Germany', 1997, 68.12, 'https://www.arcticcola.com', '2024-02-25 10:23:15'),
(18, 'Aero Soda', 'Summit Foods Ltd', 'India', 1999, 87.28, 'https://www.aerosoda.com', '2022-09-17 09:36:31');

