async function populate_sales_chart(fromDate, toDate) {
    let url = '/sales_b2b';  // Updated route without timeframe

    // Ensure the URL includes the date range parameters
    url += `?from_date=${fromDate}&to_date=${toDate}`;

    try {
        const response = await fetch(url);
        const data = await response.json();

        // Check if data exists
        if (!data.rows || data.rows.length === 0) {
            console.warn("No data available to render the chart.");
            return;
        }

        // Extract the sales data and categories correctly from the response
        const salesData = data.rows.map(entry => entry[1]); // Sales data is at index 1
        const categories = data.rows.map(entry => {
            const dateStr = entry[0]; // Date is at index 0
            return new Date(dateStr).toISOString(); // Convert 'YYYY-MM-DD' to ISO string
        });

        // update cards
        const total_net = data['rows'].reduce((sum, item) => sum + item[1], 0);
        const count_orders = data['rows'].reduce((sum, item) => sum + item[2], 0);
        const avg_basket = Math.round(total_net/count_orders);
        $("#sales").text(f_num(count_orders));
        $("#sales-title").html('No. of Sales');
        $("#revenue").text("R"+f_num(Math.round(total_net)));
        $("#revenue-title").html('Sales (Exc. Vat)');
        $("#count_customers").text(f_num(avg_basket));
        $("#customer-title").html('Avg. Basket ');


        const chartContainer = document.querySelector("#reportsChart");

        // Ensure the chart container has proper dimensions
        if (!chartContainer.offsetWidth || !chartContainer.offsetHeight) {
            console.error("Chart container dimensions are not set. Delaying rendering.");
            setTimeout(() => populate_sales_chart(fromDate, toDate), 200); // Retry rendering
            return;
        }

        const options = {
            series: [{
                name: 'Sales',
                data: salesData
            }],
            chart: {
                height: 400,
                type: 'area',
                toolbar: {
                    show: false
                },
            },
            markers: {
                size: 4
            },
            colors: ['#4154f1'],
            fill: {
                type: "gradient",
                gradient: {
                    shadeIntensity: 1,
                    opacityFrom: 0.3,
                    opacityTo: 0.4,
                    stops: [0, 90, 100]
                }
            },
            dataLabels: {
                enabled: false
            },
            stroke: {
                curve: 'smooth',
                width: 2
            },
            xaxis: {
                type: 'datetime',
                categories: categories,
            },
            yaxis: {
                min: 0,
                max: Math.max(...salesData) + 1000,
                forceNiceScale: true
            },
            tooltip: {
                x: {
                    format: 'dd MMM yyyy' // Date format for the tooltip
                },
            }
        };

        // Clear any previous chart instance
        chartContainer.innerHTML = '';

        // Render the chart
        const chart = new ApexCharts(chartContainer, options);
        chart.render();
    } catch (error) {
        console.error('Error fetching sales data:', error);
    }
}

async function populate_shipday_sales(fromDate, toDate) {
    let url = '/shipday_sales';  // Updated route without timeframe

    // Ensure the URL includes the date range parameters
    url += `?from_date=${fromDate}&to_date=${toDate}`;

    try {
        const response = await fetch(url);
        const data = await response.json();

        // Check if data exists
        if (!data.rows || data.rows.length === 0) {
            $("#online_orders").text("R0");
            return;
        }

        // Extract the sales data and categories correctly from the response
        const salesData = data.rows.map(entry => entry[1]); // Sales data is at index 1
        const categories = data.rows.map(entry => {
            const dateStr = entry[0]; // Date is at index 0
            return new Date(dateStr).toISOString(); // Convert 'YYYY-MM-DD' to ISO string
        });

        // update cards
        const total_net = data['rows'].reduce((sum, item) => sum + item[1], 0);
        const count_orders = data['rows'].reduce((sum, item) => sum + item[2], 0);
        const avg_basket = Math.round(total_net/count_orders);
        $("#online_orders").text("R"+f_num(Math.round(total_net)));
    } catch (error) {
        console.error('Error fetching sales data:', error);
    }

}
