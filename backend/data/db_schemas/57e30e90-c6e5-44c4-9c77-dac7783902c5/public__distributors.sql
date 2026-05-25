CREATE TABLE public.distributors (
	distributor_id VARCHAR(20) NOT NULL, 
	dist_name VARCHAR(255), 
	region VARCHAR(100), 
	fleet_size INTEGER, 
	CONSTRAINT distributors_pkey PRIMARY KEY (distributor_id)
);
