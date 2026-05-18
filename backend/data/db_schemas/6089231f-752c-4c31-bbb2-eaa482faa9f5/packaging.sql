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
