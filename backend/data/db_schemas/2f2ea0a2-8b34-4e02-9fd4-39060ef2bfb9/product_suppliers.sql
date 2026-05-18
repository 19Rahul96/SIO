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
