CREATE TABLE public.ingredient_suppliers (
	ing_supp_id VARCHAR(20) NOT NULL, 
	ingredient_id VARCHAR(20), 
	supplier_id VARCHAR(20), 
	unit_cost NUMERIC, 
	CONSTRAINT ingredient_suppliers_pkey PRIMARY KEY (ing_supp_id), 
	CONSTRAINT ingredient_suppliers_ingredient_id_fkey FOREIGN KEY(ingredient_id) REFERENCES public.ingredients (ingredient_id), 
	CONSTRAINT ingredient_suppliers_supplier_id_fkey FOREIGN KEY(supplier_id) REFERENCES public.suppliers (supplier_id)
);
