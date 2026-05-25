CREATE TABLE public.product_ingredients (
	prod_ing_id VARCHAR(20) NOT NULL, 
	product_id VARCHAR(20), 
	ingredient_id VARCHAR(20), 
	quantity_pct NUMERIC, 
	CONSTRAINT product_ingredients_pkey PRIMARY KEY (prod_ing_id), 
	CONSTRAINT product_ingredients_ingredient_id_fkey FOREIGN KEY(ingredient_id) REFERENCES public.ingredients (ingredient_id), 
	CONSTRAINT product_ingredients_product_id_fkey FOREIGN KEY(product_id) REFERENCES public.products (product_id)
);
