CREATE TABLE public.shipments (
	shipment_id VARCHAR(20) NOT NULL, 
	batch_id VARCHAR(20), 
	distributor_id VARCHAR(20), 
	destination_city VARCHAR(100), 
	shipment_dt DATE, 
	delivery_status VARCHAR(50), 
	CONSTRAINT shipments_pkey PRIMARY KEY (shipment_id), 
	CONSTRAINT shipments_batch_id_fkey FOREIGN KEY(batch_id) REFERENCES public.production_batches (batch_id), 
	CONSTRAINT shipments_distributor_id_fkey FOREIGN KEY(distributor_id) REFERENCES public.distributors (distributor_id)
);
