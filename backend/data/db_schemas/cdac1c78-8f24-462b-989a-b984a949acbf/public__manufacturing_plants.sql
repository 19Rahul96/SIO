CREATE TABLE public.manufacturing_plants (
	plant_id VARCHAR(20) NOT NULL, 
	plant_nm VARCHAR(255), 
	location VARCHAR(255), 
	capacity_ltr_day INTEGER, 
	operational_since INTEGER, 
	CONSTRAINT manufacturing_plants_pkey PRIMARY KEY (plant_id)
);
