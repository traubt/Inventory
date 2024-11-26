  function dialog(dialog_title, dialog_body) {
      // Set the title of the modal
      $('#exampleModalLabel').text(dialog_title);

      // Set the body content of the modal
      $('#dialog_body').html(dialog_body);

      // Show the modal directly without triggering the button click
      $('#exampleModal').modal('show');
    }

    // Get the current date in yyyy-mm-dd format
function getCurrentDate() {
    const today = new Date();
    const year = today.getFullYear();
    const month = (today.getMonth() + 1).toString().padStart(2, '0'); // Add leading zero if needed
    const day = today.getDate().toString().padStart(2, '0'); // Add leading zero if needed
    return `${year}${month}${day}`;
}

function allOrderQtyZero() {
    return $('#ProductOrderTemplate').DataTable().column(8).data().toArray().every(value => value === 0)
}

async function fetchTOCShops() {
    try {
        const response = await fetch('/api/toc_shops'); // Call the Flask route
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json(); // Parse JSON response
        _shops = data; // Populate _shops with the fetched data
        console.log(_shops); // Log the updated _shops variable to the console
    } catch (error) {
        console.error('Error fetching TOC Shops:', error);
    }
}

// Fetch all products
async function fetchProducts() {
    try {
        const response = await fetch('/api/products'); // Call the Flask route
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const products = await response.json(); // Parse JSON response
        _products = products;
        console.log(_products); // Log the product data to the console
    } catch (error) {
        console.error('Error fetching products:', error);
    }
}

// Fetch all products
async function fetchOpenOrders() {
    try {
        const response = await fetch('/api/open_orders'); // Call the Flask route
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        _open_orders = await response.json(); // Parse JSON response
        console.log(_open_orders);
    } catch (error) {
        console.error('Error fetching products:', error);
    }
}

function getShopCodeByBlName(blName) {
    const shop = _shops.find(item => item.blName === blName);
    return shop ? shop.customer : null; // Return the customer or null if not found
}





