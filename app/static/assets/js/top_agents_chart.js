async function populateTopAgentChart(timeframe) {
    try {
        // Fetch data from the Flask route
        const response = await fetch(`/top_agent/${timeframe}`);
        if (!response.ok) {
            throw new Error(`Failed to fetch data: ${response.statusText}`);
        }

        const data = await response.json();

        // Extract labels (staff name with shop) and data (total net amount)
        const labels = data.map(agent => `${agent[0]} (${agent[2]})`); // Combine name and shop
        const totalNetAmounts = data.map(agent => agent[1]); // Total quantity sold

        // Remove existing chart instance if it exists
        if (window.topAgentChartInstance) {
            window.topAgentChartInstance.destroy();
        }

        // Create the Bar Chart
        const ctx = document.getElementById("topAgentChart").getContext("2d");
        window.topAgentChartInstance = new Chart(ctx, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    label: "Total Sales (Net Amount)",
                    data: totalNetAmounts,
                    backgroundColor: "rgba(75, 192, 192, 0.2)",
                    borderColor: "rgba(75, 192, 192, 1)",
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: "Staff Name (Shop)"
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: "Total Net Amount"
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error("Error populating Top Agent Chart:", error);
        alert("Failed to load top agents data.");
    }
}
