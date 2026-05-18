CREATE TABLE categories (
    category_id INTEGER,
    category_name TEXT,
    caffeine_type TEXT,
    health_index REAL,
    created_at TEXT,
    PRIMARY KEY (category_id)
);

INSERT INTO categories (category_id, category_name, caffeine_type, health_index, created_at) VALUES
(1, 'Cola', 'Medium', 58.3, '2022-11-11 07:41:48'),
(2, 'Energy Drink', 'High', 44.1, '2026-03-26 04:20:15'),
(3, 'Sparkling Water', 'None', 88.6, '2023-09-14 19:41:08'),
(4, 'Soda', 'Low', 52.4, '2023-01-29 07:37:41'),
(5, 'Diet Soda', 'Low', 69.2, '2022-07-21 04:22:50'),
(6, 'Fruit Carbonated Drink', 'Low', 63.7, '2024-02-06 08:41:42');

