CREATE TABLE public.brands (
	brand_id VARCHAR(20) NOT NULL, 
	brand_nm VARCHAR(255), 
	headquarters VARCHAR(255), 
	founded_yr INTEGER, 
	market_segment VARCHAR(100), 
	CONSTRAINT brands_pkey PRIMARY KEY (brand_id)
);
