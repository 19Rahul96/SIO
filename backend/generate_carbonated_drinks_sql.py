from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

SEED = 20260514
BASE_DIR = Path("data/db_data/carbonated_drinks")


def sql_escape(value: str) -> str:
    return value.replace("'", "''")


def sql_value(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return f"'{sql_escape(str(value))}'"


def write_table_sql(
    table_name: str,
    create_statement: str,
    columns: list[str],
    rows: Iterable[tuple],
    chunk_size: int = 500,
) -> None:
    path = BASE_DIR / f"{table_name}.sql"
    with path.open("w", encoding="utf-8") as f:
        f.write(create_statement.strip() + "\n\n")
        batch: list[tuple] = []

        for row in rows:
            batch.append(row)
            if len(batch) >= chunk_size:
                _flush_insert_batch(f, table_name, columns, batch)
                batch.clear()

        if batch:
            _flush_insert_batch(f, table_name, columns, batch)


def _flush_insert_batch(file_obj, table_name: str, columns: list[str], rows: list[tuple]) -> None:
    columns_sql = ", ".join(columns)
    file_obj.write(f"INSERT INTO {table_name} ({columns_sql}) VALUES\n")
    lines = []
    for row in rows:
        values_sql = ", ".join(sql_value(v) for v in row)
        lines.append(f"({values_sql})")
    file_obj.write(",\n".join(lines))
    file_obj.write(";\n\n")


def random_timestamp(start_year: int = 2022, end_year: int = 2026) -> str:
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31, 23, 59, 59)
    delta = end - start
    second_offset = random.randint(0, int(delta.total_seconds()))
    return (start + timedelta(seconds=second_offset)).strftime("%Y-%m-%d %H:%M:%S")


def random_date(start_year: int = 2023, end_year: int = 2026) -> str:
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta_days = (end - start).days
    return (start + timedelta(days=random.randint(0, delta_days))).strftime("%Y-%m-%d")


def main() -> None:
    random.seed(SEED)
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    countries = [
        "USA",
        "Canada",
        "UK",
        "Germany",
        "France",
        "India",
        "Japan",
        "Brazil",
        "Australia",
        "Mexico",
    ]
    regions = [
        "North America",
        "Europe",
        "South Asia",
        "East Asia",
        "South America",
        "Oceania",
    ]

    # 1) brands
    brand_prefixes = [
        "Fizz",
        "Spark",
        "Bubble",
        "Aero",
        "Viva",
        "Nova",
        "Pulse",
        "Arctic",
        "Citra",
        "River",
        "Peak",
        "Sun",
    ]
    brand_suffixes = [
        "Cola",
        "Soda",
        "Drinks",
        "Beverages",
        "Refresh",
        "Sparkle",
    ]
    parent_companies = [
        "Global Beverage Group",
        "Blue Mountain Holdings",
        "Urban Sip International",
        "Summit Foods Ltd",
        "HydroTaste Corp",
    ]

    brands_rows = []
    brand_count = 18
    for i in range(1, brand_count + 1):
        brand_name = f"{random.choice(brand_prefixes)} {random.choice(brand_suffixes)}"
        brands_rows.append(
            (
                i,
                brand_name,
                random.choice(parent_companies),
                random.choice(countries),
                random.randint(1950, 2020),
                round(random.uniform(55, 96), 2),
                f"https://www.{brand_name.lower().replace(' ', '')}.com",
                random_timestamp(),
            )
        )

    brands_ddl = """
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
"""
    write_table_sql(
        "brands",
        brands_ddl,
        [
            "brand_id",
            "brand_name",
            "parent_company",
            "headquarters_country",
            "founded_year",
            "sustainability_score",
            "website",
            "created_at",
        ],
        brands_rows,
    )

    # 2) categories
    categories = [
        (1, "Cola", "Medium", 58.3),
        (2, "Energy Drink", "High", 44.1),
        (3, "Sparkling Water", "None", 88.6),
        (4, "Soda", "Low", 52.4),
        (5, "Diet Soda", "Low", 69.2),
        (6, "Fruit Carbonated Drink", "Low", 63.7),
    ]
    categories_rows = [
        (cid, name, caffeine, health_index, random_timestamp())
        for cid, name, caffeine, health_index in categories
    ]

    categories_ddl = """
CREATE TABLE categories (
    category_id INTEGER,
    category_name TEXT,
    caffeine_type TEXT,
    health_index REAL,
    created_at TEXT,
    PRIMARY KEY (category_id)
);
"""
    write_table_sql(
        "categories",
        categories_ddl,
        ["category_id", "category_name", "caffeine_type", "health_index", "created_at"],
        categories_rows,
    )

    # 3) products
    flavors = [
        "Classic Cola",
        "Lemon Lime",
        "Orange Zest",
        "Berry Blast",
        "Mango Twist",
        "Ginger Spice",
        "Vanilla Cream",
        "Cherry Pop",
        "Green Apple",
        "Tropical Mix",
    ]
    sweetener_types = ["Sugar", "Stevia", "Sucralose", "Aspartame", "Monk Fruit"]
    ingredient_strings = [
        "Carbonated Water, Sugar, Natural Flavor",
        "Carbonated Water, Citric Acid, Natural Flavor",
        "Carbonated Water, Sweetener Blend, Caffeine",
        "Carbonated Water, Fruit Concentrate, Vitamin C",
    ]
    preservative_strings = [
        "Potassium Sorbate",
        "Sodium Benzoate",
        "Citric Acid",
        "None",
    ]

    products_rows = []
    product_count = 50
    for pid in range(1, product_count + 1):
        brand_id = random.randint(1, brand_count)
        category_id = random.randint(1, len(categories))
        product_name = f"{brands_rows[brand_id - 1][1]} {random.choice(flavors)}"
        products_rows.append(
            (
                pid,
                brand_id,
                category_id,
                product_name,
                random.choice(flavors),
                random.randint(2005, 2026),
                round(random.uniform(2.5, 5.0), 2),
                round(random.uniform(0, 14), 2),
                round(random.uniform(0, 180), 2),
                random.randint(0, 260),
                random.choice(sweetener_types),
                random.choice(ingredient_strings),
                random.choice(preservative_strings),
                random.choice([0, 1]),
                random.choice([0, 1]),
                random.choice([250, 330, 355, 500, 750, 1000, 1500, 2000]),
                random.randint(120, 540),
                random_timestamp(),
            )
        )

    products_ddl = """
CREATE TABLE products (
    product_id INTEGER,
    brand_id INTEGER,
    category_id INTEGER,
    product_name TEXT,
    flavor TEXT,
    launch_year INTEGER,
    carbonation_level REAL,
    sugar_g REAL,
    caffeine_mg REAL,
    calories INTEGER,
    sweetener_type TEXT,
    ingredients TEXT,
    preservatives TEXT,
    vegan_friendly INTEGER,
    organic_certified INTEGER,
    package_size_ml INTEGER,
    shelf_life_days INTEGER,
    created_at TEXT,
    PRIMARY KEY (product_id),
    FOREIGN KEY(brand_id) REFERENCES brands (brand_id),
    FOREIGN KEY(category_id) REFERENCES categories (category_id)
);
"""
    write_table_sql(
        "products",
        products_ddl,
        [
            "product_id",
            "brand_id",
            "category_id",
            "product_name",
            "flavor",
            "launch_year",
            "carbonation_level",
            "sugar_g",
            "caffeine_mg",
            "calories",
            "sweetener_type",
            "ingredients",
            "preservatives",
            "vegan_friendly",
            "organic_certified",
            "package_size_ml",
            "shelf_life_days",
            "created_at",
        ],
        products_rows,
    )

    # 4) packaging
    package_types = ["Can", "Bottle", "Glass Bottle", "PET Bottle"]
    material_types = ["Aluminum", "Glass", "PET", "Recycled PET"]
    packaging_rows = []
    for package_id in range(1, product_count + 1):
        packaging_rows.append(
            (
                package_id,
                package_id,
                random.choice(package_types),
                random.choice([0, 1]),
                random.choice(material_types),
                round(random.uniform(10, 65), 2),
                f"{random.randint(700000000000, 999999999999)}",
                random_timestamp(),
            )
        )

    packaging_ddl = """
CREATE TABLE packaging (
    package_id INTEGER,
    product_id INTEGER,
    package_type TEXT,
    recyclable INTEGER,
    material_type TEXT,
    weight_g REAL,
    barcode TEXT,
    created_at TEXT,
    PRIMARY KEY (package_id),
    FOREIGN KEY(product_id) REFERENCES products (product_id)
);
"""
    write_table_sql(
        "packaging",
        packaging_ddl,
        [
            "package_id",
            "product_id",
            "package_type",
            "recyclable",
            "material_type",
            "weight_g",
            "barcode",
            "created_at",
        ],
        packaging_rows,
    )

    # 5) distributors
    distributors_rows = []
    distributor_count = 50
    for did in range(1, distributor_count + 1):
        distributors_rows.append(
            (
                did,
                f"Distribution Hub {did}",
                random.choice(countries),
                random.choice(regions),
                random.randint(5000, 150000),
                round(random.uniform(60, 98), 2),
                random_timestamp(),
            )
        )

    distributors_ddl = """
CREATE TABLE distributors (
    distributor_id INTEGER,
    distributor_name TEXT,
    country TEXT,
    region TEXT,
    warehouse_capacity INTEGER,
    delivery_network_score REAL,
    created_at TEXT,
    PRIMARY KEY (distributor_id)
);
"""
    write_table_sql(
        "distributors",
        distributors_ddl,
        [
            "distributor_id",
            "distributor_name",
            "country",
            "region",
            "warehouse_capacity",
            "delivery_network_score",
            "created_at",
        ],
        distributors_rows,
    )

    # 6) retailers
    retailer_types = ["Supermarket", "Convenience Store", "Online Retail"]
    retailers_rows = []
    retailer_count = 50
    for rid in range(1, retailer_count + 1):
        r_type = random.choice(retailer_types)
        retailers_rows.append(
            (
                rid,
                f"{r_type} Outlet {rid}",
                r_type,
                random.choice(countries),
                random.choice(regions),
                round(random.uniform(1_000_000, 250_000_000), 2),
                random_timestamp(),
            )
        )

    retailers_ddl = """
CREATE TABLE retailers (
    retailer_id INTEGER,
    retailer_name TEXT,
    retailer_type TEXT,
    country TEXT,
    region TEXT,
    annual_revenue REAL,
    created_at TEXT,
    PRIMARY KEY (retailer_id)
);
"""
    write_table_sql(
        "retailers",
        retailers_ddl,
        [
            "retailer_id",
            "retailer_name",
            "retailer_type",
            "country",
            "region",
            "annual_revenue",
            "created_at",
        ],
        retailers_rows,
    )

    # 7) product_distribution
    product_distribution_rows = []
    distribution_count = 50
    for dist_id in range(1, distribution_count + 1):
        product_distribution_rows.append(
            (
                dist_id,
                random.randint(1, product_count),
                random.randint(1, distributor_count),
                random.randint(1, retailer_count),
                random.choice(regions),
                random.randint(100, 20000),
                round(random.uniform(25, 12000), 2),
                random_timestamp(),
            )
        )

    product_distribution_ddl = """
CREATE TABLE product_distribution (
    distribution_id INTEGER,
    product_id INTEGER,
    distributor_id INTEGER,
    retailer_id INTEGER,
    region TEXT,
    monthly_volume INTEGER,
    logistics_cost REAL,
    created_at TEXT,
    PRIMARY KEY (distribution_id),
    FOREIGN KEY(product_id) REFERENCES products (product_id),
    FOREIGN KEY(distributor_id) REFERENCES distributors (distributor_id),
    FOREIGN KEY(retailer_id) REFERENCES retailers (retailer_id)
);
"""
    write_table_sql(
        "product_distribution",
        product_distribution_ddl,
        [
            "distribution_id",
            "product_id",
            "distributor_id",
            "retailer_id",
            "region",
            "monthly_volume",
            "logistics_cost",
            "created_at",
        ],
        product_distribution_rows,
    )

    # 8) sales (>= 50K rows)
    sales_rows = []
    sales_count = 50
    for sid in range(1, sales_count + 1):
        units = random.randint(1, 420)
        unit_price = round(random.uniform(0.8, 3.5), 2)
        discount = round(random.uniform(0, 35), 2)
        gross = units * unit_price
        revenue = round(gross * (1 - discount / 100), 2)
        sales_rows.append(
            (
                sid,
                random.randint(1, product_count),
                random.randint(1, retailer_count),
                random_date(),
                units,
                revenue,
                discount,
                round(random.uniform(1.0, 5.0), 2),
                random_timestamp(),
            )
        )

    sales_ddl = """
CREATE TABLE sales (
    sale_id INTEGER,
    product_id INTEGER,
    retailer_id INTEGER,
    sale_date TEXT,
    units_sold INTEGER,
    revenue REAL,
    discount_percentage REAL,
    customer_rating REAL,
    created_at TEXT,
    PRIMARY KEY (sale_id),
    FOREIGN KEY(product_id) REFERENCES products (product_id),
    FOREIGN KEY(retailer_id) REFERENCES retailers (retailer_id)
);
"""
    write_table_sql(
        "sales",
        sales_ddl,
        [
            "sale_id",
            "product_id",
            "retailer_id",
            "sale_date",
            "units_sold",
            "revenue",
            "discount_percentage",
            "customer_rating",
            "created_at",
        ],
        sales_rows,
        chunk_size=1000,
    )

    # 9) customers
    age_groups = ["18-24", "25-34", "35-44", "45-54", "55+"]
    genders = ["Female", "Male", "Non-binary"]
    category_names = [c[1] for c in categories]

    customers_rows = []
    customer_count = 50
    for cid in range(1, customer_count + 1):
        customers_rows.append(
            (
                cid,
                random.choice(age_groups),
                random.choice(genders),
                random.choice(countries),
                random.choice(category_names),
                round(random.uniform(15, 98), 2),
                random_timestamp(),
            )
        )

    customers_ddl = """
CREATE TABLE customers (
    customer_id INTEGER,
    age_group TEXT,
    gender TEXT,
    country TEXT,
    preferred_category TEXT,
    health_conscious_score REAL,
    created_at TEXT,
    PRIMARY KEY (customer_id)
);
"""
    write_table_sql(
        "customers",
        customers_ddl,
        [
            "customer_id",
            "age_group",
            "gender",
            "country",
            "preferred_category",
            "health_conscious_score",
            "created_at",
        ],
        customers_rows,
    )

    # 10) customer_reviews
    review_titles = [
        "Great taste",
        "Too sweet",
        "Perfect fizz",
        "Surprisingly refreshing",
        "Could be better",
        "My new favorite",
        "Good value",
        "Not for me",
    ]
    positive_phrases = [
        "balanced flavor and crisp carbonation",
        "clean finish with refreshing aftertaste",
        "great companion for meals",
        "consistent quality across batches",
        "light and enjoyable for daily use",
    ]
    negative_phrases = [
        "a bit too sugary for my preference",
        "carbonation fades quickly after opening",
        "aftertaste felt slightly artificial",
        "flavor profile was flatter than expected",
        "price feels high for the portion",
    ]

    def build_review_text(sentiment: float) -> str:
        if sentiment >= 0.2:
            return (
                f"I liked this drink because it has {random.choice(positive_phrases)}. "
                f"The aroma was pleasant and I would buy it again."
            )
        if sentiment <= -0.2:
            return (
                f"The drink was okay, but {random.choice(negative_phrases)}. "
                f"I might try another flavor next time."
            )
        return (
            "The drink is average overall. Carbonation and sweetness are acceptable, "
            "but it depends on personal preference."
        )

    customer_reviews_rows = []
    review_count = 50
    for rid in range(1, review_count + 1):
        sentiment = round(random.uniform(-1, 1), 2)
        rating = max(1, min(5, int(round((sentiment + 1) * 2.2))))
        customer_reviews_rows.append(
            (
                rid,
                random.randint(1, customer_count),
                random.randint(1, product_count),
                random.choice(review_titles),
                build_review_text(sentiment),
                sentiment,
                rating,
                random_date(),
                random_timestamp(),
            )
        )

    customer_reviews_ddl = """
CREATE TABLE customer_reviews (
    review_id INTEGER,
    customer_id INTEGER,
    product_id INTEGER,
    review_title TEXT,
    review_text TEXT,
    sentiment_score REAL,
    rating INTEGER,
    review_date TEXT,
    created_at TEXT,
    PRIMARY KEY (review_id),
    FOREIGN KEY(customer_id) REFERENCES customers (customer_id),
    FOREIGN KEY(product_id) REFERENCES products (product_id)
);
"""
    write_table_sql(
        "customer_reviews",
        customer_reviews_ddl,
        [
            "review_id",
            "customer_id",
            "product_id",
            "review_title",
            "review_text",
            "sentiment_score",
            "rating",
            "review_date",
            "created_at",
        ],
        customer_reviews_rows,
    )

    # 11) marketing_campaigns
    campaign_platforms = ["Instagram", "YouTube", "TikTok", "TV", "In-Store", "Search Ads"]
    demographics = [
        "Teens",
        "Young Adults",
        "Fitness Enthusiasts",
        "Families",
        "Office Professionals",
        "Students",
    ]

    marketing_rows = []
    campaign_count = 50
    for campaign_id in range(1, campaign_count + 1):
        start_date = datetime.strptime(random_date(2023, 2026), "%Y-%m-%d")
        end_date = start_date + timedelta(days=random.randint(14, 120))
        marketing_rows.append(
            (
                campaign_id,
                random.randint(1, brand_count),
                f"Campaign {campaign_id}",
                random.choice(campaign_platforms),
                random.choice(demographics),
                round(random.uniform(10_000, 2_500_000), 2),
                round(random.uniform(15, 98), 2),
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                random_timestamp(),
            )
        )

    marketing_campaigns_ddl = """
CREATE TABLE marketing_campaigns (
    campaign_id INTEGER,
    brand_id INTEGER,
    campaign_name TEXT,
    platform TEXT,
    target_demographic TEXT,
    budget_usd REAL,
    engagement_score REAL,
    start_date TEXT,
    end_date TEXT,
    created_at TEXT,
    PRIMARY KEY (campaign_id),
    FOREIGN KEY(brand_id) REFERENCES brands (brand_id)
);
"""
    write_table_sql(
        "marketing_campaigns",
        marketing_campaigns_ddl,
        [
            "campaign_id",
            "brand_id",
            "campaign_name",
            "platform",
            "target_demographic",
            "budget_usd",
            "engagement_score",
            "start_date",
            "end_date",
            "created_at",
        ],
        marketing_rows,
    )

    # 12) suppliers
    ingredient_types = [
        "Sweetener",
        "Natural Flavor",
        "Acidulant",
        "Coloring",
        "Preservative",
        "Carbonation Gas",
        "Botanical Extract",
    ]

    suppliers_rows = []
    supplier_count = 50
    for sid in range(1, supplier_count + 1):
        suppliers_rows.append(
            (
                sid,
                f"Supplier {sid}",
                random.choice(ingredient_types),
                random.choice(countries),
                round(random.uniform(45, 99), 2),
                random_timestamp(),
            )
        )

    suppliers_ddl = """
CREATE TABLE suppliers (
    supplier_id INTEGER,
    supplier_name TEXT,
    ingredient_type TEXT,
    country TEXT,
    sustainability_rating REAL,
    created_at TEXT,
    PRIMARY KEY (supplier_id)
);
"""
    write_table_sql(
        "suppliers",
        suppliers_ddl,
        [
            "supplier_id",
            "supplier_name",
            "ingredient_type",
            "country",
            "sustainability_rating",
            "created_at",
        ],
        suppliers_rows,
    )

    # 13) product_suppliers
    ingredient_names = [
        "Carbonated Water",
        "Cane Sugar",
        "High Fructose Syrup",
        "Citric Acid",
        "Natural Cola Flavor",
        "Caffeine",
        "Stevia Extract",
        "Caramel Color",
        "Sodium Benzoate",
        "Potassium Sorbate",
        "Fruit Essence",
    ]

    product_suppliers_rows = []
    mapping_count = 50
    for mid in range(1, mapping_count + 1):
        product_suppliers_rows.append(
            (
                mid,
                random.randint(1, product_count),
                random.randint(1, supplier_count),
                random.choice(ingredient_names),
                round(random.uniform(0.05, 3.75), 3),
                random_timestamp(),
            )
        )

    product_suppliers_ddl = """
CREATE TABLE product_suppliers (
    mapping_id INTEGER,
    product_id INTEGER,
    supplier_id INTEGER,
    ingredient_name TEXT,
    supply_cost REAL,
    created_at TEXT,
    PRIMARY KEY (mapping_id),
    FOREIGN KEY(product_id) REFERENCES products (product_id),
    FOREIGN KEY(supplier_id) REFERENCES suppliers (supplier_id)
);
"""
    write_table_sql(
        "product_suppliers",
        product_suppliers_ddl,
        [
            "mapping_id",
            "product_id",
            "supplier_id",
            "ingredient_name",
            "supply_cost",
            "created_at",
        ],
        product_suppliers_rows,
    )

    print(f"Generated 13 table SQL files in {BASE_DIR}")
    print(f"Sales rows generated: {sales_count}")


if __name__ == "__main__":
    main()
