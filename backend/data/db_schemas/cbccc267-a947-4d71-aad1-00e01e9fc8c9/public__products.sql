CREATE TABLE public.products (
	product_id VARCHAR(20) NOT NULL, 
	prod_nm VARCHAR(255), 
	brand_id VARCHAR(20), 
	flavor_type VARCHAR(100), 
	sugar_g NUMERIC, 
	caffeine_mg NUMERIC, 
	launch_dt DATE, 
	CONSTRAINT products_pkey PRIMARY KEY (product_id), 
	CONSTRAINT products_brand_id_fkey FOREIGN KEY(brand_id) REFERENCES public.brands (brand_id)
);
