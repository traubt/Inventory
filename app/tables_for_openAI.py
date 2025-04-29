
# ===============================
# Static Database Schema for AI (used in prompt)
# ===============================
DATABASE_SCHEMA ='''
Tables:
- toc_product (
    item_sku VARCHAR(45) PRIMARY KEY,
    item_name VARCHAR(200),
    stat_group VARCHAR(45),
    acct_group VARCHAR(45),
    retail_price FLOAT,
    cost_price FLOAT,
    wh_price FLOAT,
    cann_cost_price FLOAT,
    product_url VARCHAR(200),
    image_url VARCHAR(200),
    stock_ord_ind INT,
    creation_date DATETIME,
    update_date DATETIME
)

- toc_shops (
    blName VARCHAR(255) PRIMARY KEY,        -- Shop name (unique ID)
    blId BIGINT,                             -- Business location ID
    country VARCHAR(2),                      -- Country code (e.g., ZA for South Africa)
    timezone VARCHAR(50),                    -- Timezone string
    store VARCHAR(10),                       -- Store code
    customer VARCHAR(10),                    -- Customer code
    mt_shop_name VARCHAR(45),                 -- MT shop name (alternate or marketing name)
    actv_ind INT DEFAULT 1,                   -- Active indicator (1 = Active, 0 = Inactive)
    tier VARCHAR(2),                          -- Store tier/level
    longitude VARCHAR(20),                    -- Store longitude (GPS)
    latitude VARCHAR(20)                      -- Store latitude (GPS)
)

- toc_ls_sales (
    sales_id VARCHAR(45) PRIMARY KEY,          -- Unique sale transaction ID
    creation_date DATETIME,                    -- Date record was created
    channel VARCHAR(3),                        -- Sales channel (POS, WEB, etc.)
    store_ls_code VARCHAR(45),                  -- LightSpeed store code
    store_name VARCHAR(45),                     -- Store name
    store_customer VARCHAR(10),                 -- Store customer code
    store_code VARCHAR(10),                     -- Store internal code
    time_of_sale DATETIME,                      -- Actual time of sale
    quantity INT,                               -- Quantity sold
    device_id VARCHAR(10),                      -- POS device ID
    device_name VARCHAR(45),                    -- POS device name
    owner_name VARCHAR(45),                     -- Name of sales owner (cashier/salesperson)
    owner_id INT,                               -- ID of the owner/cashier
    status VARCHAR(20)                          -- Status of sale (Completed, Voided, etc.)
)

- toc_ls_sales_item (
    salesline_id VARCHAR(45) PRIMARY KEY,           -- Unique sales line item ID
    creation_date DATETIME,                         -- When this sales line was created
    sales_id VARCHAR(45),                           -- Foreign key to toc_ls_sales.sales_id
    time_of_sale DATETIME,                          -- Actual time of sale
    item_name VARCHAR(100),                         -- Name of the product sold
    item_sku VARCHAR(20),                           -- SKU code of the product
    quantity FLOAT,                                 -- Quantity sold in this line
    tot_amt FLOAT,                                  -- Total amount (gross)
    net_amt FLOAT,                                  -- Net amount (after discounts)
    tax_amt FLOAT,                                  -- Tax amount applied
    discount_amt FLOAT,                             -- Discount amount applied
    unit_cost_price FLOAT,                          -- Cost price per unit
    service_charge FLOAT,                           -- Additional service charge (if any)
    tax_rate FLOAT,                                 -- Tax rate applied
    stat_group VARCHAR(45),                         -- Statistical group (business category?)
    acct_group VARCHAR(45),                         -- Accounting group
    device_id INT,                                  -- Device ID used for sale
    device_name VARCHAR(45),                        -- Device name used
    staff_id INT,                                   -- Staff member ID who sold item
    staff_name VARCHAR(45)                          -- Staff member name
)

- toc_wc_sales_order (
    order_id INT PRIMARY KEY,                 -- Unique WooCommerce order ID
    creation_date DATETIME,                    -- When record was created in the database
    order_date DATETIME,                       -- Date when order was placed
    total_amount FLOAT,                        -- Total amount for the order
    discount_amount FLOAT,                     -- Total discount applied
    shipping_amount FLOAT,                     -- Shipping cost
    customer_id INT,                           -- Customer ID (internal reference)
    customer_name VARCHAR(100),                 -- Customer full name
    customer_email VARCHAR(100),                -- Customer email address
    customer_phone VARCHAR(15),                 -- Customer phone number
    status VARCHAR(20),                         -- Order status (e.g., completed, pending, refunded)
    mt_status INT                               -- -- Member Track push status (0 = Not pushed, 1 = Successfully pushed)
)

- toc_wc_sales_items (
    sales_id INT PRIMARY KEY,                -- Unique sales line item ID
    creation_date DATETIME,                   -- When this sales item was recorded
    product_name VARCHAR(100),                 -- Name of the product sold
    sku VARCHAR(45),                           -- SKU code of the product
    quantity FLOAT,                            -- Quantity sold of the product
    total_amount FLOAT,                        -- Total price for this item line
    order_id INT                               -- Foreign key to toc_wc_sales_order.order_id
)

- toc_ls_payments (
    payment_id VARCHAR(45) PRIMARY KEY,        -- Unique payment transaction ID
    creation_date DATETIME,                    -- When payment record was created
    sales_id VARCHAR(45),                      -- Foreign key to toc_ls_sales.sales_id (sale the payment relates to)
    payment_date DATETIME,                     -- Date of payment
    payment_amount FLOAT,                      -- Amount paid
    email VARCHAR(100),                        -- Customer email address
    mt_status INT                              -- Member Track push status (0 = Not pushed, 1 = Successfully pushed)
)






'''
