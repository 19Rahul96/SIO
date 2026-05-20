CREATE TABLE public.suppliers (
	supplier_id VARCHAR(20) NOT NULL, 
	supp_nm VARCHAR(255), 
	country VARCHAR(100), 
	certification VARCHAR(100), 
	reliability_score NUMERIC, 
	CONSTRAINT suppliers_pkey PRIMARY KEY (supplier_id)
);
