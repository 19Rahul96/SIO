CREATE TABLE public.ingredients (
	ingredient_id VARCHAR(20) NOT NULL, 
	ing_name VARCHAR(255), 
	category VARCHAR(100), 
	allergen_flag VARCHAR(10), 
	organic_flag VARCHAR(10), 
	CONSTRAINT ingredients_pkey PRIMARY KEY (ingredient_id)
);
