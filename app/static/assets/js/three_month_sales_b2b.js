// three_month_sales_b2b.js

async function sales_three_months_b2b() {
  try {
    const res = await fetch('/sales_three_months_b2b');
    const data = await res.json(); // [{wholesaler, sale_month, total_sales}]

    const chartDom = document.getElementById('salesChart');
    if (!chartDom) {
      console.error('B2B chart container #salesChart not found');
      return;
    }

    if (!Array.isArray(data) || data.length === 0) {
      console.warn('No B2B data available to render the chart.');
      echarts.init(chartDom).clear();
      return;
    }

    // Distinct months (sorted) and wholesaler names
    const months = [...new Set(data.map(d => d.sale_month))]
      .sort((a, b) => new Date(a + '-01') - new Date(b + '-01'));

    const wholesalers = [...new Set(data.map(d => d.wholesaler))];

    // Build matrix: series per month, values aligned to wholesalers order
    const valueByWhMonth = {};
    wholesalers.forEach(w => (valueByWhMonth[w] = {}));
    data.forEach(d => {
      valueByWhMonth[d.wholesaler][d.sale_month] = d.total_sales || 0;
    });

    const series = months.map(m => ({
      name: m,
      type: 'bar',
      data: wholesalers.map(w => valueByWhMonth[w][m] ?? 0),
    }));

    const chart = echarts.init(chartDom);
    chart.setOption({
      title: { text: 'Total Orders', left: 'center' },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { data: months, bottom: 10 },
      grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
      xAxis: { type: 'value', name: 'Total Orders', min: 0 },
      yAxis: { type: 'category', name: 'Wholeseller', data: wholesalers },
      series,
    });

    // responsive
    window.addEventListener('resize', () => chart.resize());
  } catch (err) {
    console.error('Error fetching data:', err);
  }
}

// Auto-init on page load if container exists
document.addEventListener('DOMContentLoaded', () => {
  const el = document.getElementById('salesChart');
  if (el) sales_three_months_b2b();
});
