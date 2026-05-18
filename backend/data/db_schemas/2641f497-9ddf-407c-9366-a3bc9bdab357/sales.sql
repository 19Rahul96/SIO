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
