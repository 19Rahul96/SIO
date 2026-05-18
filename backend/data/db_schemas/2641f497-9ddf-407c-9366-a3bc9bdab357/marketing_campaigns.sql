CREATE TABLE marketing_campaigns (
	campaign_id INTEGER, 
	brand_id INTEGER, 
	campaign_name TEXT, 
	platform TEXT, 
	target_demographic TEXT, 
	budget_usd REAL, 
	engagement_score REAL, 
	start_date TEXT, 
	end_date TEXT, 
	created_at TEXT, 
	PRIMARY KEY (campaign_id), 
	FOREIGN KEY(brand_id) REFERENCES brands (brand_id)
);
