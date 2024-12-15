import pymysql
import json
from flask import session

# Database connection details
db_config = {
    'host': '176.58.117.107',
    'user': 'tasteofc_wp268',
    'password': ']44p7214)S',
    'database': 'tasteofc_wp268'
}

def get_db_connection():
    return pymysql.connect(**db_config)

def get_top_items():
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT item_name, SUM(net_amt) AS total_amount
    FROM toc_ls_sales_item
    WHERE time_of_sale >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
    GROUP BY item_name
    ORDER BY total_amount DESC
    LIMIT 5;
    """
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results


def get_sales_summary():
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to get the sales summary
    cursor.execute("SELECT * FROM toc_sales_summary")
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

def get_sales_data_for_lineChart():
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()
    # Query to get the sales data
    query = """
    SELECT ts.time_of_sale, SUM(tsi.net_amt)
    FROM toc_ls_sales ts
    JOIN toc_ls_sales_item tsi ON ts.sales_id = tsi.sales_id
    WHERE ts.store_name = 'TOC - Sandton City'
    AND ts.time_of_sale > '2024-11-08'
    GROUP BY ts.time_of_sale
    ORDER BY ts.time_of_sale;
    """
    cursor.execute(query)
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    # Format the result as a list of dictionaries
    data = [{"time_of_sale": row[0], "total_sales": row[1]} for row in result]
    return data

# db_queries.py
def get_recent_sales(shop_name):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    if shop_name == "Head Office":
        query = '''
            SELECT 
                s.sales_id,
                CONCAT(m.first_name, ' ', m.last_name) AS customer,
                i.item_name as product,
                i.net_amt as price,
                s.time_of_sale,
                s.store_name
            FROM 
                toc_ls_sales s
            JOIN 
                toc_ls_sales_item i ON s.sales_id = i.sales_id
            JOIN 
                toc_ls_payments p ON s.sales_id = p.sales_id
            JOIN 
                toc_canna_member m ON p.email = m.email 
            ORDER BY 
                s.time_of_sale DESC
            LIMIT 100;
        '''
        cursor.execute(query)
    else:
        query = '''
            SELECT 
                s.sales_id,
                CONCAT(m.first_name, ' ', m.last_name) AS customer,
                i.item_name as product,
                i.net_amt as price,
                s.time_of_sale,
                s.store_name
            FROM 
                toc_ls_sales s
            JOIN 
                toc_ls_sales_item i ON s.sales_id = i.sales_id
            JOIN 
                toc_ls_payments p ON s.sales_id = p.sales_id
            JOIN 
                toc_canna_member m ON p.email = m.email 
            WHERE 
                s.store_name = %s
            ORDER BY 
                s.time_of_sale DESC
            LIMIT 100;
        '''
        cursor.execute(query, (shop_name,))

    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result


# db_queries.py
def get_product_sales(timeframe, shop_name):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    if shop_name == "Head Office":
        query = f'''
            SELECT product_name, SUM(total_sales_{timeframe}) AS total_sales
            FROM toc_sales_summary_product
            WHERE total_sales_{timeframe} IS NOT NULL 
            GROUP BY product_name
            ORDER BY total_sales DESC
            LIMIT 5;
        '''
        cursor.execute(query)
    else:
        query = f'''
            SELECT product_name, SUM(total_sales_{timeframe}) AS total_sales
            FROM toc_sales_summary_product
            WHERE total_sales_{timeframe} IS NOT NULL AND shop_name = %s
            GROUP BY product_name
            ORDER BY total_sales DESC
            LIMIT 5;
        '''
        cursor.execute(query, (shop_name,))

    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

def get_specials_sales(timeframe, shop_name):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    if shop_name == "Head Office":
        query = f'''
            SELECT product_name, SUM(count_sales_{timeframe}) AS total_sales
            FROM toc_sales_summary_product ts
            join toc_product p ON p.item_name = ts.product_name
            WHERE count_sales_{timeframe} IS NOT NULL AND p.acct_group = 'Specials'
            GROUP BY product_name
            ORDER BY total_sales DESC
            LIMIT 10;
        '''
        cursor.execute(query)
    else:
        query = f'''
            SELECT product_name, SUM(count_sales_{timeframe}) AS total_sales
            FROM toc_sales_summary_product ts
            join toc_product p ON p.item_name = ts.product_name
            WHERE count_sales_{timeframe} IS NOT NULL AND p.acct_group = 'Specials' and ts.shop_name = %s
            GROUP BY product_name
            ORDER BY total_sales DESC
            LIMIT 10;
        '''
        cursor.execute(query, (shop_name,))

    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

def get_recent_product_sales(timeframe, shop_name):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    if shop_name == "Head Office":
        query = f'''
                SELECT 
                    p.product_name, 
                    SUM(p.count_sales_{timeframe}) AS total_count, 
                    SUM(p.total_sales_{timeframe}) AS total_sales, 
                    prod.cost_price * SUM(p.count_sales_{timeframe}) AS total_cost, 
                    (CASE 
                        WHEN SUM(p.total_sales_{timeframe}) IS NOT NULL AND prod.cost_price IS NOT NULL 
                        THEN (SUM(p.total_sales_{timeframe}) - (SUM(p.count_sales_{timeframe}) * prod.cost_price)) / SUM(p.total_sales_{timeframe}) * 100 
                        ELSE NULL 
                    END) AS gross_profit_percentage
                FROM 
                    toc_sales_summary_product p
                JOIN 
                    toc_product prod 
                ON 
                    p.product_name = prod.item_name
                WHERE 
                    p.total_sales_{timeframe} IS NOT NULL
                    and prod.acct_group <> 'Specials'
                GROUP BY 
                    p.product_name, prod.cost_price
                ORDER BY 
                    total_sales DESC;
        
        '''
        cursor.execute(query)
    else:
        query = f'''       
                SELECT 
                    p.product_name, 
                    SUM(p.count_sales_{timeframe}) AS total_count, 
                    SUM(p.total_sales_{timeframe}) AS total_sales, 
                    prod.cost_price * SUM(p.count_sales_{timeframe}) AS total_cost,
                    (CASE 
                        WHEN SUM(p.total_sales_{timeframe}) IS NOT NULL AND prod.cost_price IS NOT NULL 
                        THEN (SUM(p.total_sales_{timeframe}) - (SUM(p.count_sales_{timeframe}) * prod.cost_price)) / SUM(p.total_sales_{timeframe}) * 100 
                        ELSE NULL 
                    END) AS gross_profit_percentage
                FROM 
                    toc_sales_summary_product p
                JOIN 
                    toc_product prod 
                ON 
                    p.product_name = prod.item_name
                WHERE 
                    p.total_sales_{timeframe} IS NOT NULL and shop_name = %s
                    and prod.acct_group <> 'Specials'
                GROUP BY 
                    p.product_name, prod.cost_price
                ORDER BY 
                    total_sales DESC;           
        '''
        cursor.execute(query, (shop_name,))

    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

# db_queries.py
# db_queries.py
def get_hourly_sales(shop_name, timeframe):
    conn = get_db_connection()
    cursor = conn.cursor()
    print(f"shop_name: {shop_name}")
    print(f"time_frame: {timeframe}")

    if shop_name == "Head Office":
        if timeframe == "hourly":
            query = '''                             
                SELECT 
                    'Head Office' as store_name,
                    DATE_FORMAT(s.time_of_sale, '%Y-%m-%d %H:00') AS sale_hour, 
                    ROUND(SUM(net_amt)) AS total_amount
                FROM 
                    toc_ls_sales_item i
				JOIN
					toc_ls_sales s 
				ON i.sales_id = s.sales_id
                GROUP BY 
                    sale_hour
                ORDER BY 
                    sale_hour DESC
                LIMIT 200;
            '''
            cursor.execute(query)
        elif timeframe == "daily":
            query = '''
                SELECT 
                    'Head Office' AS store_name,
                    DATE_FORMAT(i.time_of_sale, '%Y-%m-%d') AS sale_date,
                    ROUND(SUM(net_amt)) AS total_amount
                FROM 
                    toc_ls_sales_item i
                JOIN
                    toc_ls_sales s on i.sales_id = s.sales_id
                GROUP BY 
                    DATE_FORMAT(i.time_of_sale, '%Y-%m-%d')
                ORDER BY 
                    sale_date
                limit 200;
            '''
            cursor.execute(query)
    elif shop_name == "Online":
        if timeframe == "hourly":
            query = '''                             
                SELECT 
                    'Online' AS store_name,
                    DATE_FORMAT(o.creation_date, '%Y-%m-%d %H:00') AS sale_hour, 
                    ROUND(SUM(o.total_amount / 1.15), 2) AS total_amount -- Removing 15% VAT
                FROM 
                    toc_wc_sales_order o
                GROUP BY 
                    sale_hour
                ORDER BY 
                    sale_hour DESC
                LIMIT 200;
            '''
            cursor.execute(query)
        elif timeframe == "daily":
            query = '''
                SELECT 
                    'Online' AS store_name,
                    DATE_FORMAT(o.creation_date, '%Y-%m-%d') AS sale_hour, 
                    ROUND(SUM(o.total_amount / 1.15), 2) AS total_amount -- Removing 15% VAT
                FROM 
                    toc_wc_sales_order o
                GROUP BY 
                    sale_hour
                ORDER BY 
                    sale_hour DESC
                LIMIT 200;
            '''
            cursor.execute(query)
    else:
        if timeframe == "hourly":
            query = '''
                SELECT 
                    ts.store_name,
                    DATE_FORMAT(tlsi.time_of_sale, '%%Y-%%m-%%d %%H:00') AS sale_hour,
                    ROUND(SUM(tlsi.net_amt)) AS total_amount
                FROM 
                    toc_ls_sales_item tlsi
                JOIN 
                    toc_ls_sales ts ON tlsi.sales_id = ts.sales_id
                WHERE
                    ts.store_name = %s
                GROUP BY 
                    ts.store_name, sale_hour
                ORDER BY 
                    ts.store_name, sale_hour
                limit 200;
            '''
            cursor.execute(query, (shop_name,))
        elif timeframe == "daily":
            query = '''
                SELECT 
                    ts.store_name,
                    DATE_FORMAT(tlsi.time_of_sale, '%%Y-%%m-%%d') AS sale_date,
                    ROUND(SUM(tlsi.net_amt)) AS total_amount
                FROM 
                    toc_ls_sales_item tlsi
                JOIN 
                    toc_ls_sales ts ON tlsi.sales_id = ts.sales_id
                WHERE 
                    ts.store_name = %s
                GROUP BY 
                    ts.store_name, sale_date
                ORDER BY 
                    ts.store_name, sale_date limit 200;
            
            '''
            cursor.execute(query, (shop_name,))

    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result


def get_stock_order_template():
    shop_data = json.loads(session.get('shop'))
    shop = shop_data["customer"]

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to get the sales summary
    query = '''
        SELECT 
            toc_product.item_sku AS sku,
            toc_product.item_name AS product_name,
            0 AS stock_count,
            0 AS last_stock_qty,
            0 AS calc_stock_qty,
            0 AS variance,
            'NA' AS variance_rsn,
            0 AS stock_recount,
            0 AS rejects_qty,
            'NA' AS comments
        FROM 
            toc_shops
        CROSS JOIN 
            toc_product
        WHERE 
            toc_product.acct_group <> 'Specials'
            AND toc_shops.customer = %s;
    '''

    # Execute the query with the parameter
    cursor.execute(query, (shop,))
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

def distribute_product_to_shops(sku):
    # Connect to the database
    conn = get_db_connection()  # Assuming this function is defined elsewhere to get the connection
    cursor = conn.cursor()

    # Query to insert the product into the toc_stock table for all shops
    query = '''
        INSERT INTO toc_stock (
            shop_id, sku, stock_qty_date, product_name, shop_name, final_stock_qty,
            stock_count, count_by, last_stock_qty, calc_stock_qty, variance, variance_rsn,
            stock_recount, rejects_qty, replenish_id, comments
        )
        SELECT 
            toc_shops.customer AS shop_id,
            toc_product.item_sku AS sku,
            NOW() AS stock_qty_date,
            toc_product.item_name AS product_name,
            toc_shops.blName AS shop_name,
            0 AS final_stock_qty,
            0 AS stock_count,
            'NA' AS count_by,
            0 AS last_stock_qty,
            0 AS calc_stock_qty,
            0 AS variance,
            'NA' AS variance_rsn,
            0 AS stock_recount,
            0 AS rejects_qty,
            'NA' AS replenish_id,  -- Replacing transfer_id with replenish_id
            'NA' AS comments
        FROM 
            toc_shops
        CROSS JOIN 
            toc_product
        WHERE 
            toc_product.item_sku = %s;
    '''

    try:
        # Execute the query with the sku parameter
        cursor.execute(query, (sku,))

        # Commit the transaction to save the changes to the database
        conn.commit()

    except Exception  as err:
        # Rollback in case of error
        conn.rollback()
        print(f"Error occurred: {err}")
        return {"status": "error", "message": str(err)}

    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()

    # If successful, return a success message
    return {"status": "success", "message": f"Product {sku} distributed to shops successfully."}


def get_stock_order_form():
    shop_data = json.loads(session.get('shop'))
    shop = shop_data["customer"]

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
        SELECT 
            p.item_sku AS sku,
            p.item_name AS product_name,
            0 AS stock_count,
            0 AS last_stock_qty,
            0 AS calc_stock_qty,
            0 AS variance,
            'NA' AS variance_rsn,
            0 AS stock_recount,
            COALESCE(o.order_qty, 0) AS order_qty,
            'NA' AS comments
        FROM 
            toc_shops s
        CROSS JOIN 
            toc_product p
        LEFT JOIN 
            toc_stock_order o
        ON 
            s.customer = o.shop_id 
            AND p.item_sku = o.sku
            AND o.order_status = 'New'
        WHERE 
            p.acct_group <> 'Specials'
            AND s.customer = %s
		ORDER BY order_qty desc, product_name asc;
    '''

    # Execute the query with the parameter
    cursor.execute(query, (shop,))
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

def get_replenish_order_form(shop,threshold, replenish):

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
WITH sales_data AS (
    SELECT 
        d.item_sku,
        d.item_name,
        b.store_customer,
        c.blName AS shop_name,
        COUNT(CASE WHEN a.time_of_sale > CURDATE() - INTERVAL %s DAY THEN a.sales_id END) AS threshold_sold_qty,
        COUNT(CASE WHEN a.time_of_sale > CURDATE() - INTERVAL %s DAY THEN a.sales_id END) AS replenish_qty,
        COUNT(CASE WHEN a.time_of_sale > st.stock_qty_date THEN a.sales_id END) AS sales_since_stock_read  -- Added new column
    FROM 
        toc_product d
    LEFT JOIN 
        toc_ls_sales_item a
        ON d.item_sku = a.item_sku
    LEFT JOIN 
        toc_ls_sales b 
        ON a.sales_id = b.sales_id
    LEFT JOIN 
        toc_shops c
        ON b.store_customer = c.customer
    LEFT JOIN
        toc_stock st
        ON d.item_sku = st.sku AND b.store_customer = st.shop_id  -- Joining toc_stock for stock_qty_date
    WHERE 
        d.acct_group <> 'Specials'
        AND c.blName = %s  -- Ensures we only get sales related to this shop
        and d.item_sku <> '9568' -- Refund item
    GROUP BY 
        d.item_sku, d.item_name, b.store_customer, c.blName, st.stock_qty_date  -- Group by stock_qty_date
)
SELECT 
    s.item_sku,
    s.item_name,
    s.store_customer,
    s.shop_name,
    s.threshold_sold_qty,
    s.replenish_qty,
    s.sales_since_stock_read,  -- Include the new column in the final SELECT
    st.final_stock_qty AS last_stock_update,
    st.stock_qty_date AS last_stock_update_date,
    st.final_stock_qty 
        - s.sales_since_stock_read 
        + COALESCE((
            SELECT SUM(tro.received_qty) 
            FROM toc_replenish_order tro
            WHERE tro.shop_id = s.store_customer 
              AND tro.sku = s.item_sku
              AND tro.received_date > st.stock_qty_date
        ), 0) AS current_stock_qty,  -- Updated current_stock_qty calculation
    CASE 
        WHEN st.final_stock_qty 
            - s.sales_since_stock_read 
            + COALESCE((
                SELECT SUM(tro.received_qty) 
                FROM toc_replenish_order tro
                WHERE tro.shop_id = s.store_customer 
                  AND tro.sku = s.item_sku
                  AND tro.received_date > st.stock_qty_date
            ), 0) > s.threshold_sold_qty THEN 0
        ELSE s.replenish_qty
    END AS replenish_order  -- Add the replenish_order column
FROM 
    sales_data s
LEFT JOIN 
    toc_stock st
ON 
    s.item_sku = st.sku AND s.store_customer = st.shop_id
ORDER BY  s.sales_since_stock_read DESC;
            '''

    # Execute the query with the parameter
    cursor.execute(query, (threshold, replenish,shop))
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

def get_stock_count_per_shop(shop):

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
WITH sales_data AS (
    SELECT 
        d.item_sku,
        d.item_name,
        b.store_customer,
        c.blName AS shop_name,
        st.stock_qty_date,
        COUNT(CASE WHEN a.time_of_sale > st.stock_qty_date THEN a.sales_id END) AS sales_since_stock_read
    FROM 
        toc_product d
    LEFT JOIN 
        toc_ls_sales_item a
        ON d.item_sku = a.item_sku
    LEFT JOIN 
        toc_ls_sales b 
        ON a.sales_id = b.sales_id
    LEFT JOIN 
        toc_shops c
        ON b.store_customer = c.customer
    LEFT JOIN
        toc_stock st
        ON d.item_sku = st.sku AND b.store_customer = st.shop_id
    WHERE 
        d.acct_group <> 'Specials'
        AND c.blName = %s -- Ensures we only get sales related to this shop
    GROUP BY 
        d.item_sku, d.item_name, b.store_customer, c.blName, st.stock_qty_date
)
SELECT DISTINCT
    st.sku AS item_sku,
    st.product_name AS item_name,
    st.shop_id AS store_customer,
    st.shop_name,
    st.final_stock_qty AS last_stock_count, -- Last stock count (final_stock_qty from toc_stock)
    st.stock_qty_date AS last_stock_count_date, -- Last stock count date (stock_qty_date from toc_stock)
    COALESCE(s.sales_since_stock_read, 0) AS sold_quantity, -- Sold quantity (sales_since_stock_read from sales_data, or 0 if no sales data)
    st.final_stock_qty - COALESCE(s.sales_since_stock_read, 0) AS current_quantity, -- Current quantity (last stock count - sold quantity)
    COALESCE((
        SELECT SUM(tro.received_qty) 
        FROM toc_replenish_order tro
        WHERE tro.shop_id = st.shop_id 
          AND tro.sku = st.sku
          AND tro.received_date > st.stock_qty_date
    ), 0) AS received_stock -- Received stock
FROM 
    toc_stock st
LEFT JOIN 
    sales_data s
ON 
    st.sku = s.item_sku AND st.shop_id = s.store_customer
WHERE 
    st.shop_name = %s -- Filter to include only entries for the specified shop
ORDER BY 
    COALESCE(s.sales_since_stock_read, 0) DESC
    limit 10;
            '''

    # Execute the query with the parameter
    cursor.execute(query, (shop,shop))
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

def get_receive_stock_order(shop,order_id):

    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
                select * from toc_replenish_order where shop_id = %s and order_id = %s
            '''

    # Execute the query with the parameter
    cursor.execute(query, (shop,order_id))
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

def get_sales_by_shop_last_three_months():
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to retrieve the stock order form
    query = '''
            SELECT 
                ts.store_name,
                DATE_FORMAT(tlsi.time_of_sale, '%Y-%m') AS sale_month,
                ROUND(SUM(tlsi.net_amt)) AS total_sales
            FROM 
                toc_ls_sales_item tlsi
            JOIN 
                toc_ls_sales ts ON tlsi.sales_id = ts.sales_id
            JOIN toc_shops s on ts.store_customer = s.customer
            WHERE 
                tlsi.time_of_sale >= DATE_FORMAT(CURDATE() - INTERVAL 2 MONTH, '%Y-%m-01')
                and s.actv_ind = 1
            GROUP BY 
                ts.store_name, sale_month
    union all
            SELECT 
                'Online' AS store_name,
                DATE_FORMAT(creation_date, '%Y-%m') AS sale_month, -- Grouping by creation_date
                ROUND(SUM(total_amount / 1.15)) AS total_sales -- Removing 15% VAT
            FROM 
                toc_wc_sales_order
                WHERE 
                creation_date >= DATE_FORMAT(CURDATE() - INTERVAL 2 MONTH, '%Y-%m-01')
            group by store_name,sale_month;
            '''

    # Execute the query
    cursor.execute(query)
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return result_as_dicts


def get_top_agents(shop_name, timeframe):
    conn = get_db_connection()
    cursor = conn.cursor()
    print(f"shop_name: {shop_name}")
    print(f"time_frame: {timeframe}")

    if shop_name == "Head Office":
        if timeframe == "daily":
            query = '''                             
            SELECT 
                staff_name, 
                ROUND(SUM(i.net_amt)) AS total_net_amt,
                s.store_name
            FROM 
                toc_ls_sales_item i
            JOIN 
                toc_ls_sales s ON i.sales_id = s.sales_id
            WHERE 
                i.time_of_sale >= CURDATE() - INTERVAL 1 DAY
                AND i.time_of_sale < CURDATE()
            GROUP BY 
                staff_name
            ORDER BY 
                total_net_amt DESC
            LIMIT 10;
            '''
            cursor.execute(query)
        elif timeframe == "monthly":
            query = '''
            SELECT 
                staff_name, 
                ROUND(SUM(i.net_amt)) AS total_net_amt,
                s.store_name
            FROM 
                toc_ls_sales_item i
            JOIN 
                toc_ls_sales s ON i.sales_id = s.sales_id
            WHERE 
                i.time_of_sale >= CURDATE() - INTERVAL 1 MONTH
                AND i.time_of_sale < CURDATE()
            GROUP BY 
                staff_name
            ORDER BY 
                total_net_amt DESC
            LIMIT 10;
            '''
            cursor.execute(query)
    else:
        if timeframe == "daily":
            query = '''
            SELECT 
                staff_name, 
                ROUND(SUM(i.net_amt)) AS total_net_amt,
                s.store_name
            FROM 
                toc_ls_sales_item i
            JOIN 
                toc_ls_sales s ON i.sales_id = s.sales_id
			join
				toc_shops ts on ts.blName = s.store_name
            WHERE 
                i.time_of_sale >= CURDATE() - INTERVAL 1 DAY
                AND i.time_of_sale < CURDATE()
                AND store_name = %s
            GROUP BY 
                staff_name
            ORDER BY 
                total_net_amt DESC
            LIMIT 10;
            '''
            cursor.execute(query, (shop_name,))
        elif timeframe == "monthly":
            query = '''
            SELECT 
                staff_name, 
                ROUND(SUM(i.net_amt)) AS total_net_amt,
                s.store_name
            FROM 
                toc_ls_sales_item i
            JOIN 
                toc_ls_sales s ON i.sales_id = s.sales_id
			join
				toc_shops ts on ts.blName = s.store_name
            WHERE 
                i.time_of_sale >= CURDATE() - INTERVAL 1 MONTH
                AND i.time_of_sale < CURDATE()
                AND store_name = %s
            GROUP BY 
                staff_name
            ORDER BY 
                total_net_amt DESC
            LIMIT 10;

            '''
            cursor.execute(query, (shop_name,))

    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result

################################################  REPORT SECTION

def get_sales_report(report_type, from_date, to_date, group_by):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    if report_type == "Sales Report Per Shop":

        # Start with the base query for all report types
        query = '''
                    SELECT 
                        a.store_name, 
                '''

        # Conditionally add DATE_FORMAT based on group_by
        if group_by == 'none':
            query += '''
                        count(*) AS total_sales_quantity,
                        ROUND(SUM(b.net_amt)) AS total_sales_amount
                    '''
        elif group_by == 'day':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d') AS Date,  -- Format as YYYY-MM-DD
                        count(*) AS total_sales_quantity,
                        ROUND(SUM(b.net_amt)) AS total_sales_amount
                    '''
        elif group_by == 'month':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%b/%%Y') AS month,  -- Format as Mon/Year (e.g., Oct/2024)
                        count(*) AS total_sales_quantity,
                        ROUND(SUM(b.net_amt)) AS total_sales_amount
                    '''

        query += '''
                    FROM 
                        toc_ls_sales a
                    JOIN 
                        toc_ls_sales_item b ON a.sales_id = b.sales_id
                    JOIN 
                        toc_product d ON b.item_sku = d.item_sku 
           --         LEFT JOIN 
           --             toc_ls_payments c ON b.sales_id = c.sales_id
                    WHERE 
                        a.time_of_sale >= %s AND a.time_of_sale <= %s
                '''

        # Add dynamic GROUP BY clause based on 'group_by' parameter
        if group_by == 'none':
            query += ''' 
                        GROUP BY a.store_name
                    '''
        elif group_by == 'day':
            query += ''' 
                        GROUP BY a.store_name, DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d')  -- Group by Day
                    '''
        elif group_by == 'month':
            query += ''' 
                        GROUP BY a.store_name, DATE_FORMAT(a.time_of_sale, '%%b/%%Y')  -- Group by Month (e.g., Oct/2024)
                    '''

        # Add ORDER BY clause
        query += '''
                    ORDER BY a.store_name ASC, DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d') ASC;
                '''

    elif report_type == "Sales Report Per Staff":
        # Start the query with columns specific to "Sales Report Per Staff"
        query = '''
                    SELECT 
                        a.store_name,
                        b.staff_name,
                '''

        # Conditionally add DATE_FORMAT based on group_by
        if group_by == 'none':
            query += '''
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''
        elif group_by == 'day':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d') AS Date,  -- Format as YYYY-MM-DD
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''
        elif group_by == 'month':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%b/%%Y') AS month,  -- Format as Mon/Year (e.g., Oct/2024)
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''

        # Add the FROM and JOIN clauses
        query += '''
                    FROM 
                        toc_ls_sales a
                    JOIN 
                        toc_ls_sales_item b ON a.sales_id = b.sales_id
                    WHERE 
                        a.time_of_sale >= %s AND a.time_of_sale <= %s                        
                '''

        # Add dynamic GROUP BY clause based on 'group_by' parameter
        if group_by == 'none':
            query += ''' 
                        GROUP BY a.store_name, b.staff_name
                    '''
        elif group_by == 'day':
            query += ''' 
                        GROUP BY a.store_name, b.staff_name, DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d')  -- Group by Day
                    '''
        elif group_by == 'month':
            query += ''' 
                        GROUP BY a.store_name, b.staff_name, DATE_FORMAT(a.time_of_sale, '%%b/%%Y')  -- Group by Month
                    '''

        # Add ORDER BY clause
        query += '''
                    ORDER BY total_net_amt DESC;
                '''

    elif report_type == "Product Sales Report":
        # Start the query with columns specific to "Product Sales Report"
        query = '''
                    SELECT 
                        b.item_name,
                        b.item_sku,
                '''

        # Conditionally add DATE_FORMAT based on group_by
        if group_by == 'none':
            query += '''
                        SUM(b.quantity) AS total_quantity,
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''
        elif group_by == 'day':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d') AS Date,  -- Format as YYYY-MM-DD
                        SUM(b.quantity) AS total_quantity,
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''
        elif group_by == 'month':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%b/%%Y') AS month,  -- Format as Mon/Year (e.g., Oct/2024)
                        SUM(b.quantity) AS total_quantity,
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''

        # Add the FROM and JOIN clauses
        query += '''
                    FROM 
                        toc_ls_sales a
                    JOIN 
                        toc_ls_sales_item b ON a.sales_id = b.sales_id
                    JOIN
                        toc_product d ON b.item_sku = d.item_sku
                    WHERE 
                        a.time_of_sale >= %s AND a.time_of_sale <= %s
                '''

        # Add dynamic GROUP BY clause based on 'group_by' parameter
        if group_by == 'none':
            query += ''' 
                        GROUP BY b.item_name, b.item_sku
                    '''
        elif group_by == 'day':
            query += ''' 
                        GROUP BY b.item_name, b.item_sku, DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d')  -- Group by Day
                    '''
        elif group_by == 'month':
            query += ''' 
                        GROUP BY b.item_name, b.item_sku, DATE_FORMAT(a.time_of_sale, '%%b/%%Y')  -- Group by Month
                    '''

        # Add ORDER BY clause
        query += '''
                    ORDER BY total_net_amt DESC;
                '''

    elif report_type == "Product Category Sales Report":
        # Start the query with columns specific to "Product Category Sales Report"
        query = '''
                    SELECT 
                        d.stat_group,
                '''

        # Conditionally add DATE_FORMAT based on group_by
        if group_by == 'none':
            query += '''
                        SUM(b.quantity) AS total_quantity,
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''
        elif group_by == 'day':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d') AS Date,  -- Format as YYYY-MM-DD
                        SUM(b.quantity) AS total_quantity,
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''
        elif group_by == 'month':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%b/%%Y') AS month,  -- Format as Mon/Year (e.g., Oct/2024)
                        SUM(b.quantity) AS total_quantity,
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''

        # Add the FROM and JOIN clauses
        query += '''
                    FROM 
                        toc_ls_sales a
                    JOIN 
                        toc_ls_sales_item b ON a.sales_id = b.sales_id
                    JOIN
                        toc_product d ON b.item_sku = d.item_sku
                    WHERE 
                        a.time_of_sale >= %s AND a.time_of_sale <= %s
                '''

        # Add dynamic GROUP BY clause based on 'group_by' parameter
        if group_by == 'none':
            query += ''' 
                        GROUP BY d.stat_group
                    '''
        elif group_by == 'day':
            query += ''' 
                        GROUP BY d.stat_group, DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d')  -- Group by Day
                    '''
        elif group_by == 'month':
            query += ''' 
                        GROUP BY d.stat_group, DATE_FORMAT(a.time_of_sale, '%%b/%%Y')  -- Group by Month
                    '''

        # Add ORDER BY clause
        query += '''
                    ORDER BY total_net_amt DESC;
                '''

    elif report_type == "Customer Sales Report":
        # Start the query with columns specific to "Customer Sales Report"
        query = '''
                    SELECT 
                        CONCAT(m.first_name,' ', m.last_name) AS name,
                        m.email,
                '''

        # Conditionally add DATE_FORMAT based on group_by
        if group_by == 'none':
            query += '''
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''
        elif group_by == 'day':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d') AS Date,  -- Format as YYYY-MM-DD
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''
        elif group_by == 'month':
            query += '''
                        DATE_FORMAT(a.time_of_sale, '%%b/%%Y') AS month,  -- Format as Mon/Year (e.g., Oct/2024)
                        ROUND(SUM(b.net_amt)) AS total_net_amt
                    '''

        # Add the FROM and JOIN clauses
        query += '''
                    FROM 
                        toc_ls_sales a
                    JOIN 
                        toc_ls_sales_item b ON a.sales_id = b.sales_id
                    JOIN
                        toc_ls_payments p ON p.sales_id = a.sales_id
                    JOIN
                        toc_canna_member m ON p.email = m.email
                    WHERE 
                        a.time_of_sale >= %s AND a.time_of_sale <= %s
                '''

        # Add dynamic GROUP BY clause based on 'group_by' parameter
        if group_by == 'none':
            query += ''' 
                        GROUP BY m.first_name, m.last_name, m.email
                    '''
        elif group_by == 'day':
            query += ''' 
                        GROUP BY m.first_name, m.last_name, m.email, DATE_FORMAT(a.time_of_sale, '%%Y-%%m-%%d')  -- Group by Day
                    '''
        elif group_by == 'month':
            query += ''' 
                        GROUP BY m.first_name, m.last_name, m.email, DATE_FORMAT(a.time_of_sale, '%%b/%%Y')  -- Group by Month
                    '''

        # Add ORDER BY clause
        query += '''
                    ORDER BY total_net_amt DESC
                    LIMIT 40;
                '''

    # Execute the query with the given date range
    cursor.execute(query, (from_date, to_date))  # Pass dates as parameters to prevent SQL injection
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return result_as_dicts

def get_db_variance_report(report_type, from_date, to_date, group_by):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Base query initialization
    query = """
        SELECT 
    """

    # Add fields for `group_by == 'none'`
    if group_by == 'none':
        query += """
            creation_date,
            shop_id,
            sku,
            stock_qty_date,
            product_name,
            stock_count,
            count_by,
            last_stock_qty,
            calc_stock_qty,
            variance,
            stock_recount,
            shop_name,
            rejects_qty,
            final_stock_qty,
            replenish_id,
            comments
        """
    elif group_by == 'day':
        query += """
            shop_name,
            DATE_FORMAT(stock_qty_date, '%%Y-%%m-%%d') AS Date,
            COUNT(*) AS total_records,
            ROUND(SUM(ABS(variance)), 2) AS total_variance
        """
    elif group_by == 'month':
        query += """
            shop_name,
            DATE_FORMAT(stock_qty_date, '%%b/%%Y') AS Month,
            COUNT(*) AS total_records,
            ROUND(SUM(ABS(variance)), 2) AS total_variance
        """
    elif group_by == 'user':
        query += """
            count_by AS user,
            COUNT(*) AS total_records,
            ROUND(SUM(ABS(variance)), 2) AS total_variance
        """
    elif group_by == 'shop':
        query += """
            shop_name,
            COUNT(*) AS total_records,
            ROUND(SUM(ABS(variance)), 2) AS total_variance
        """

    # Add FROM clause
    query += """
        FROM toc_stock_variance
        WHERE stock_qty_date >= %s AND stock_qty_date <= %s
    """

    # Filter by report type
    if report_type == "Stock Count Variance":
        query += " AND replenish_id LIKE '%%C'"
    elif report_type == "Stock Receive Variance":
        query += " AND replenish_id LIKE '%%R'"

    # Add dynamic GROUP BY clause if not `none`
    if group_by == 'day':
        query += " GROUP BY shop_name, DATE_FORMAT(stock_qty_date, '%%Y-%%m-%%d')"
    elif group_by == 'month':
        query += " GROUP BY shop_name, DATE_FORMAT(stock_qty_date, '%%b/%%Y')"
    elif group_by == 'user':
        query += " GROUP BY count_by"
    elif group_by == 'shop':
        query += " GROUP BY shop_name"

    # Add ORDER BY clause
    if group_by != 'none':
        query += " ORDER BY shop_name ASC"
        if group_by in ['day', 'month']:
            query += ", stock_qty_date ASC"

    # Execute the query with the given parameters
    cursor.execute(query, (from_date, to_date))
    result = cursor.fetchall()

    # Fetch column names
    columns = [col[0] for col in cursor.description]

    # Convert result tuples to dictionaries
    result_as_dicts = [dict(zip(columns, row)) for row in result]

    cursor.close()
    conn.close()

    return result_as_dicts







