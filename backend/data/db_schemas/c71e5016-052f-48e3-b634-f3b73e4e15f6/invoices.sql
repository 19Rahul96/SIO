CREATE TABLE invoices (
	id INTEGER, 
	customer_id INTEGER, 
	total REAL, 
	status TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
);
