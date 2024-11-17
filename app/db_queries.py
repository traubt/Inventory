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
    SELECT item_name, SUM(tot_amt) AS total_amount
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
    SELECT ts.time_of_sale, SUM(tsi.tot_amt)
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
                i.tot_amt as price,
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
                i.tot_amt as price,
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

def get_recent_product_sales(timeframe, shop_name):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    if shop_name == "Head Office":
        query = f'''
            SELECT product_name, SUM(count_sales_{timeframe}) AS total_count , SUM(total_sales_{timeframe}) AS total_sales
            FROM toc_sales_summary_product
            WHERE total_sales_{timeframe} IS NOT NULL 
            GROUP BY product_name
            ORDER BY total_sales DESC;          
        '''
        cursor.execute(query)
    else:
        query = f'''
            SELECT product_name, SUM(count_sales_{timeframe}) AS total_count , SUM(total_sales_{timeframe}) AS total_sales
            FROM toc_sales_summary_product
            WHERE total_sales_{timeframe} IS NOT NULL AND shop_name = %s
            GROUP BY product_name
            ORDER BY total_sales DESC;
        '''
        cursor.execute(query, (shop_name,))

    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

# db_queries.py
# db_queries.py
def get_hourly_sales(shop_name, timeframe):
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()

    if shop_name == "Head Office":
        if timeframe == "hourly":
            query = '''
                SELECT 
                    DATE_FORMAT(time_of_sale, '%%Y-%%m-%%d %%H:00:00') AS time_of_sale,
                    SUM(total_amount) AS total_amount
                FROM 
                    toc_sales_hourly
                WHERE 
                    time_of_sale >= NOW() - INTERVAL 1 DAY
                GROUP BY 
                    DATE_FORMAT(time_of_sale, '%%Y-%%m-%%d %%H:00:00')
                ORDER BY 
                    time_of_sale DESC
                LIMIT 24;
            '''
            cursor.execute(query)
        elif timeframe == "daily":
            query = '''
                SELECT 
                    DATE_FORMAT(time_of_sale, '%%Y-%%m-%%d') AS time_of_sale,
                    SUM(total_amount) AS total_amount
                FROM 
                    toc_sales_daily
                WHERE 
                    time_of_sale >= NOW() - INTERVAL 1 MONTH
                GROUP BY 
                    DATE_FORMAT(time_of_sale, '%%Y-%%m-%%d')
                ORDER BY 
                    time_of_sale DESC
                LIMIT 30;
            '''
            cursor.execute(query)
    else:
        if timeframe == "hourly":
            query = '''
                SELECT 
                    DATE_FORMAT(time_of_sale, '%%Y-%%m-%%d %%H:00:00') AS time_of_sale,
                    SUM(total_amount) AS total_amount
                FROM 
                    toc_sales_hourly
                WHERE 
                    store_name = %s AND time_of_sale >= NOW() - INTERVAL 1 DAY
                GROUP BY 
                    DATE_FORMAT(time_of_sale, '%%Y-%%m-%%d %%H:00:00')
                ORDER BY 
                    time_of_sale DESC
                LIMIT 24;
            '''
            cursor.execute(query, (shop_name,))
        elif timeframe == "daily":
            query = '''
                SELECT 
                    DATE_FORMAT(time_of_sale, '%%Y-%%m-%%d') AS time_of_sale,
                    SUM(total_amount) AS total_amount
                FROM 
                    toc_sales_daily
                WHERE 
                    store_name = %s AND time_of_sale >= NOW() - INTERVAL 1 MONTH
                GROUP BY 
                    DATE_FORMAT(time_of_sale, '%%Y-%%m-%%d')
                ORDER BY 
                    time_of_sale DESC
                LIMIT 30;
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
            toc_product.stat_group <> 'Specials'
            AND toc_shops.customer = %s;
    '''

    # Execute the query with the parameter
    cursor.execute(query, (shop,))
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result

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
            p.stat_group <> 'Specials'
            AND s.customer = %s
		ORDER BY order_qty desc, product_name asc;
    '''

    # Execute the query with the parameter
    cursor.execute(query, (shop,))
    result = cursor.fetchall()

    cursor.close()
    conn.close()

    return result





