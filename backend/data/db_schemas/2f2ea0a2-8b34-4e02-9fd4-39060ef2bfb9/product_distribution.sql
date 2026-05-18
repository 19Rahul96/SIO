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
