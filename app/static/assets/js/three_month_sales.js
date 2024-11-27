async function sales_three_months() {
    try {
        const response = await fetch('/sales_three_months');
        const data = await response.json();

        if (!data.length) {
            console.warn("No data available to render the chart.");
            return;
        }

        // Group data by months and extract store names and total sales
        const months = [...new Set(data.map(item => item.sale_month))];
        const stores = [...new Set(data.map(item => item.store_name))];
        const salesData = months.map(month =>
            stores.map(store => {
                const entry = data.find(item => item.sale_month === month && item.store_name === store);
                return entry ? entry.total_sales : 0;
            })
        );

        // Chart initialization
        const chart = echarts.init(document.getElementById('salesChart'));

        // Chart options
        const options = {
            title: {
                text: 'Sales Per Shop',
                left: 'center'
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: {
                    type: 'shadow'
                }
            },
            legend: {
                data: months,
                bottom: 10
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '10%',
                containLabel: true
            },
            xAxis: {
                type: 'value',
                name: 'Total Sales'
            },
            yAxis: {
                type: 'category',
                name: 'Store',
                data: stores
            },
            series: months.map((month, index) => ({
                name: month,
                type: 'bar',
                data: salesData[index]
            }))
        };

        chart.setOption(options);
    } catch (error) {
        console.error("Error fetching data:", error);
    }
}



