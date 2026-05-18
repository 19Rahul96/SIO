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
