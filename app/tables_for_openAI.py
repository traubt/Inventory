
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

- toc_wc_sales_order (                        -- table shows the online sales in WooCommerce
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

- toc_wc_sales_items (                       -- table shows the online sales items in WooCommerce
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

- toc_stock (
    shop_id VARCHAR(20) PRIMARY KEY,          -- Shop ID (part of composite key)
    sku VARCHAR(45) PRIMARY KEY,               -- Product SKU (part of composite key)
    stock_qty_date DATETIME,                   -- Date when stock was counted
    product_name VARCHAR(100),                 -- Name of the product
    stock_count DOUBLE,                        -- Stock quantity physically counted
    count_by VARCHAR(45),                      -- Staff who counted stock
    last_stock_qty DOUBLE,                     -- Previous stock quantity
    calc_stock_qty DOUBLE,                     -- System calculated stock quantity
    variance DOUBLE DEFAULT 0,                 -- Difference between counted and system stock
    variance_rsn VARCHAR(45),                  -- Reason for variance
    stock_transfer DOUBLE DEFAULT 0,           -- Quantity transferred between shops
    shop_name VARCHAR(45),                     -- Shop Name (redundant sometimes)
    rejects_qty DOUBLE,                        -- Rejected (bad quality) quantity
    final_stock_qty DOUBLE,                    -- Final stock after adjustments
    replenish_id VARCHAR(45),                  -- Replenishment ID
    comments VARCHAR(150),                     -- Additional comments
    pastel_ind INT DEFAULT -1,                  -- Sync indicator with Pastel accounting
    pastel_count DOUBLE,                       -- Pastel system stock count
    pastel_date DATETIME,                      -- Date of pastel record
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP -- Record creation date
)

- toc_replenish_ctrl (
    order_id VARCHAR(45) PRIMARY KEY,         -- Unique replenish order ID
    shop_id VARCHAR(45),                      -- Shop ID placing the order
    order_open_date DATETIME,                  -- Date the order was opened
    user VARCHAR(45),                          -- User who created the order
    order_status VARCHAR(45),                  -- Current status of the order (e.g., pending, sent, received)
    order_status_date DATETIME,                -- Last status change date
    tracking_code VARCHAR(45),                 -- Tracking code for shipment
    sold_qty INT,                              -- parameter holds number of days which an item/product sold during the past days
    replenish_qty INT,                         -- second parameter holds number of days which an item/product sold during the past days
    sent_from VARCHAR(45)                      -- Origin location/shop sending the stock
)

- toc_replenish_order (
    shop_id VARCHAR(45) PRIMARY KEY,           -- Shop placing the order (part of composite key)
    order_id VARCHAR(45) PRIMARY KEY,           -- Replenishment order ID (part of composite key). Foreign key to toc_replenish_ctrl.order_id
    sku VARCHAR(45) PRIMARY KEY,                -- Product SKU (part of composite key)
    order_open_date DATETIME,                   -- When the order was opened
    user VARCHAR(45),                           -- User who opened the order
    item_name VARCHAR(100),                     -- Name of the product ordered
    replenish_qty DOUBLE,                       -- Quantity requested to replenish
    comments VARCHAR(100),                      -- Comments by the user
    received_qty DOUBLE,                        -- Quantity actually received
    rejected_qty DOUBLE,                        -- Quantity rejected upon receipt
    variance DOUBLE,                            -- Difference between ordered and received
    received_date DATETIME,                     -- Date items were received
    received_by VARCHAR(45),                    -- Staff who received the items
    received_comment VARCHAR(100),              -- Comments upon receipt
    pastel_ind INT DEFAULT 0,                   -- Indicator if synced to Pastel accounting system
    save_count DOUBLE DEFAULT 0,                -- Counter for save/submit operations
    pastel_date DATETIME                        -- Date synced with Pastel
)

- toc_stock_order (
    shop_id VARCHAR(45) PRIMARY KEY,           -- Shop placing order from the head quarter
    order_open_date DATETIME PRIMARY KEY,       -- Date when the order was opened (part of composite key)
    sku VARCHAR(45) PRIMARY KEY,                -- Product SKU (part of composite key)
    order_id VARCHAR(45),                       -- Optional unique identifier for the order
    user VARCHAR(45),                           -- User who created the order
    item_name VARCHAR(100),                     -- Product name
    order_qty DOUBLE,                           -- Quantity ordered
    comments VARCHAR(100),                      -- Additional comments
    order_status VARCHAR(45),                   -- Status of the order (pending, sent, received)
    order_status_date DATETIME                  -- Last status update date
)



- toc_stock_variance (
    id INT PRIMARY KEY AUTO_INCREMENT,         -- Unique variance record ID
    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP,  -- When the variance was recorded
    shop_id VARCHAR(20),                        -- Shop where variance was found
    sku VARCHAR(45),                            -- Product SKU
    stock_qty_date DATETIME,                    -- Date of stock count
    product_name VARCHAR(100),                  -- Product name
    stock_count DOUBLE,                         -- Counted stock quantity
    count_by VARCHAR(45),                       -- Staff who counted
    last_stock_qty DOUBLE,                      -- Previous stock recorded
    calc_stock_qty DOUBLE,                      -- Calculated stock quantity
    variance DOUBLE DEFAULT 0,                  -- Difference (counted - calculated)
    stock_recount DOUBLE,                       -- Recounted stock if variance exists
    shop_name VARCHAR(45),                      -- Shop Name
    rejects_qty DOUBLE,                         -- Quantity rejected (damaged, etc.)
    final_stock_qty DOUBLE,                     -- Final stock quantity after adjustments
    replenish_id VARCHAR(45),                   -- Related replenish order ID if any
    comments VARCHAR(150)                       -- Additional notes
)






'''
