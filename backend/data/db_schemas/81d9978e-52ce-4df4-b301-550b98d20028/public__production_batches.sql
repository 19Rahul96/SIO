CREATE TABLE public.production_batches (
	batch_id VARCHAR(20) NOT NULL, 
	product_id VARCHAR(20), 
	plant_id VARCHAR(20), 
	production_dt DATE, 
	qty_produced INTEGER, 
	qa_status VARCHAR(50), 
	CONSTRAINT production_batches_pkey PRIMARY KEY (batch_id), 
	CONSTRAINT production_batches_plant_id_fkey FOREIGN KEY(plant_id) REFERENCES public.manufacturing_plants (plant_id), 
	CONSTRAINT production_batches_product_id_fkey FOREIGN KEY(product_id) REFERENCES public.products (product_id)
);
