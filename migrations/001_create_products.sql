CREATE TABLE products (
    id BIGSERIAL PRIMARY KEY,
    product_name TEXT NOT NULL CHECK (char_length(product_name) BETWEEN 1 AND 300),
    product_details TEXT NOT NULL CHECK (char_length(product_details) BETWEEN 1 AND 10000),
    image_url TEXT NOT NULL,
    affiliate_url TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
