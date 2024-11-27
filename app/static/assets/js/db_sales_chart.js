async function populate_sales_chart(timeframe) {
    let url = '';

    if (timeframe === "hourly") {
        $("#line_chart_title").html('Sales Chart <span>| Hourly</span>');
        url = '/hourly_sales/hourly';
    } else if (timeframe === "daily") {
        $("#line_chart_title").html('Sales Chart <span>| Daily</span>');
        url = '/hourly_sales/daily';
    }

    try {
        const response = await fetch(url);
        const data = await response.json();

        // Convert dates to ISO 8601 format
        const salesData = data.map(entry => entry[2]); // Extract sales data
        const categories = data.map(entry => {
            const dateStr = entry[1];
            return timeframe === "daily"
                ? new Date(dateStr).toISOString() // Convert 'YYYY-MM-DD' to ISO
                : new Date(dateStr.replace(" ", "T") + ":00").toISOString(); // Convert 'YYYY-MM-DD HH:00' to ISO
        });

        if (!salesData.length || !categories.length) {
            console.warn("No data available to render the chart.");
            return;
        }

        const chartContainer = document.querySelector("#reportsChart");

        // Ensure the chart container has proper dimensions
        if (!chartContainer.offsetWidth || !chartContainer.offsetHeight) {
            console.error("Chart container dimensions are not set. Delaying rendering.");
            setTimeout(() => populate_sales_chart(timeframe), 200); // Retry rendering
            return;
        }

        const tooltipFormat = timeframe === "daily" ? 'dd MMM yyyy' : 'dd MMM yyyy HH:mm';

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
                    format: tooltipFormat
                },
            }
        };

        // Clear any previous chart instance
        chartContainer.innerHTML = '';

        // Render the chart
        const chart = new ApexCharts(chartContainer, options);
        chart.render();
    } catch (error) {
        console.error('Error fetching data:', error);
    }
}
